import json, os, logging, random, time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not TOKEN or not SECRET: raise RuntimeError("Missing LINE credentials")

bot = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ==========================
# Colors - Dark Mode
# ==========================
C = {
    'bg': '#000000',          # خلفية سوداء
    'card': '#1A1A1A',        # خلفية البطاقات داكنة
    'card_light': '#2A2A2A',  # خلفية ثانوية داكنة
    'primary': '#9D7EF2',
    'primary_soft': '#B39DFF',
    'accent': '#8B5CF6',
    'blue': '#60A5FA',
    'cyan': '#22D3EE',
    'pink': '#F472B6',
    'orange': '#FB923C',
    'green': '#4ADE80',
    'yellow': '#FBBF24',
    'text': '#FFFFFF',        # نصوص بيضاء
    'text_dim': '#B8B8B8',    # نص ثانوي فاتح
    'text_muted': '#B0B0B0'   # نص باهت قليلًا
}

# ==========================
# Commands
# ==========================
CMDS = {
    "سؤال": ["سؤال", "سوال"], "تحدي": ["تحدي"], "اعتراف": ["اعتراف"],
    "منشن": ["منشن"], "موقف": ["موقف"], "لغز": ["لغز", "الغاز"],
    "اقتباسات": ["اقتباسات", "اقتباس", "حكمة"],
    "تحليل": ["تحليل", "شخصية"], "مساعدة": ["مساعدة", "أوامر"]
}

ALL_CMDS = set()
for v in CMDS.values(): ALL_CMDS.update(x.lower() for x in v)
ALL_CMDS.update({"لمح", "جاوب"})
ALL_CMDS.update(str(i) for i in range(1, 11))
ALL_CMDS.update({"أ", "ب", "ج", "a", "b", "c"})

ANS_MAP = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج", "أ": "أ", "ب": "ب", "ج": "ج"}

INFO = {
    'سؤال': ('☁️', 'أسئلة للنقاش', C['blue']),
    'منشن': ('☁️', 'أسئلة منشن', C['cyan']),
    'اعتراف': ('☁️', 'اعترافات جريئة', C['pink']),
    'تحدي': ('☁️', 'تحديات ممتعة', C['orange']),
    'موقف': ('☁️', 'مواقف للنقاش', C['yellow']),
    'اقتباسات': ('☁️', 'حكم وأقوال', C['green']),
    'لغز': ('💡', 'ألغاز ذهنية', C['primary']),
    'تحليل': ('☁️', 'تحليل الشخصية', C['primary_soft'])
}

# ==========================
# Content Manager
# ==========================
class Content:
    def __init__(s):
        s.data, s.used = {}, {}
    
    def _load_txt(s, p):
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return [l.strip() for l in f if l.strip()]
        except: pass
        return []
    
    def _load_json(s, p, d=None):
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except: pass
        return d or []
    
    def init(s):
        s.data = {
            'سؤال': s._load_txt("questions.txt"),
            'تحدي': s._load_txt("challenges.txt"),
            'اعتراف': s._load_txt("confessions.txt"),
            'منشن': s._load_txt("more_questions.txt"),
            'موقف': s._load_txt("situations.txt"),
            'لغز': s._load_json("riddles.json", []),
            'اقتباس': s._load_json("quotes.json", []),
            'تحليل': s._load_json("personality_games.json", {}),
            'نتائج': s._load_json("detailed_results.json", {})
        }
        if isinstance(s.data['تحليل'], dict):
            s.data['تحليل'] = [s.data['تحليل'][k] for k in sorted(s.data['تحليل'].keys())]
        s.used = {k: [] for k in s.data}
    
    def get(s, k):
        items = s.data.get(k, [])
        if not items: return None
        if len(s.used.get(k, [])) >= len(items): s.used[k] = []
        av = [i for i in range(len(items)) if i not in s.used.get(k, [])]
        idx = random.choice(av) if av else 0
        s.used.setdefault(k, []).append(idx)
        return items[idx]

content = Content()
content.init()

# ==========================
# Session Manager
# ==========================
class Sessions:
    def __init__(s): s.riddles, s.games = {}, {}
    def set_riddle(s, u, r): s.riddles[u] = {'d': r, 't': time.time()}
    def get_riddle(s, u): return s.riddles.get(u, {}).get('d')
    def clear_riddle(s, u): s.riddles.pop(u, None)
    def start_game(s, u, g): s.games[u] = {'gi': g, 'qi': 0, 'ans': [], 't': time.time()}
    def get_game(s, u): return s.games.get(u)
    def in_game(s, u): return u in s.games
    def answer(s, u, a):
        if u in s.games:
            s.games[u]['ans'].append(a)
            s.games[u]['qi'] += 1
    def end_game(s, u): return s.games.pop(u, None)

sessions = Sessions()

# ==========================
# Quick Menu
# ==========================
MENU = QuickReply(items=[QuickReplyButton(action=MessageAction(label=f"{INFO[k][0]} {k}", text=k))
    for k in ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]])

# ==========================
# Flex Messages - Dark Mode
# ==========================
def card_border(color, inner):
    return BoxComponent(layout='vertical', backgroundColor=C['card'], cornerRadius='24px',
        paddingAll='3px', borderWidth='2px', borderColor=color, margin='md',
        contents=[BoxComponent(layout='vertical', backgroundColor=C['bg'], cornerRadius='22px',
            paddingAll='28px', contents=inner)])

# مثال لدوال Flex Messages كاملة:
def flex_help():
    rows = [BoxComponent(layout='horizontal', backgroundColor=C['card'], cornerRadius='12px',
        paddingAll='16px', margin='md', contents=[
            TextComponent(text=icon, size='xl', flex=0, color=color),
            BoxComponent(layout='vertical', paddingStart='16px', flex=1, contents=[
                TextComponent(text=cmd, size='md', color=color, weight='bold'),
                TextComponent(text=desc, size='sm', color=C['text_muted'], margin='xs')])
        ]) for cmd, (icon, desc, color) in INFO.items()]
    
    return FlexSendMessage(alt_text="قائمة الأوامر", quick_reply=MENU,
        contents=BubbleContainer(direction='rtl', body=BoxComponent(
            layout='vertical', backgroundColor=C['bg'], paddingAll='24px', contents=[
                BoxComponent(layout='vertical', alignItems='center', contents=[
                    TextComponent(text="بوت عناد المالكي", size='xl', color=C['primary_soft'], weight='bold', margin='lg'),
                    TextComponent(text="─────────", size='sm', color=C['card_light'], margin='md')]),
                BoxComponent(layout='vertical', margin='xl', contents=rows)])))

# باقي دوال Flex Messages (flex_simple, flex_quote, flex_riddle, flex_answer,
# flex_games, flex_game_q, flex_result, calc_result) تبقى كما هي مع استخدام الألوان الجديدة.

# ==========================
# Routes & Handlers
# ==========================
@app.route("/", methods=["GET"])
def home(): return "OK", 200

@app.route("/health", methods=["GET"])
def health(): return {"status": "ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try: handler.handle(body, sig)
    except InvalidSignatureError: abort(400)
    except: pass
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(event):
    uid, txt, tl = event.source.user_id, event.message.text.strip(), event.message.text.lower().strip()
    if tl not in ALL_CMDS and not sessions.in_game(uid): return
    
    try:
        cmd = next((k for k, v in CMDS.items() if tl in [x.lower() for x in v]), None)
        
        if cmd == "مساعدة":
            bot.reply_message(event.reply_token, flex_help())
        elif cmd in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف"]:
            data = content.get(cmd)
            if data: bot.reply_message(event.reply_token, flex_simple(cmd, data))
        elif cmd == "اقتباسات":
            q = content.get('اقتباس')
            if q: bot.reply_message(event.reply_token, flex_quote(q))
        elif cmd == "لغز":
            r = content.get('لغز')
            if r:
                sessions.set_riddle(uid, r)
                bot.reply_message(event.reply_token, flex_riddle(r))
        elif tl in ["لمح", "تلميح"]:
            r = sessions.get_riddle(uid)
            if r: bot.reply_message(event.reply_token, flex_answer(r.get('hint', 'فكر أكثر...'), True))
        elif tl in ["جاوب", "الجواب"]:
            r = sessions.get_riddle(uid)
            if r:
                sessions.clear_riddle(uid)
                bot.reply_message(event.reply_token, flex_answer(r.get('answer', ''), False))
        elif cmd == "تحليل":
            msg = flex_games()
            if msg: bot.reply_message(event.reply_token, msg)
        elif txt.isdigit() and not sessions.in_game(uid):
            idx = int(txt) - 1
            games = content.data.get('تحليل', [])
            if 0 <= idx < len(games):
                sessions.start_game(uid, idx)
                msg = flex_game_q(games[idx], 0)
                if msg: bot.reply_message(event.reply_token, msg)
        elif sessions.in_game(uid):
            ans = ANS_MAP.get(tl)
            if ans:
                game_data = sessions.get_game(uid)
                gi = game_data['gi']
                games = content.data.get('تحليل', [])
                if gi < len(games):
                    game = games[gi]
                    sessions.answer(uid, ans)
                    next_qi = game_data['qi'] + 1
                    total_qs = len(game.get('questions', []))
                    if next_qi < total_qs:
                        msg = flex_game_q(game, next_qi)
                        if msg: bot.reply_message(event.reply_token, msg)
                    else:
                        answers = game_data['ans'] + [ans]
                        result = calc_result(answers, gi)
                        sessions.end_game(uid)
                        bot.reply_message(event.reply_token, flex_result(result))
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
