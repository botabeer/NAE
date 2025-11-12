import json
import os
import logging
import random
from typing import List, Optional, Dict, Union
from threading import Lock
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage,
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    ImageComponent, SeparatorComponent, FillerComponent,
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

# === نظام الإحصائيات ===
class UserStats:
    def __init__(self):
        self.stats: Dict[str, dict] = {}
    
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
            self.check_achievements(user_id)
    
    def add_points(self, user_id: str, points: int):
        with stats_lock:
            stats = self.get_user_stats(user_id)
            stats["points"] = stats.get("points", 0) + points
            self.check_achievements(user_id)
    
    def check_achievements(self, user_id: str):
        stats = self.stats[user_id]
        achievements = stats.get("achievements", [])
        
        # إنجازات جديدة
        new_achievements = []
        
        if stats.get("riddles_solved", 0) >= 5 and "🧩 حلّال الألغاز" not in achievements:
            new_achievements.append("🧩 حلّال الألغاز")
        
        if stats.get("emoji_solved", 0) >= 5 and "😊 خبير الإيموجي" not in achievements:
            new_achievements.append("😊 خبير الإيموجي")
        
        if stats.get("games_completed", 0) >= 3 and "🎮 لاعب محترف" not in achievements:
            new_achievements.append("🎮 لاعب محترف")
        
        if stats.get("points", 0) >= 100 and "⭐ نجم ساطع" not in achievements:
            new_achievements.append("⭐ نجم ساطع")
        
        if stats.get("points", 0) >= 500 and "👑 أسطورة" not in achievements:
            new_achievements.append("👑 أسطورة")
        
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
        self.games_list: List[dict] = []
        self.poems_list: List[dict] = []
        self.quotes_list: List[dict] = []
        self.daily_tips: List[dict] = []
        self.detailed_results: Dict = {}
        self.used_indices: Dict[str, List[int]] = {}

    def load_file_lines(self, filename: str) -> List[str]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                logger.info(f"تم تحميل {len(lines)} سطر من {filename}")
                return lines
        except Exception as e:
            logger.error(f"خطأ في قراءة الملف {filename}: {e}")
            return []

    def load_json_file(self, filename: str) -> Union[dict, list]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return [] if filename.endswith("s.json") else {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"خطأ في قراءة أو تحليل JSON {filename}: {e}")
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        # الملفات النصية
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }

        # تهيئة used_indices
        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر", "ايموجي", "لغز", "شعر", "اقتباسات", "نصيحة"]:
            self.used_indices[key] = []

        # ملفات إضافية
        self.more_questions = self.load_file_lines("more_file.txt")
        self.emoji_puzzles = self.load_json_file("emoji_puzzles.json")
        self.riddles_list = self.load_json_file("riddles.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")
        self.daily_tips = self.load_json_file("daily_tips.json")

        # الألعاب
        data = self.load_json_file("personality_games.json")
        if isinstance(data, dict):
            self.games_list = [data[key] for key in sorted(data.keys())]
        else:
            self.games_list = []

        logger.info("تم تهيئة جميع الملفات بنجاح")

    def get_random_index(self, command: str, max_length: int) -> int:
        with content_lock:
            if len(self.used_indices[command]) >= max_length:
                self.used_indices[command] = []
            available_indices = [i for i in range(max_length) if i not in self.used_indices[command]]
            index = random.choice(available_indices) if available_indices else random.randint(0, max_length-1)
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
        return f"📝 {poem_entry.get('poet', 'شاعر مجهول')}\n\n{poem_entry.get('text', '')}"

    def get_quote(self) -> Optional[str]:
        if not self.quotes_list: return None
        index = self.get_random_index("اقتباسات", len(self.quotes_list))
        quote_entry = self.quotes_list[index]
        return f"💭 {quote_entry.get('author', '')}\n\n{quote_entry.get('text', '')}"

    def get_daily_tip(self) -> Optional[dict]:
        if not self.daily_tips: return None
        index = self.get_random_index("نصيحة", len(self.daily_tips))
        return self.daily_tips[index]

# === تهيئة مدير المحتوى ===
content_manager = ContentManager()
content_manager.initialize()

# === الأزرار الرئيسية ===
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="❓ سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="🎯 تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="💬 اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="✨ أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="😊 ايموجي", text="ايموجي")),
        QuickReplyButton(action=MessageAction(label="🧩 لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="📝 شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="💭 اقتباس", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="🎮 لعبة", text="لعبه")),
        QuickReplyButton(action=MessageAction(label="💡 نصيحة", text="نصيحة")),
        QuickReplyButton(action=MessageAction(label="📊 إحصائياتي", text="احصائياتي")),
    ])

# === حالات المستخدمين ===
user_game_state: Dict[str, dict] = {}
user_emoji_state: Dict[str, dict] = {}
user_riddle_state: Dict[str, dict] = {}

# === خريطة الأوامر ===
COMMANDS_MAP = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة", "اسأل"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "أكثر": ["أكثر", "اكثر", "زيادة"],
    "ايموجي": ["ايموجي", "إيموجي", "emoji", "رموز"],
    "لغز": ["لغز", "الغاز", "ألغاز"],
    "شعر": ["شعر"],
    "اقتباسات": ["اقتباسات", "اقتباس", "قول"],
    "نصيحة": ["نصيحة", "نصايح", "tip"],
    "احصائياتي": ["احصائياتي", "إحصائياتي", "احصائيات", "stats"]
}

def find_command(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in COMMANDS_MAP.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# === دوال الألعاب ===
def get_games_list() -> str:
    if not content_manager.games_list:
        return "⚠️ لا توجد ألعاب متاحة حالياً."
    
    lines = ["━━━━━━━━━━━━━━━━━━━", "🎮  الألعاب المتاحة", "━━━━━━━━━━━━━━━━━━━", ""]
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, game in enumerate(content_manager.games_list):
        emoji = number_emojis[i] if i < len(number_emojis) else f"{i+1}."
        game_title = game.get('title', f'اللعبة {i+1}')
        lines.append(f"{emoji} {game_title}")
    
    lines.extend(["", "━━━━━━━━━━━━━━━━━━━", f"📌 أرسل رقم اللعبة (1-{len(content_manager.games_list)})", ""])
    return "\n".join(lines)

def calculate_result(answers: List[str], game_index: int) -> str:
    count = {"أ": 0, "ب": 0, "ج": 0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key, {}).get(
        most_common, f"✅ إجابتك الأكثر: {most_common}\n\n🎯 نتيجتك تعكس شخصية فريدة!"
    )
    
    stats = f"\n\n━━━━━━━━━━━━━━━━━━━\n📊 إحصائياتك\n━━━━━━━━━━━━━━━━━━━\nأ: {count['أ']} | ب: {count['ب']} | ج: {count['ج']}"
    return result_text + stats

def handle_game_selection(event, user_id: str, num: int):
    if 1 <= num <= len(content_manager.games_list):
        game_index = num - 1
        user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        options = "\n".join([f"  {k}. {v}" for k, v in first_q["options"].items()])
        
        msg = f"━━━━━━━━━━━━━━━━━━━\n🎮 {game.get('title', f'اللعبة {num}')}\n━━━━━━━━━━━━━━━━━━━\n\n❓ {first_q['question']}\n\n{options}\n\n━━━━━━━━━━━━━━━━━━━\n📝 أرسل: أ، ب، أو ج"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_game_answer(event, user_id: str, text: str):
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
            
            msg = f"{progress}\n\n❓ {q['question']}\n\n{options}\n\n━━━━━━━━━━━━━━━━━━━\n📝 أرسل: أ، ب، أو ج"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
        else:
            result = calculate_result(state["answers"], state["game_index"])
            user_stats.update_stat(user_id, "games_completed")
            user_stats.add_points(user_id, 50)
            
            new_achievements = user_stats.check_achievements(user_id)
            achievement_msg = ""
            if new_achievements:
                achievement_msg = f"\n\n🎉 إنجاز جديد: {', '.join(new_achievements)}\n+50 نقطة"
            
            final_msg = f"━━━━━━━━━━━━━━━━━━━\n🏁 انتهت اللعبة!\n━━━━━━━━━━━━━━━━━━━\n\n{result}{achievement_msg}\n\n💬 أرسل 'لعبه' لتجربة لعبة أخرى!"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=final_msg, quick_reply=create_main_menu()))
            del user_game_state[user_id]

# === دوال المحتوى ===
def handle_emoji_puzzle(event, user_id: str):
    """معالجة ألغاز الإيموجي"""
    puzzle = content_manager.get_emoji_puzzle()
    if not puzzle:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ لا توجد ألغاز إيموجي متاحة حالياً.", quick_reply=create_main_menu())
        )
        return
    
    user_emoji_state[user_id] = puzzle
    user_stats.update_stat(user_id, "total_questions")
    
    # إذا كان هناك صورة
    if puzzle.get("image") and puzzle["image"].strip():
        line_bot_api.reply_message(
            event.reply_token,
            [
                ImageSendMessage(
                    original_content_url=puzzle["image"],
                    preview_image_url=puzzle["image"]
                ),
                TextSendMessage(
                    text=f"━━━━━━━━━━━━━━━━━━━\n😊 خمّن الإيموجي!\n━━━━━━━━━━━━━━━━━━━\n\n💡 'لمح' للتلميح\n💡 'جاوب' للإجابة",
                    quick_reply=create_main_menu()
                )
            ]
        )
    else:
        # إيموجي نصي
        msg = f"━━━━━━━━━━━━━━━━━━━\n😊 خمّن الإيموجي\n━━━━━━━━━━━━━━━━━━━\n\n{puzzle['question']}\n\n━━━━━━━━━━━━━━━━━━━\n💡 'لمح' للتلميح | 'جاوب' للإجابة"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_riddle(event, user_id: str):
    """معالجة الألغاز العادية"""
    riddle = content_manager.get_riddle()
    if not riddle:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ لا توجد ألغاز متاحة حالياً.", quick_reply=create_main_menu())
        )
        return
    
    user_riddle_state[user_id] = riddle
    user_stats.update_stat(user_id, "total_questions")
    
    # إذا كان هناك صورة
    if riddle.get("image") and riddle["image"].strip():
        line_bot_api.reply_message(
            event.reply_token,
            [
                ImageSendMessage(
                    original_content_url=riddle["image"],
                    preview_image_url=riddle["image"]
                ),
                TextSendMessage(
                    text=f"━━━━━━━━━━━━━━━━━━━\n🧩 اللغز في الصورة!\n━━━━━━━━━━━━━━━━━━━\n\n💡 'لمح' للتلميح\n💡 'جاوب' للإجابة",
                    quick_reply=create_main_menu()
                )
            ]
        )
    else:
        # لغز نصي
        msg = f"━━━━━━━━━━━━━━━━━━━\n🧩 اللغز\n━━━━━━━━━━━━━━━━━━━\n\n{riddle['question']}\n\n━━━━━━━━━━━━━━━━━━━\n💡 'لمح' للتلميح | 'جاوب' للإجابة"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_content_command(event, command: str):
    user_id = event.source.user_id
    
    if command == "ايموجي":
        handle_emoji_puzzle(event, user_id)
        return
    
    if command == "لغز":
        handle_riddle(event, user_id)
        return
    
    if command == "احصائياتي":
        show_user_stats(event, user_id)
        return
    
    user_stats.update_stat(user_id, "total_questions")
    
    if command == "أكثر":
        question = content_manager.get_more_question()
        content = question if question else "⚠️ لا توجد أسئلة متاحة في قسم 'أكثر'."
    
    elif command == "شعر":
        poem = content_manager.get_poem()
        if poem:
            content = f"━━━━━━━━━━━━━━━━━━━\n{poem}\n━━━━━━━━━━━━━━━━━━━"
        else:
            content = "⚠️ لا يوجد شعر متاح حالياً."
    
    elif command == "اقتباسات":
        quote = content_manager.get_quote()
        if quote:
            content = f"━━━━━━━━━━━━━━━━━━━\n{quote}\n━━━━━━━━━━━━━━━━━━━"
        else:
            content = "⚠️ لا توجد اقتباسات متاحة حالياً."
    
    elif command == "نصيحة":
        tip = content_manager.get_daily_tip()
        if tip:
            content = f"━━━━━━━━━━━━━━━━━━━\n💡 {tip.get('title', 'نصيحة اليوم')}\n━━━━━━━━━━━━━━━━━━━\n\n{tip.get('content', '')}\n\n━━━━━━━━━━━━━━━━━━━\n✨ {tip.get('category', '')}"
        else:
            content = "⚠️ لا توجد نصائح متاحة حالياً."
    
    else:
        content = content_manager.get_content(command)
        if content:
            content = f"━━━━━━━━━━━━━━━━━━━\n{content}\n━━━━━━━━━━━━━━━━━━━"
        else:
            content = f"⚠️ لا توجد بيانات متاحة في قسم '{command}' حالياً."
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=content, quick_reply=create_main_menu()))

def handle_answer_command(event, user_id: str):
    """معالجة أمر الإجابة"""
    if user_id in user_emoji_state:
        puzzle = user_emoji_state.pop(user_id)
        user_stats.update_stat(user_id, "emoji_solved")
        user_stats.add_points(user_id, 10)
        
        new_achievements = user_stats.check_achievements(user_id)
        achievement_msg = ""
        if new_achievements:
            achievement_msg = f"\n\n🎉 إنجاز جديد: {', '.join(new_achievements)}"
        
        msg = f"━━━━━━━━━━━━━━━━━━━\n✅ الإجابة الصحيحة\n━━━━━━━━━━━━━━━━━━━\n\n{puzzle['answer']}\n\n+10 نقاط{achievement_msg}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
    
    elif user_id in user_riddle_state:
        riddle = user_riddle_state.pop(user_id)
        user_stats.update_stat(user_id, "riddles_solved")
        user_stats.add_points(user_id, 10)
        
        new_achievements = user_stats.check_achievements(user_id)
        achievement_msg = ""
        if new_achievements:
            achievement_msg = f"\n\n🎉 إنجاز جديد: {', '.join(new_achievements)}"
        
        msg = f"━━━━━━━━━━━━━━━━━━━\n✅ الإجابة الصحيحة\n━━━━━━━━━━━━━━━━━━━\n\n{riddle['answer']}\n\n+10 نقاط{achievement_msg}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_hint_command(event, user_id: str):
    """معالجة أمر التلميح"""
    if user_id in user_emoji_state:
        puzzle = user_emoji_state[user_id]
        hint = puzzle.get('hint', 'لا يوجد تلميح')
        msg = f"━━━━━━━━━━━━━━━━━━━\n💡 تلميح\n━━━━━━━━━━━━━━━━━━━\n\n{hint}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
    
    elif user_id in user_riddle_state:
        riddle = user_riddle_state[user_id]
        hint = riddle.get('hint', 'لا يوجد تلميح')
        msg = f"━━━━━━━━━━━━━━━━━━━\n💡 تلميح\n━━━━━━━━━━━━━━━━━━━\n\n{hint}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def show_user_stats(event, user_id: str):
    """عرض إحصائيات المستخدم"""
    stats = user_stats.get_user_stats(user_id)
    
    # حساب الرتبة
    points = stats.get("points", 0)
    if points < 50:
        rank = "🥉 مبتدئ"
    elif points < 100:
        rank = "🥈 متقدم"
    elif points < 300:
        rank = "🥇 محترف"
    elif points < 500:
        rank = "💎 خبير"
    else:
        rank = "👑 أسطورة"
    
    achievements_list = stats.get("achievements", [])
    achievements_text = "\n".join(achievements_list) if achievements_list else "لا توجد إنجازات بعد"
    
    msg = f"""━━━━━━━━━━━━━━━━━━━
📊 إحصائياتك
━━━━━━━━━━━━━━━━━━━

🏅 الرتبة: {rank}
⭐ النقاط: {points}

📈 الإنجازات:
❓ أسئلة مجاب عليها: {stats.get('total_questions', 0)}
🧩 ألغاز محلولة: {stats.get('riddles_solved', 0)}
😊 إيموجي محلولة: {stats.get('emoji_solved', 0)}
🎮 ألعاب مكتملة: {stats.get('games_completed', 0)}

🏆 الإنجازات المفتوحة:
{achievements_text}

━━━━━━━━━━━━━━━━━━━
💪 استمر في التقدم!"""
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return "✅ البوت يعمل بنجاح!", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy", "service": "line-bot", "version": "2.0"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("توقيع غير صالح")
        abort(400)
    except Exception as e:
        logger.error(f"خطأ في معالجة الطلب: {e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()

    try:
        # رسالة البداية
        if text_lower in ["مساعدة", "help", "بداية", "start", "البداية"]:
            welcome_msg = """━━━━━━━━━━━━━━━━━━━
مرحباً بك! 👋
━━━━━━━━━━━━━━━━━━━

اختر من القائمة أدناه:

❓ سؤال - أسئلة ممتعة
🎯 تحدي - تحديات شيقة
💬 اعتراف - اعترافات صريحة
✨ أكثر - أسئلة "من الأكثر"
😊 ايموجي - ألغاز الإيموجي
🧩 لغز - ألغاز ذكية
📝 شعر - أبيات شعرية
💭 اقتباس - اقتباسات ملهمة
🎮 لعبة - ألعاب شخصية
💡 نصيحة - نصائح يومية
📊 إحصائياتي - تتبع تقدمك

━━━━━━━━━━━━━━━━━━━
🎯 احصل على نقاط وافتح إنجازات!"""
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=welcome_msg, quick_reply=create_main_menu())
            )
            return

        command = find_command(text)
        if command:
            handle_content_command(event, command)
            return

        if text_lower in ["جاوب", "الجواب", "الاجابة", "اجابة", "الحل"]:
            handle_answer_command(event, user_id)
            return

        if text_lower in ["لمح", "تلميح", "hint", "مساعده"]:
            handle_hint_command(event, user_id)
            return

        if text_lower in ["لعبه", "لعبة", "العاب", "ألعاب", "game"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=get_games_list(), quick_reply=create_main_menu())
            )
            return

        if text.isdigit():
            handle_game_selection(event, user_id, int(text))
            return

        if user_id in user_game_state:
            handle_game_answer(event, user_id, text)
            return

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="⚠️ حدث خطأ، يرجى المحاولة مرة أخرى",
                    quick_reply=create_main_menu()
                )
            )
        except:
            pass

# === تشغيل التطبيق ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
