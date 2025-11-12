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
    QuickReply, QuickReplyButton, MessageAction
)

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === Environment Variables ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Locks ===
content_lock = Lock()
stats_lock = Lock()

# === Safe reply helper ===
def safe_reply(reply_token: str, messages):
    try:
        if isinstance(messages, list):
            line_bot_api.reply_message(reply_token, messages)
        else:
            line_bot_api.reply_message(reply_token, messages)
    except LineBotApiError as e:
        logger.error(f"⚠ خطأ في الرد: {e}")

# === User Stats ===
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

# === Content Manager ===
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
            return [] if filename.endswith(".json") else {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✓ تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"✗ خطأ في تحليل {filename}: {e}")
            return [] if filename.endswith(".json") else {}

    def initialize(self):
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }
        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر", "ايموجي", "لغز", "شعر", "اقتباسات", "نصيحة"]:
            self.used_indices[key] = []

        self.more_questions = self.load_file_lines("more_questions.txt")
        self.emoji_puzzles = self.load_json_file("emojis.json")
        self.riddles_list = self.load_json_file("riddles.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")
        self.daily_tips = self.load_json_file("tips.json")

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

content_manager = ContentManager()
content_manager.initialize()

# === QuickReply Menu ===
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
        QuickReplyButton(action=MessageAction(label="◆ تحليل شخصية", text="تحليل")),
        QuickReplyButton(action=MessageAction(label="◆ نصيحة", text="نصيحة")),
        QuickReplyButton(action=MessageAction(label="◆ إحصائياتي", text="احصائياتي")),
    ])

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return "✓ البوت يعمل بنجاح", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy", "service": "line-bot", "version": "3.0"}, 200

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

# === Run ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"✓ البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
