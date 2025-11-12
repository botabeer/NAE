import json
import os
import logging
import random
from typing import List, Optional, Dict, Union
from threading import Lock
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage,
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, SpacerComponent, FillerComponent,
    QuickReply, QuickReplyButton, MessageAction
)

# === إعداد Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === إعداد متغيرات البيئة ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Locks للتزامن ===
content_lock = Lock()
stats_lock = Lock()

# === دالة آمنة للرد ===
def safe_reply(reply_token, messages):
    """دالة آمنة للرد مع معالجة الأخطاء"""
    try:
        if isinstance(messages, list):
            line_bot_api.reply_message(reply_token, messages)
        else:
            line_bot_api.reply_message(reply_token, messages)
    except LineBotApiError as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")

# === نظام الإحصائيات ===
class UserStats:
    def __init__(self):
        self.stats: Dict[str, dict] = {}
        self.stats_file = "user_stats.json"
        self.load_stats()
    
    def load_stats(self):
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    self.stats = json.load(f)
                logger.info(f"✓ تم تحميل إحصائيات {len(self.stats)} مستخدم")
            except Exception as e:
                logger.error(f"خطأ في تحميل الإحصائيات: {e}")
    
    def save_stats(self):
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ الإحصائيات: {e}")
    
    def get_user_stats(self, user_id: str) -> dict:
        with stats_lock:
            if user_id not in self.stats:
                self.stats[user_id] = {
                    "total_questions": 0,
                    "riddles_solved": 0,
                    "emoji_solved": 0,
                    "games_completed": 0,
                    "points": 0,
                    "last_visit": datetime.now().isoformat(),
                    "achievements": []
                }
            return self.stats[user_id]
    
    def update_stat(self, user_id: str, stat_key: str, increment: int = 1):
        with stats_lock:
            stats = self.get_user_stats(user_id)
            stats[stat_key] = stats.get(stat_key, 0) + increment
            stats["last_visit"] = datetime.now().isoformat()
            new_achievements = self.check_achievements(user_id)
            self.save_stats()
            return new_achievements
    
    def add_points(self, user_id: str, points: int):
        with stats_lock:
            stats = self.get_user_stats(user_id)
            stats["points"] = stats.get("points", 0) + points
            new_achievements = self.check_achievements(user_id)
            self.save_stats()
            return new_achievements
    
    def check_achievements(self, user_id: str):
        stats = self.stats[user_id]
        achievements = stats.get("achievements", [])
        new_achievements = []
        
        achievement_rules = [
            (5, "riddles_solved", "حلّال الألغاز"),
            (5, "emoji_solved", "خبير الإيموجي"),
            (3, "games_completed", "محلل شخصيات"),
            (100, "points", "نجم صاعد"),
            (500, "points", "أسطورة")
        ]
        
        for threshold, key, achievement in achievement_rules:
            if stats.get(key, 0) >= threshold and achievement not in achievements:
                new_achievements.append(achievement)
        
        stats["achievements"].extend(new_achievements)
        return new_achievements

user_stats = UserStats()

# === مدير المحتوى ===
class ContentManager:
    def __init__(self):
        self.content_files: Dict[str, List[str]] = {}
        self.more_questions: List[str] = []
        self.emoji_puzzles: List[dict] = []
        self.riddles_list: List[dict] = []
        self.proverbs_list: List[dict] = []
        self.games_list: List[dict] = []
        self.poems_list: List[dict] = []
        self.quotes_list: List[dict] = []
        self.daily_tips: List[dict] = []
        self.detailed_results: Dict = {}
        self.used_indices: Dict[str, List[int]] = {}

    def load_file_lines(self, filename: str) -> List[str]:
        if not os.path.exists(filename):
            logger.warning(f"⚠ الملف غير موجود: {filename}")
            return []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                logger.info(f"✓ تم تحميل {len(lines)} سطر من {filename}")
                return lines
        except Exception as e:
            logger.error(f"✗ خطأ في قراءة {filename}: {e}")
            return []

    def load_json_file(self, filename: str) -> Union[dict, list]:
        if not os.path.exists(filename):
            logger.warning(f"⚠ الملف غير موجود: {filename}")
            return []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✓ تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"✗ خطأ في تحليل {filename}: {e}")
            return []

    def initialize(self):
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }

        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر", "ايموجي", "لغز", "شعر", "اقتباسات", "نصيحة", "أمثال"]:
            self.used_indices[key] = []

        self.more_questions = self.load_file_lines("more_questions.txt")
        self.emoji_puzzles = self.load_json_file("emojis.json")
        self.riddles_list = self.load_json_file("riddles.json")
        self.daily_tips = self.load_json_file("tips.json")
        self.proverbs_list = self.load_json_file("proverbs.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")

        data = self.load_json_file("personality_games.json")
        if isinstance(data, dict):
            self.games_list = [data[key] for key in sorted(data.keys())]
        elif isinstance(data, list):
            self.games_list = data
        else:
            self.games_list = []

        logger.info("✓ تم تهيئة جميع الملفات بنجاح")

    def get_random_index(self, command: str, max_length: int) -> int:
        with content_lock:
            if len(self.used_indices.get(command, [])) >= max_length:
                self.used_indices[command] = []
            available_indices = [i for i in range(max_length) if i not in self.used_indices.get(command, [])]
            index = random.choice(available_indices) if available_indices else random.randint(0, max_length-1)
            if command not in self.used_indices:
                self.used_indices[command] = []
            self.used_indices[command].append(index)
            return index

    def get_content(self, command: str) -> Optional[str]:
        file_list = self.content_files.get(command, [])
        if not file_list: return None
        index = self.get_random_index(command, len(file_list))
        return file_list[index]

    def get_more_question(self) -> Optional[str]:
        if not self.more_questions: return None
        index = self.get_random_index("أكثر", len(self.more_questions))
        return self.more_questions[index]

    def get_emoji_puzzle(self) -> Optional[dict]:
        if not self.emoji_puzzles: return None
        index = self.get_random_index("ايموجي", len(self.emoji_puzzles))
        return self.emoji_puzzles[index]

    def get_riddle(self) -> Optional[dict]:
        if not self.riddles_list: return None
        index = self.get_random_index("لغز", len(self.riddles_list))
        return self.riddles_list[index]

    def get_poem(self) -> Optional[str]:
        if not self.poems_list: return None
        index = self.get_random_index("شعر", len(self.poems_list))
        poem_entry = self.poems_list[index]
        return f"{poem_entry.get('poet', 'مجهول')}\n\n{poem_entry.get('text', '')}"

    def get_quote(self) -> Optional[str]:
        if not self.quotes_list: return None
        index = self.get_random_index("اقتباسات", len(self.quotes_list))
        quote_entry = self.quotes_list[index]
        return f"{quote_entry.get('author', '')}\n\n{quote_entry.get('text', '')}"

    def get_daily_tip(self) -> Optional[dict]:
        if not self.daily_tips: return None
        index = self.get_random_index("نصيحة", len(self.daily_tips))
        return self.daily_tips[index]
    
    def get_proverb(self) -> Optional[dict]:
        if not self.proverbs_list: return None
        index = self.get_random_index("أمثال", len(self.proverbs_list))
        return self.proverbs_list[index]

content_manager = ContentManager()
content_manager.initialize()

# === رسائل Flex احترافية ===
def create_help_flex() -> FlexSendMessage:
    """رسالة المساعدة"""
    bubble = BubbleContainer(
        size="mega",
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(text="مرحباً بك", weight="bold", size="xxl", color="#1a1a1a", align="center")
                    ],
                    padding_all="20px",
                    background_color="#f5f5f5"
                ),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(
                    layout="vertical",
                    spacing="sm",
                    margin="lg",
                    contents=[
                        TextComponent(text="الأقسام المتاحة", weight="bold", size="md", color="#2a2a2a", margin="md"),
                        SpacerComponent(size="md"),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="سؤال", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="تحدي", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="اعتراف", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="أكثر", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="ايموجي", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="لغز", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="أمثال", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="شعر", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="اقتباس", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="تحليل", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="نصيحة", size="sm", color="#3a3a3a", margin="sm")]),
                        BoxComponent(layout="horizontal", contents=[TextComponent(text="◆", size="sm", color="#6a6a6a", flex=0), TextComponent(text="إحصائياتي", size="sm", color="#3a3a3a", margin="sm")]),
                    ],
                    padding_all="20px"
                ),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(
                    layout="vertical",
                    contents=[TextComponent(text="احصل على النقاط وافتح الإنجازات", size="xs", color="#8a8a8a", align="center")],
                    padding_all="15px",
                    background_color="#fafafa"
                )
            ],
            padding_all="0px"
        )
    )
    return FlexSendMessage(alt_text="المساعدة", contents=bubble)

def create_stats_flex(user_id: str) -> FlexSendMessage:
    """رسالة الإحصائيات"""
    stats = user_stats.get_user_stats(user_id)
    points = stats.get("points", 0)
    
    if points < 50:
        rank, rank_emoji = "مبتدئ", "🥉"
    elif points < 100:
        rank, rank_emoji = "متقدم", "🥈"
    elif points < 300:
        rank, rank_emoji = "محترف", "🥇"
    elif points < 500:
        rank, rank_emoji = "خبير", "💎"
    else:
        rank, rank_emoji = "أسطورة", "👑"
    
    achievements_list = stats.get("achievements", [])
    achievements_contents = []
    if achievements_list:
        for ach in achievements_list:
            achievements_contents.append(BoxComponent(layout="horizontal", contents=[
                TextComponent(text="•", size="xs", color="#6a6a6a", flex=0),
                TextComponent(text=ach, size="xs", color="#3a3a3a", margin="sm", wrap=True)
            ], margin="xs"))
    else:
        achievements_contents.append(TextComponent(text="لا توجد إنجازات بعد", size="xs", color="#8a8a8a", align="center"))
    
    bubble = BubbleContainer(
        size="mega",
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(layout="vertical", contents=[TextComponent(text="إحصائياتك", weight="bold", size="xxl", color="#1a1a1a", align="center")], padding_all="20px", background_color="#f5f5f5"),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(layout="vertical", spacing="md", margin="lg", contents=[
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="الرتبة", weight="bold", size="sm", color="#2a2a2a", flex=2), TextComponent(text=f"{rank_emoji} {rank}", size="sm", color="#3a3a3a", flex=3, align="end")]),
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="النقاط", weight="bold", size="sm", color="#2a2a2a", flex=2), TextComponent(text=str(points), size="sm", color="#3a3a3a", flex=3, align="end")]),
                ], padding_all="20px"),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(layout="vertical", spacing="xs", margin="lg", contents=[
                    TextComponent(text="الإنجازات", weight="bold", size="sm", color="#2a2a2a"),
                    SpacerComponent(size="sm"),
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="الأسئلة", size="xs", color="#5a5a5a", flex=2), TextComponent(text=str(stats.get('total_questions', 0)), size="xs", color="#3a3a3a", flex=1, align="end")]),
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="الألغاز", size="xs", color="#5a5a5a", flex=2), TextComponent(text=str(stats.get('riddles_solved', 0)), size="xs", color="#3a3a3a", flex=1, align="end")]),
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="الإيموجي", size="xs", color="#5a5a5a", flex=2), TextComponent(text=str(stats.get('emoji_solved', 0)), size="xs", color="#3a3a3a", flex=1, align="end")]),
                    BoxComponent(layout="horizontal", contents=[TextComponent(text="التحليلات", size="xs", color="#5a5a5a", flex=2), TextComponent(text=str(stats.get('games_completed', 0)), size="xs", color="#3a3a3a", flex=1, align="end")]),
                ], padding_all="20px"),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(layout="vertical", spacing="xs", margin="lg", contents=[
                    TextComponent(text="الجوائز", weight="bold", size="sm", color="#2a2a2a"),
                    SpacerComponent(size="sm"),
                    BoxComponent(layout="vertical", spacing="xs", contents=achievements_contents)
                ], padding_all="20px"),
                BoxComponent(layout="vertical", contents=[TextComponent(text="استمر في التقدم 💪", size="xs", color="#8a8a8a", align="center")], padding_all="15px", background_color="#fafafa")
            ],
            padding_all="0px"
        )
    )
    return FlexSendMessage(alt_text="إحصائياتك", contents=bubble)

def create_winner_flex(user_id: str, achievement: str, points: int) -> FlexSendMessage:
    """رسالة الفائز"""
    stats = user_stats.get_user_stats(user_id)
    total_points = stats.get("points", 0)
    
    bubble = BubbleContainer(
        size="mega",
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(layout="vertical", contents=[
                    TextComponent(text="🎉", size="xxl", align="center"),
                    TextComponent(text="مبروك!", weight="bold", size="xl", color="#1a1a1a", align="center", margin="md")
                ], padding_all="20px", background_color="#f5f5f5"),
                SeparatorComponent(margin="lg", color="#d0d0d0"),
                BoxComponent(layout="vertical", spacing="md", margin="lg", contents=[
                    TextComponent(text="إنجاز جديد", weight="bold", size="md", color="#2a2a2a", align="center"),
                    SpacerComponent(size="md"),
                    BoxComponent(layout="vertical", contents=[
                        TextComponent(text=achievement, size="lg", color="#3a3a3a", align="center", weight="bold")
                    ], padding_all="15px", background_color="#fafafa", corner_radius="md"),
                    SpacerComponent(size="lg"),
                    BoxComponent(layout="horizontal", contents=[
                        TextComponent(text="النقاط المكتسبة", size="sm", color="#5a5a5a", flex=2),
                        TextComponent(text=f"+{points}", size="sm", color="#2a2a2a", flex=1, align="end", weight="bold")
                    ]),
                    BoxComponent(layout="horizontal", contents=[
                        TextComponent(text="إجمالي النقاط", size="sm", color="#5a5a5a", flex=2),
                        TextComponent(text=str(total_points), size="sm", color="#2a2a2a", flex=1, align="end", weight="bold")
                    ]),
                ], padding_all="20px"),
                BoxComponent(layout="vertical", contents=[
                    TextComponent(text="واصل التقدم! 🌟", size="xs", color="#8a8a8a", align="center")
                ], padding_all="15px", background_color="#fafafa")
            ],
            padding_all="0px"
        )
    )
    return FlexSendMessage(alt_text="مبروك!", contents=bubble)

def create_points_flex(points: int, reason: str) -> FlexSendMessage:
    """رسالة النقاط"""
    bubble = BubbleContainer(
        size="kilo",
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(layout="vertical", contents=[
                    TextComponent(text="✨", size="xl", align="center"),
                    TextComponent(text="نقاط جديدة", weight="bold", size="md", color="#1a1a1a", align="center", margin="sm")
                ], padding_all="15px", background_color="#f5f5f5"),
                SeparatorComponent(margin="md", color="#d0d0d0"),
                BoxComponent(layout="vertical", spacing="sm", margin="md", contents=[
                    TextComponent(text=reason, size="sm", color="#5a5a5a", align="center", wrap=True),
                    SpacerComponent(size="sm"),
                    BoxComponent(layout="vertical", contents=[
                        TextComponent(text=f"+{points}", size="xxl", color="#2a2a2a", align="center", weight="bold")
                    ], padding_all="10px", background_color="#fafafa", corner_radius="md"),
                ], padding_all="15px"),
                BoxComponent(layout="vertical", contents=[
                    TextComponent(text="أحسنت! 👏", size="xs", color="#8a8a8a", align="center")
                ], padding_all="10px", background_color="#fafafa")
            ],
            padding_all="0px"
        )
    )
    return FlexSendMessage(alt_text=f"+{points} نقطة", contents=bubble)

# === الأزرار الرئيسية ===
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="ايموجي", text="ايموجي")),
        QuickReplyButton(action=MessageAction(label="لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="أمثال", text="أمثال")),
        QuickReplyButton(action=MessageAction(label="شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="اقتباس", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="تحليل", text="تحليل")),
        QuickReplyButton(action=MessageAction(label="نصيحة", text="نصيحة")),
    ])

# === حالات المستخدمين ===
user_game_state: Dict[str, dict] = {}
user_emoji_state: Dict[str, dict] = {}
user_riddle_state: Dict[str, dict] = {}
user_proverb_state: Dict[str, dict] = {}

# === خريطة الأوامر ===
COMMANDS_MAP = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة"],
    "تحدي": ["تحدي", "تحديات"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "أكثر": ["أكثر", "اكثر"],
    "ايموجي": ["ايموجي", "إيموجي", "emoji"],
    "لغز": ["لغز", "الغاز"],
    "أمثال": ["أمثال", "امثال"],
    "شعر": ["شعر"],
    "اقتباسات": ["اقتباسات", "اقتباس"],
    "نصيحة": ["نصيحة", "نصايح"]
}

def find_command(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in COMMANDS_MAP.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# === دوال تحليل الشخصية ===
def get_personality_tests_list() -> str:
    if not content_manager.games_list:
        return "لا توجد اختبارات متاحة حالياً"
    
    lines = ["═══════════════", "تحليل الشخصية", "═══════════════", ""]
    for i, game in enumerate(content_manager.games_list, 1):
        lines.append(f"{i}. {game.get('title', f'اختبار {i}')}")
    lines.extend(["", "═══════════════", "أرسل رقم الاختبار"])
    return "\n".join(lines)

def calculate_personality_result(answers: List[str], game_index: int) -> str:
    count = {"أ": 0, "ب": 0, "ج": 0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key, {}).get(
        most_common, "إجاباتك تعكس شخصية فريدة ومميزة"
    )
    
    return result_text

def handle_personality_test_selection(reply_token, user_id: str, num: int):
    if 1 <= num <= len(content_manager.games_list):
        game_index = num - 1
        user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        options = "\n".join([f"  {k}. {v}" for k, v in first_q["options"].items()])
        msg = f"═══════════════\n{game.get('title', f'اختبار {num}')}\n═══════════════\n\n{first_q['question']}\n\n{options}\n\nأرسل: أ، ب، أو ج"
        safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_personality_test_answer(reply_token, user_id: str, text: str):
    state = user_game_state.get(user_id)
    if not state:
        return
    
    answer_map = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج"}
    answer = answer_map.get(text.lower(), text)
    
    if answer in ["أ", "ب", "ج"]:
        state["answers"].append(answer)
        game = content_manager.games_list[state["game_index"]]
        state["question_index"] += 1
        
        if state["question_index"] < len(game["questions"]):
            q = game["questions"][state["question_index"]]
            options = "\n".join([f"  {k}. {v}" for k, v in q["options"].items()])
            progress = f"[{state['question_index']+1}/{len(game['questions'])}]"
            msg = f"{progress}\n\n{q['question']}\n\n{options}\n\nأرسل: أ، ب، أو ج"
            safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
        else:
            result = calculate_personality_result(state["answers"], state["game_index"])
            new_achievements = user_stats.update_stat(user_id, "games_completed")
            user_stats.add_points(user_id, 50)
            
            if new_achievements:
                safe_reply(reply_token, [
                    TextSendMessage(text=f"═══════════════\nنتيجة التحليل\n═══════════════\n\n{result}", quick_reply=create_main_menu()),
                    create_winner_flex(user_id, new_achievements[0], 50)
                ])
            else:
                safe_reply(reply_token, [
                    TextSendMessage(text=f"═══════════════\nنتيجة التحليل\n═══════════════\n\n{result}", quick_reply=create_main_menu()),
                    create_points_flex(50, "إكمال التحليل")
                ])
            del user_game_state[user_id]

# === دوال المحتوى ===
def handle_emoji_puzzle(reply_token, user_id: str):
    puzzle = content_manager.get_emoji_puzzle()
    if not puzzle:
        safe_reply(reply_token, TextSendMessage(text="لا توجد ألغاز إيموجي حالياً", quick_reply=create_main_menu()))
        return
    
    user_emoji_state[user_id] = puzzle
    user_stats.update_stat(user_id, "total_questions")
    
    if puzzle.get("image") and puzzle["image"].strip():
        safe_reply(reply_token, [
            ImageSendMessage(original_content_url=puzzle["image"], preview_image_url=puzzle["image"]),
            TextSendMessage(text="═══════════════\nلغز الإيموجي\n═══════════════\n\nلمح • جاوب", quick_reply=create_main_menu())
        ])
    else:
        msg = f"═══════════════\nلغز الإيموجي\n═══════════════\n\n{puzzle['question']}\n\nلمح • جاوب"
        safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_riddle(reply_token, user_id: str):
    riddle = content_manager.get_riddle()
    if not riddle:
        safe_reply(reply_token, TextSendMessage(text="لا توجد ألغاز حالياً", quick_reply=create_main_menu()))
        return
    
    user_riddle_state[user_id] = riddle
    user_stats.update_stat(user_id, "total_questions")
    
    if riddle.get("image") and riddle["image"].strip():
        safe_reply(reply_token, [
            ImageSendMessage(original_content_url=riddle["image"], preview_image_url=riddle["image"]),
            TextSendMessage(text="═══════════════\nاللغز\n═══════════════\n\nلمح • جاوب", quick_reply=create_main_menu())
        ])
    else:
        msg = f"═══════════════\nاللغز\n═══════════════\n\n{riddle['question']}\n\nلمح • جاوب"
        safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_proverb(reply_token, user_id: str):
    proverb = content_manager.get_proverb()
    if not proverb:
        safe_reply(reply_token, TextSendMessage(text="لا توجد أمثال حالياً", quick_reply=create_main_menu()))
        return
    
    user_proverb_state[user_id] = proverb
    user_stats.update_stat(user_id, "total_questions")
    msg = f"═══════════════\nالمثل\n═══════════════\n\n{proverb['question']}\n\nجاوب للمعنى"
    safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_content_command(reply_token, command: str, user_id: str):
    if command == "ايموجي":
        handle_emoji_puzzle(reply_token, user_id)
        return
    
    if command == "لغز":
        handle_riddle(reply_token, user_id)
        return
    
    if command == "أمثال":
        handle_proverb(reply_token, user_id)
        return
    
    user_stats.update_stat(user_id, "total_questions")
    
    if command == "أكثر":
        question = content_manager.get_more_question()
        content = question if question else "لا توجد أسئلة حالياً"
    elif command == "شعر":
        poem = content_manager.get_poem()
        content = f"═══════════════\nشعر\n═══════════════\n\n{poem}" if poem else "لا يوجد شعر حالياً"
    elif command == "اقتباسات":
        quote = content_manager.get_quote()
        content = f"═══════════════\nاقتباس\n═══════════════\n\n{quote}" if quote else "لا توجد اقتباسات حالياً"
    elif command == "نصيحة":
        tip = content_manager.get_daily_tip()
        content = f"═══════════════\n{tip.get('title', 'نصيحة')}\n═══════════════\n\n{tip.get('content', '')}\n\n{tip.get('category', '')}" if tip else "لا توجد نصائح حالياً"
    else:
        content = content_manager.get_content(command)
        content = f"═══════════════\n{command}\n═══════════════\n\n{content}" if content else f"لا توجد بيانات في '{command}' حالياً"
    
    safe_reply(reply_token, TextSendMessage(text=content, quick_reply=create_main_menu()))

def handle_answer_command(reply_token, user_id: str):
    if user_id in user_emoji_state:
        puzzle = user_emoji_state.pop(user_id)
        new_achievements = user_stats.update_stat(user_id, "emoji_solved")
        user_stats.add_points(user_id, 10)
        
        msg = f"═══════════════\nالإجابة الصحيحة\n═══════════════\n\n{puzzle['answer']}"
        if new_achievements:
            safe_reply(reply_token, [
                TextSendMessage(text=msg, quick_reply=create_main_menu()),
                create_winner_flex(user_id, new_achievements[0], 10)
            ])
        else:
            safe_reply(reply_token, [
                TextSendMessage(text=msg, quick_reply=create_main_menu()),
                create_points_flex(10, "حل لغز الإيموجي")
            ])
    
    elif user_id in user_riddle_state:
        riddle = user_riddle_state.pop(user_id)
        new_achievements = user_stats.update_stat(user_id, "riddles_solved")
        user_stats.add_points(user_id, 10)
        
        msg = f"═══════════════\nالإجابة الصحيحة\n═══════════════\n\n{riddle['answer']}"
        if new_achievements:
            safe_reply(reply_token, [
                TextSendMessage(text=msg, quick_reply=create_main_menu()),
                create_winner_flex(user_id, new_achievements[0], 10)
            ])
        else:
            safe_reply(reply_token, [
                TextSendMessage(text=msg, quick_reply=create_main_menu()),
                create_points_flex(10, "حل اللغز")
            ])
    
    elif user_id in user_proverb_state:
        proverb = user_proverb_state.pop(user_id)
        user_stats.add_points(user_id, 5)
        msg = f"═══════════════\nمعنى المثل\n═══════════════\n\n{proverb['answer']}"
        safe_reply(reply_token, [
            TextSendMessage(text=msg, quick_reply=create_main_menu()),
            create_points_flex(5, "معرفة معنى المثل")
        ])

def handle_hint_command(reply_token, user_id: str):
    if user_id in user_emoji_state:
        puzzle = user_emoji_state[user_id]
        hint = puzzle.get('hint', 'لا يوجد تلميح')
        msg = f"═══════════════\nالتلميح\n═══════════════\n\n{hint}"
        safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
    elif user_id in user_riddle_state:
        riddle = user_riddle_state[user_id]
        hint = riddle.get('hint', 'لا يوجد تلميح')
        msg = f"═══════════════\nالتلميح\n═══════════════\n\n{hint}"
        safe_reply(reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return "✓ البوت يعمل بنجاح", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy", "service": "line-bot", "version": "4.0"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("✗ توقيع غير صالح")
        abort(400)
    except Exception as e:
        logger.error(f"✗ خطأ في معالجة الطلب: {e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    reply_token = event.reply_token
    text = event.message.text.strip()
    text_lower = text.lower()

    try:
        if text_lower in ["مساعدة", "help", "بداية", "start"]:
            safe_reply(reply_token, create_help_flex())
            return

        if text_lower in ["احصائياتي", "إحصائياتي", "احصائيات", "stats"]:
            safe_reply(reply_token, create_stats_flex(user_id))
            return

        command = find_command(text)
        if command:
            handle_content_command(reply_token, command, user_id)
            return

        if text_lower in ["جاوب", "الجواب", "الاجابة", "الحل"]:
            handle_answer_command(reply_token, user_id)
            return

        if text_lower in ["لمح", "تلميح", "hint"]:
            handle_hint_command(reply_token, user_id)
            return

        if text_lower in ["تحليل", "اختبار"]:
            safe_reply(reply_token, TextSendMessage(text=get_personality_tests_list(), quick_reply=create_main_menu()))
            return

        if text.isdigit():
            handle_personality_test_selection(reply_token, user_id, int(text))
            return

        if user_id in user_game_state:
            handle_personality_test_answer(reply_token, user_id, text)
            return

    except Exception as e:
        logger.error(f"✗ خطأ في معالجة الرسالة: {e}", exc_info=True)
        try:
            safe_reply(reply_token, TextSendMessage(text="حدث خطأ، يرجى المحاولة مرة أخرى", quick_reply=create_main_menu()))
        except:
            pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"✓ البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
