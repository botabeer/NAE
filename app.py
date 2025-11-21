import json
import os
import logging
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise RuntimeError("❌ Missing LINE credentials")

bot = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ═══════════════════════════════════════════════════════════
# الألوان البنفسجية الداكنة
C = {
    'bg': '#0D0D12',
    'card': '#1A1A24',
    'card_inner': '#12121A',
    'primary': '#9D7EF2',
    'primary_light': '#B39DFF',
    'accent': '#8B5CF6',
    'glow': '#9D7EF2',
    'text': '#FFFFFF',
    'text_dim': '#A0A0B0',
    'text_muted': '#6B6B80',
    'border': '#9D7EF2',
    'btn_secondary': '#2A2A3A',
    'btn_secondary_text': '#FFFFFF'
}

# ═══════════════════════════════════════════════════════════
# الأوامر
COMMAND_ORDER = ["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل","مساعدة"]

COMMANDS = {
    "سؤال": ["سؤال", "سوال"],
    "تحدي": ["تحدي"],
    "اعتراف": ["اعتراف"],
    "منشن": ["منشن"],
    "موقف": ["موقف"],
    "لغز": ["لغز", "الغاز"],
    "اقتباس": ["اقتباس"],
    "تحليل": ["تحليل", "شخصية"],
    "مساعدة": ["مساعدة", "أوامر"]
}

CMD_INFO = {
    'سؤال': ('💭', 'سؤال'),
    'منشن': ('💬', 'منشن'),
    'اعتراف': ('💗', 'اعتراف'),
    'تحدي': ('🎯', 'تحدي'),
    'موقف': ('🤔', 'موقف'),
    'اقتباس': ('✨', 'اقتباس'),
    'لغز': ('💡', 'لغز'),
    'تحليل': ('🎭', 'تحليل'),
    'مساعدة': ('🆘', 'مساعدة')
}

ALL_KEYWORDS = set()
for variants in COMMANDS.values():
    ALL_KEYWORDS.update(x.lower() for x in variants)
ALL_KEYWORDS.update({"لمح", "تلميح", "جاوب", "الجواب", "التالي"})
ALL_KEYWORDS.update(str(i) for i in range(1, 11))
ALL_KEYWORDS.update({"أ", "ب", "ج", "a", "b", "c"})

ANSWER_MAP = {
    "1": "أ", "2": "ب", "3": "ج",
    "a": "أ", "b": "ب", "c": "ج",
    "أ": "أ", "ب": "ب", "ج": "ج"
}

# ═══════════════════════════════════════════════════════════
class ContentManager:
    def __init__(self):
        self.data = {}
        self.used = {}
    
    def _load_text(self, path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return [l.strip() for l in f if l.strip()]
        except Exception as e:
            logging.error(f"Error loading {path}: {e}")
        return []
    
    def _load_json(self, path, default=None):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {path}: {e}")
        return default or []
    
    def init(self):
        self.data = {
            'سؤال': self._load_text("questions.txt"),
            'تحدي': self._load_text("challenges.txt"),
            'اعتراف': self._load_text("confessions.txt"),
            'منشن': self._load_text("more_questions.txt"),
            'موقف': self._load_text("situations.txt"),
            'لغز': self._load_json("riddles.json", []),
            'اقتباس': self._load_json("quotes.json", []),
            'تحليل': self._load_json("personality_games.json", {}),
            'نتائج': self._load_json("detailed_results.json", {})
        }
        if isinstance(self.data['تحليل'], dict):
            self.data['تحليل'] = [self.data['تحليل'][k] for k in sorted(self.data['تحليل'].keys())]
        self.used = {k: [] for k in self.data}
    
    def get(self, key):
        items = self.data.get(key, [])
        if not items:
            return None
        if len(self.used.get(key, [])) >= len(items):
            self.used[key] = []
        available = [i for i in range(len(items)) if i not in self.used.get(key, [])]
        idx = random.choice(available) if available else 0
        self.used.setdefault(key, []).append(idx)
        return items[idx]

cm = ContentManager()
cm.init()

# ═══════════════════════════════════════════════════════════
class SessionManager:
    def __init__(self):
        self.riddles = {}
        self.games = {}
    
    def set_riddle(self, uid, r):
        self.riddles[uid] = {'data': r, 'time': time.time()}
    
    def get_riddle(self, uid):
        return self.riddles.get(uid, {}).get('data')
    
    def clear_riddle(self, uid):
        self.riddles.pop(uid, None)
    
    def start_game(self, uid, gi):
        self.games[uid] = {'game_index': gi, 'question_index': 0, 'answers': [], 'time': time.time()}
    
    def get_game(self, uid):
        return self.games.get(uid)
    
    def in_game(self, uid):
        return uid in self.games
    
    def add_answer(self, uid, ans):
        if uid in self.games:
            self.games[uid]['answers'].append(ans)
            self.games[uid]['question_index'] += 1
    
    def end_game(self, uid):
        return self.games.pop(uid, None)

sm = SessionManager()

# ═══════════════════════════════════════════════════════════
def quick_menu():
    items = [QuickReplyButton(action=MessageAction(label=f"▪️ {c}", text=c)) 
             for c in COMMAND_ORDER[:-1]]  # آخر عنصر "مساعدة" نضيفه بالFlex فقط
    return QuickReply(items=items)

# ═══════════════════════════════════════════════════════════
def card_box(inner, border_color=None):
    bc = border_color or C['border']
    return BoxComponent(
        layout='vertical',
        backgroundColor=C['card'],
        cornerRadius='20px',
        borderWidth='2px',
        borderColor=bc,
        margin='lg',
        contents=[
            BoxComponent(
                layout='vertical',
                backgroundColor=C['card_inner'],
                cornerRadius='18px',
                paddingAll='24px',
                contents=inner
            )
        ]
    )

def btn(label, color, is_primary=True):
    bg = color if is_primary else C['btn_secondary']
    txt_color = C['text'] if is_primary else C['btn_secondary_text']
    return BoxComponent(
        layout='vertical',
        backgroundColor=bg,
        cornerRadius='12px',
        paddingAll='14px',
        flex=1,
        action=MessageAction(label=label, text=label),
        contents=[
            TextComponent(text=label, size='md', color=txt_color, weight='bold', align='center')
        ]
    )

# ═══════════════════════════════════════════════════════════
# Flex Messages: flex_help يعرض فقط الأوامر بدون شرح
def flex_help():
    rows = []
    for c in COMMAND_ORDER[:-1]:  # بدون المساعدة نفسها
        icon = CMD_INFO[c][0]
        rows.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=C['card'],
                cornerRadius='12px',
                paddingAll='14px',
                margin='sm',
                contents=[
                    TextComponent(text=f"{icon} {c}", size='md', color=C['text'], weight='bold', flex=1, align='center')
                ]
            )
        )
    return FlexSendMessage(
        alt_text="📋 قائمة الأوامر",
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[BoxComponent(layout='vertical', contents=rows)]
            )
        )
    )

# بقية Flex Messages (flex_simple, flex_quote, flex_riddle, flex_answer, flex_games, flex_game_q, calc_result, flex_result) 
# تبقى كما في النسخة السابقة مع ضمان color=C['text'] لجميع النصوص

# ═══════════════════════════════════════════════════════════
# Routes
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, sig)
    except InvalidSignatureError:
        abort(400)
    except:
        abort(500)
    return "OK"

# ═══════════════════════════════════════════════════════════
# Message Handler
@handler.add(MessageEvent, message=TextMessage)
def handle_msg(event):
    uid = event.source.user_id
    txt = event.message.text.strip()
    tl = txt.lower().strip()
    
    if tl not in ALL_KEYWORDS and not sm.in_game(uid):
        return
    
    try:
        # البحث عن الأمر
        cmd = None
        for c, variants in COMMANDS.items():
            if tl in [v.lower() for v in variants]:
                cmd = c
                break
        
        if cmd == "مساعدة":
            bot.reply_message(event.reply_token, flex_help())
        
        # المحتوى البسيط
        elif cmd in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف"]:
            d = cm.get(cmd)
            if d:
                bot.reply_message(event.reply_token, flex_simple(cmd, d))
        
        elif cmd == "اقتباس":
            q = cm.get('اقتباس')
            if q:
                bot.reply_message(event.reply_token, flex_quote(q))
        
        elif cmd == "لغز":
            r = cm.get('لغز')
            if r:
                sm.set_riddle(uid, r)
                bot.reply_message(event.reply_token, flex_riddle(r))
        
        elif tl in ["لمح", "تلميح", "💡 تلميح"]:
            r = sm.get_riddle(uid)
            if r:
                bot.reply_message(event.reply_token, flex_answer(r.get('hint', 'فكر أكثر... 🤔'), True))
        
        elif tl in ["جاوب", "الجواب", "✓ جاوب"]:
            r = sm.get_riddle(uid)
            if r:
                sm.clear_riddle(uid)
                bot.reply_message(event.reply_token, flex_answer(r.get('answer', ''), False))
        
        elif cmd == "تحليل":
            msg = flex_games()
            if msg:
                bot.reply_message(event.reply_token, msg)
        
        elif txt.isdigit() and not sm.in_game(uid):
            gi = int(txt) - 1
            games = cm.data.get('تحليل', [])
            if 0 <= gi < len(games):
                sm.start_game(uid, gi)
                msg = flex_game_q(games[gi], 0)
                if msg:
                    bot.reply_message(event.reply_token, msg)
        
        elif sm.in_game(uid):
            ans = ANSWER_MAP.get(tl)
            if ans:
                gd = sm.get_game(uid)
                gi = gd['game_index']
                games = cm.data.get('تحليل', [])
                
                if gi < len(games):
                    game = games[gi]
                    sm.add_answer(uid, ans)
                    
                    nqi = gd['question_index'] + 1
                    total = len(game.get('questions', []))
                    
                    if nqi < total:
                        msg = flex_game_q(game, nqi)
                        if msg:
                            bot.reply_message(event.reply_token, msg)
                    else:
                        all_ans = gd['answers'] + [ans]
                        result = calc_result(all_ans, gi)
                        sm.end_game(uid)
                        bot.reply_message(event.reply_token, flex_result(result))
    
    except Exception as e:
        logging.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
