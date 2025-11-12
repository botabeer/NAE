import json
import os
import logging
import random
from typing import List, Optional, Dict
from threading import Lock
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ================= Logging =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ================= إعداد البيئة =================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ================= Locks =================
content_lock = Lock()
stats_lock = Lock()

# ================= User Stats =================
class UserStats:
    def __init__(self):
        self.stats: Dict[str, dict] = {}
        self.stats_file = "user_stats.json"
        self.load_stats()

    def load_stats(self):
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                self.stats = json.load(f)

    def save_stats(self):
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

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
        rules = [
            (5, "riddles_solved", "حلّال الألغاز"),
            (5, "emoji_solved", "خبير الإيموجي"),
            (3, "games_completed", "محلل شخصيات"),
            (100, "points", "نجم صاعد"),
            (500, "points", "أسطورة")
        ]
        for threshold, key, name in rules:
            if stats.get(key, 0) >= threshold and name not in achievements:
                new_achievements.append(name)
        stats["achievements"].extend(new_achievements)
        return new_achievements

user_stats = UserStats()

# ================= Content Manager =================
class ContentManager:
    def __init__(self):
        self.files: Dict[str, List[str]] = {}
        self.emoji_puzzles: List[dict] = []
        self.riddles: List[dict] = []
        self.poems: List[dict] = []
        self.quotes: List[dict] = []
        self.tips: List[dict] = []
        self.proverbs: List[dict] = []
        self.games: List[dict] = []
        self.used_indices: Dict[str, List[int]] = {}

    def load_file_lines(self, filename: str) -> List[str]:
        if not os.path.exists(filename): return []
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def load_json_file(self, filename: str):
        if not os.path.exists(filename): return []
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)

    def initialize(self):
        self.files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
            "أكثر": self.load_file_lines("more_questions.txt")
        }
        self.emoji_puzzles = self.load_json_file("emojis.json")
        self.riddles = self.load_json_file("riddles.json")
        self.poems = self.load_json_file("poems.json")
        self.quotes = self.load_json_file("quotes.json")
        self.tips = self.load_json_file("tips.json")
        self.proverbs = self.load_json_file("proverbs.json")
        games_data = self.load_json_file("personality_games.json")
        self.games = [games_data[k] for k in sorted(games_data.keys())] if isinstance(games_data, dict) else games_data
        for key in self.files.keys():
            self.used_indices[key] = []

    def get_random_index(self, key: str, max_len: int) -> int:
        with content_lock:
            if len(self.used_indices.get(key, [])) >= max_len:
                self.used_indices[key] = []
            available = [i for i in range(max_len) if i not in self.used_indices.get(key, [])]
            idx = random.choice(available) if available else random.randint(0, max_len-1)
            self.used_indices.setdefault(key, []).append(idx)
            return idx

    def get_content(self, key: str) -> Optional[str]:
        lst = self.files.get(key, [])
        if not lst: return None
        idx = self.get_random_index(key, len(lst))
        return lst[idx]

    def get_emoji_puzzle(self) -> Optional[dict]:
        if not self.emoji_puzzles: return None
        idx = self.get_random_index("ايموجي", len(self.emoji_puzzles))
        return self.emoji_puzzles[idx]

    def get_riddle(self) -> Optional[dict]:
        if not self.riddles: return None
        idx = self.get_random_index("لغز", len(self.riddles))
        return self.riddles[idx]

    def get_poem(self) -> Optional[str]:
        if not self.poems: return None
        idx = self.get_random_index("شعر", len(self.poems))
        poem = self.poems[idx]
        return f"{poem.get('poet','مجهول')}\n\n{poem.get('text','')}"

    def get_quote(self) -> Optional[str]:
        if not self.quotes: return None
        idx = self.get_random_index("اقتباسات", len(self.quotes))
        q = self.quotes[idx]
        return f"{q.get('author','')}\n\n{q.get('text','')}"

    def get_daily_tip(self) -> Optional[dict]:
        if not self.tips: return None
        idx = self.get_random_index("نصيحة", len(self.tips))
        return self.tips[idx]

    def get_proverb(self) -> Optional[dict]:
        if not self.proverbs: return None
        idx = self.get_random_index("أمثال", len(self.proverbs))
        return self.proverbs[idx]

content_manager = ContentManager()
content_manager.initialize()

# ================= Helper =================
def safe_reply(reply_token, messages):
    try:
        if isinstance(messages, list):
            line_bot_api.reply_message(reply_token, messages)
        else:
            line_bot_api.reply_message(reply_token, messages)
    except Exception as e:
        logger.error(f"خطأ في الإرسال: {e}")

# ================= Flask Routes =================
@app.route("/", methods=["GET"])
def home(): return "✓ البوت يعمل", 200

@app.route("/health", methods=["GET"])
def health(): return {"status":"healthy"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature","")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("✗ توقيع غير صالح")
        abort(400)
    except Exception as e:
        logger.error(f"✗ خطأ: {e}")
        abort(500)
    return "OK"

# ================= Handle Messages =================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # مثال: أمر سؤال
    if text == "سؤال":
        content = content_manager.get_content("سؤال") or "لا يوجد أسئلة حالياً."
        safe_reply(event.reply_token, TextSendMessage(text=content))
        user_stats.update_stat(user_id, "total_questions", 1)
        return

    # مثال: أمر تحدي
    if text == "تحدي":
        content = content_manager.get_content("تحدي") or "لا يوجد تحديات حالياً."
        safe_reply(event.reply_token, TextSendMessage(text=content))
        user_stats.update_stat(user_id, "points", 5)
        return

    # مثال: أمر اعتراف
    if text == "اعتراف":
        content = content_manager.get_content("اعتراف") or "لا يوجد اعترافات حالياً."
        safe_reply(event.reply_token, TextSendMessage(text=content))
        user_stats.update_stat(user_id, "points", 3)
        return

    # مثال: شعر
    if text == "شعر":
        content = content_manager.get_poem() or "لا يوجد شعر حالياً."
        safe_reply(event.reply_token, TextSendMessage(text=content))
        return

    # مثال: اقتباسات
    if text == "اقتباسات":
        content = content_manager.get_quote() or "لا يوجد اقتباسات حالياً."
        safe_reply(event.reply_token, TextSendMessage(text=content))
        return

    # مثال: نصائح
    if text == "نصيحة":
        tip = content_manager.get_daily_tip()
        safe_reply(event.reply_token, TextSendMessage(text=tip.get("text","") if tip else "لا يوجد نصائح حالياً."))
        return

    # مثال: أمثال
    if text == "أمثال":
        proverb = content_manager.get_proverb()
        safe_reply(event.reply_token, TextSendMessage(text=proverb.get("text","") if proverb else "لا يوجد أمثال حالياً."))
        return

    # افتراضي
    safe_reply(event.reply_token, TextSendMessage(text="✗ لم أفهم الرسالة، جرب أحد الأوامر: سؤال، تحدي، اعتراف، شعر، اقتباسات، نصيحة، أمثال"))

# ================= Main =================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"✓ البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
