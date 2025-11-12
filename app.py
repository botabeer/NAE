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
    QuickReply, QuickReplyButton, MessageAction, FlexSendMessage
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
def safe_reply(reply_token: str, messages):
    try:
        if reply_token and reply_token != "00000000000000000000000000000000":
            line_bot_api.reply_message(reply_token, messages)
            return True
    except LineBotApiError as e:
        if "Invalid reply token" in str(e):
            logger.warning("⚠ Reply token منتهي الصلاحية")
        else:
            logger.error(f"✗ خطأ في LINE API: {e}")
    except Exception as e:
        logger.error(f"✗ خطأ غير متوقع: {e}")
    return False

# === نظام الإحصائيات ===
class UserStats:
    def __init__(self):
        self.stats: Dict[str, dict] = {}
        self.stats_file = "/content/user_stats.json"
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
            (5, "riddles_solved", "◆ حلّال الألغاز"),
            (5, "emoji_solved", "◆ خبير الإيموجي"),
            (3, "games_completed", "◆ محلل شخصيات"),
            (100, "points", "◆ نجم صاعد"),
            (500, "points", "◆ أسطورة")
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
        self.content_path = "/content/" if os.path.exists("/content/") else "./"
        self.content_files: Dict[str, List[str]] = {}
        self.more_questions: List[str] = []
        self.emoji_puzzles: List[dict] = []
        self.riddles_list: List[dict] = []
        self.games_list: List[dict] = []
        self.poems_list: List[dict] = []
        self.quotes_list: List[dict] = []
        self.daily_tips: List[dict] = []
        self.proverbs_list: List[dict] = []
        self.detailed_results: Dict = {}
        self.used_indices: Dict[str, List[int]] = {}

    def get_file_path(self, filename: str) -> str:
        return os.path.join(self.content_path, filename)

    def load_file_lines(self, filename: str) -> List[str]:
        filepath = self.get_file_path(filename)
        if not os.path.exists(filepath):
            logger.warning(f"⚠ الملف غير موجود: {filepath}")
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                logger.info(f"✓ تم تحميل {len(lines)} سطر من {filename}")
                return lines
        except Exception as e:
            logger.error(f"✗ خطأ في قراءة {filename}: {e}")
            return []

    def load_json_file(self, filename: str) -> Union[dict, list]:
        filepath = self.get_file_path(filename)
        if not os.path.exists(filepath):
            logger.warning(f"⚠ الملف غير موجود: {filepath}")
            return [] if filename.endswith("s.json") else {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✓ تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"✗ خطأ في تحليل {filename}: {e}")
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        logger.info(f"📁 مسار المحتوى: {self.content_path}")
        # الملفات النصية
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }
        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر", "ايموجي", "لغز", "شعر", "اقتباسات", "نصيحة", "امثال"]:
            self.used_indices[key] = []

        self.more_questions = self.load_file_lines("more_questions.txt")
        self.emoji_puzzles = self.load_json_file("emojis.json")
        self.riddles_list = self.load_json_file("riddles.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")
        self.daily_tips = self.load_json_file("tips.json")
        self.proverbs_list = self.load_json_file("proverbs.json")
        data = self.load_json_file("personality_games.json")
        if isinstance(data, dict):
            self.games_list = [data[key] for key in sorted(data.keys())]
        else:
            self.games_list = []
        logger.info("✓ تم تهيئة جميع الملفات بنجاح")

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

content_manager = ContentManager()
content_manager.initialize()

# === QuickReply ===
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="◆ سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="◆ تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="◆ اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="◆ أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="◆ ايموجي", text="ايموجي")),
        QuickReplyButton(action=MessageAction(label="◆ لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="◆ شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="◆ اقتباس", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="◆ تحليل", text="تحليل")),
        QuickReplyButton(action=MessageAction(label="◆ نصيحة", text="نصيحة")),
        QuickReplyButton(action=MessageAction(label="◆ أمثال", text="امثال"))
    ])

# === Flask Webhook ===
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# === Handle Messages ===
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text.strip()
    reply_token = event.reply_token
    if text in content_manager.content_files:
        content = content_manager.get_content(text)
        if content:
            safe_reply(reply_token, TextSendMessage(text=content, quick_reply=create_main_menu()))
        else:
            safe_reply(reply_token, TextSendMessage(text="لا يوجد محتوى متاح حالياً.", quick_reply=create_main_menu()))
    else:
        safe_reply(reply_token, TextSendMessage(text="اختر أحد الخيارات المتاحة.", quick_reply=create_main_menu()))

# === Run App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
