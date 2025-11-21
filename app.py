import json
import os
import logging
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
    BubbleContainer, BoxComponent, TextComponent,
    ButtonComponent, SeparatorComponent
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# الإعدادات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not TOKEN or not SECRET:
    raise RuntimeError("يجب تعيين متغيرات LINE")

line_bot = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎨 التصميم - ستايل ليلي داكن أنيق وعصري
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

C = {
    # ═══════════════════════════════════════
    # 🌙 Dark Modern Theme - ليلي داكن عصري
    # ═══════════════════════════════════════
    
    # الخلفيات
    'bg': '#0B0B14',           # خلفية داكنة جداً
    'card': '#161625',         # البطاقات الداكنة
    'card_light': '#1E1E35',   # البطاقات الأفتح قليلاً
    
    # البنفسجي المضيء
    'primary': '#9D7EF2',      # بنفسجي مضيء
    'primary_soft': '#B39DFF', # بنفسجي فاتح
    'accent': '#8B5CF6',       # لون التمييز
    'glow': '#A78BFA',         # للتوهج
    
    # ألوان الأقسام
    'blue': '#60A5FA',         # سؤال
    'cyan': '#22D3EE',         # منشن
    'pink': '#F472B6',         # اعتراف
    'orange': '#FB923C',       # تحدي
    'green': '#4ADE80',        # اقتباسات
    'yellow': '#FBBF24',       # موقف
    
    # النصوص
    'text': '#FFFFFF',         # نص أبيض نقي
    'text_dim': '#B8B8D1',     # نص ثانوي
    'text_muted': '#7E7E9A',   # نص خافت
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# الأوامر
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CMDS = {
    "سؤال": ["سؤال", "سوال"],
    "تحدي": ["تحدي"],
    "اعتراف": ["اعتراف"],
    "منشن": ["منشن"],
    "موقف": ["موقف"],
    "لغز": ["لغز", "الغاز"],
    "اقتباسات": ["اقتباسات", "اقتباس", "حكمة"],
    "تحليل": ["تحليل", "شخصية"],
    "مساعدة": ["مساعدة", "أوامر"]
}

ALL_CMDS = set()
for v in CMDS.values():
    ALL_CMDS.update(x.lower() for x in v)
ALL_CMDS.update({"لمح", "جاوب"})
ALL_CMDS.update(str(i) for i in range(1, 11))
ALL_CMDS.update({"أ", "ب", "ج", "a", "b", "c"})

ANS_MAP = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج", "أ": "أ", "ب": "ب", "ج": "ج"}

# معلومات الأقسام
INFO = {
    '��ؤال': ('☁️', 'أسئلة للنقاش', C['blue']),
    'منشن': ('☁️', 'أسئلة منشن', C['cyan']),
    'اعتراف': ('☁️', 'اعترافات جريئة', C['pink']),
    'تحدي': ('☁️', 'تحديات ممتعة', C['orange']),
    'موقف': ('☁️', 'مواقف للنقاش', C['yellow']),
    'اقتباسات': ('☁️', 'حكم وأقوال', C['green']),
    'لغز': ('💡', 'ألغاز ذهنية', C['primary']),
    'تحليل': ('☁️', 'تحليل الشخصية', C['primary_soft']),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# مدير المحتوى
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Content:
    def __init__(s):
        s.data, s.used = {}, {}
        
    def _txt(s, p):
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return [l.strip() for l in f if l.strip()]
        except: pass
        return []
    
    def _json(s, p, d=None):
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except: pass
        return d or []
    
    def init(s):
        s.data = {
            'سؤال': s._txt("questions.txt"),
            'تحدي': s._txt("challenges.txt"),
            'اعتراف': s._txt("confessions.txt"),
            'منشن': s._txt("more_questions.txt"),
            'موقف': s._txt("situations.txt"),
            'لغز': s._json("riddles.json", []),
            'اقتباس': s._json("quotes.json", []),
            'تحليل': s._json("personality_games.json", {}),
            'نتائج': s._json("detailed_results.json", {})
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# مدير الجلسات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Sessions:
    def __init__(s):
        s.riddles, s.games = {}, {}
    
    def set_riddle(s, uid, r): s.riddles[uid] = {'d': r, 't': time.time()}
    def get_riddle(s, uid): return s.riddles.get(uid, {}).get('d')
    def clear_riddle(s, uid): s.riddles.pop(uid, None)
    def has_riddle(s, uid): return uid in s.riddles
    
    def start_game(s, uid, gi): s.games[uid] = {'gi': gi, 'qi': 0, 'ans': [], 't': time.time()}
    def get_game(s, uid): return s.games.get(uid)
    def in_game(s, uid): return uid in s.games
    def answer(s, uid, a):
        if uid in s.games:
            s.games[uid]['ans'].append(a)
            s.games[uid]['qi'] += 1
    def end_game(s, uid): return s.games.pop(uid, None)

sessions = Sessions()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# القائمة السريعة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MENU = QuickReply(items=[
    QuickReplyButton(action=MessageAction(label=f"{INFO[k][0]} {k}", text=k))
    for k in ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]
])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎨 بناء الرسائل - تصميم نظيف ومتناسق
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def flex_help():
    """رسالة المساعدة"""
    rows = []
    for cmd, (icon, desc, color) in INFO.items():
        rows.append(BoxComponent(
            layout='horizontal',
            backgroundColor=C['card'],
            cornerRadius='12px',
            paddingAll='16px',
            margin='md',
            contents=[
                TextComponent(text=icon, size='xl', flex=0, color=color),
                BoxComponent(
                    layout='vertical',
                    paddingStart='16px',
                    flex=1,
                    contents=[
                        TextComponent(text=cmd, size='md', color=color, weight='bold'),
                        TextComponent(text=desc, size='sm', color=C['text_muted'], margin='xs')
                    ]
                )
            ]
        ))
    
    return FlexSendMessage(
        alt_text="قائمة الأوامر",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        alignItems='center',
                        contents=[
                            TextComponent(
                                text="بوت عناد المالكي",
                                size='xl',
                                color=C['primary_soft'],
                                weight='bold',
                                margin='lg'
                            ),
                            TextComponent(
                                text="─────────",
                                size='sm',
                                color=C['card_light'],
                                margin='md'
                            )
                        ]
                    ),
                    # القائمة
                    BoxComponent(layout='vertical', margin='xl', contents=rows)
                ]
            )
        )
    )

def flex_simple(cmd, text):
    """رسالة بسيطة موحدة - ستايل عصري مع حواف مضيئة"""
    icon, _, color = INFO.get(cmd, ('💬', '', C['primary']))
    
    return FlexSendMessage(
        alt_text=f"{icon} {cmd}",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    # حاوية مع حدود مضيئة
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=color,
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='28px',
                                contents=[
                                    # الرأس
                                    BoxComponent(
                                        layout='horizontal',
                                        justifyContent='center',
                                        alignItems='center',
                                        contents=[
                                            TextComponent(text=icon, size='xxl', flex=0),
                                            TextComponent(
                                                text=cmd,
                                                size='xl',
                                                color=color,
                                                weight='bold',
                                                margin='lg',
                                                flex=0
                                            )
                                        ]
                                    ),
                                    # الخط الفاصل المضيء
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=color,
                                        height='3px',
                                        margin='xl',
                                        cornerRadius='2px'
                                    ),
                                    # المحتوى
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='28px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=text,
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                lineSpacing='10px'
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

def flex_quote(q):
    """رسالة الاقتباس"""
    text = q.get('text', '')
    author = q.get('author', 'مجهول')
    
    return FlexSendMessage(
        alt_text="☁️ اقتباس",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=C['green'],
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='28px',
                                contents=[
                                    TextComponent(text="☁️", size='xxl', align='center', color=C['primary_soft']),
                                    TextComponent(
                                        text="نتيجة التحليل",
                                        size='xl',
                                        color=C['primary_soft'],
                                        weight='bold',
                                        align='center',
                                        margin='lg'
                                    ),
                                    BoxComponent(layout='vertical', backgroundColor=C['primary'], height='3px', margin='xl', cornerRadius='2px'),
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='28px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=result,
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                lineSpacing='10px'
                                            )
                                        ]
                                    ),
                                    ButtonComponent(
                                        action=MessageAction(label='تحليل جديد', text='تحليل'),
                                        style='primary',
                                        color=C['primary'],
                                        height='md',
                                        margin='xl'
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# حساب النتيجة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_result(answers, game_idx):
    cnt = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        cnt[a] = cnt.get(a, 0) + 1
    top = max(cnt, key=cnt.get)
    return content.data.get('نتائج', {}).get(f"لعبة{game_idx + 1}", {}).get(top, "شخصيتك فريدة ومميزة! ✨")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# معالج الأوامر
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def find_cmd(txt):
    t = txt.lower().strip()
    for k, v in CMDS.items():
        if t in [x.lower() for x in v]:
            return k
    return None

def reply(token, msg):
    try:
        line_bot.reply_message(token, msg)
    except Exception as e:
        logger.error(f"Reply error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

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
        pass
    return "OK"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# معالج الرسائل الرئيسي
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(event):
    uid = event.source.user_id
    txt = event.message.text.strip()
    tl = txt.lower()
    
    # تجاهل غير الأوامر (إلا في لعبة)
    if tl not in ALL_CMDS and not sessions.in_game(uid):
        return
    
    try:
        cmd = find_cmd(txt)
        
        # المساعدة
        if cmd == "مساعدة":
            reply(event.reply_token, flex_help())
            return
        
        # الأوامر البسيطة
        if cmd in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف"]:
            data = content.get(cmd)
            if data:
                reply(event.reply_token, flex_simple(cmd, data))
            return
        
        # الاقتباسات
        if cmd == "اقتباسات":
            q = content.get('اقتباس')
            if q:
                reply(event.reply_token, flex_quote(q))
            return
        
        # الألغاز
        if cmd == "لغز":
            r = content.get('لغز')
            if r:
                sessions.set_riddle(uid, r)
                reply(event.reply_token, flex_riddle(r))
            return
        
        # تلميح اللغز
        if tl in ["لمح", "تلميح"]:
            r = sessions.get_riddle(uid)
            if r:
                hint = r.get('hint', 'فكر أكثر...')
                reply(event.reply_token, flex_answer(hint, is_hint=True))
            return
        
        # جواب اللغز
        if tl in ["جاوب", "الجواب"]:
            r = sessions.get_riddle(uid)
            if r:
                sessions.clear_riddle(uid)
                reply(event.reply_token, flex_answer(r.get('answer', ''), is_hint=False))
            return
        
        # قائمة التحليلات
        if cmd == "تحليل":
            msg = flex_games()
            if msg:
                reply(event.reply_token, msg)
            return
        
        # اختيار لعبة تحليل
        if txt.isdigit() and not sessions.in_game(uid):
            idx = int(txt) - 1
            games = content.data.get('تحليل', [])
            if 0 <= idx < len(games):
                sessions.start_game(uid, idx)
                msg = flex_game_q(games[idx], 0)
                if msg:
                    reply(event.reply_token, msg)
            return
        
        # الإجابة في اللعبة
        if sessions.in_game(uid):
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
                        # السؤال التالي
                        msg = flex_game_q(game, next_qi)
                        if msg:
                            reply(event.reply_token, msg)
                    else:
                        # النتيجة
                        answers = game_data['ans'] + [ans]
                        result = calc_result(answers, gi)
                        sessions.end_game(uid)
                        reply(event.reply_token, flex_result(result))
            return
            
    except Exception as e:
        logger.error(f"Error: {e}")
        # لا نرسل رسالة خطأ - نتجاهل بصمت

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# التشغيل
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)', align='center', color=C['green']),
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='28px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=f'❝ {text} ❞',
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                lineSpacing='10px'
                                            ),
                                            BoxComponent(
                                                layout='vertical',
                                                backgroundColor=C['green'],
                                                height='2px',
                                                margin='xl',
                                                cornerRadius='1px',
                                                paddingStart='60px',
                                                paddingEnd='60px'
                                            ),
                                            TextComponent(
                                                text=f"— {author}",
                                                size='md',
                                                color=C['green'],
                                                align='center',
                                                margin='xl',
                                                weight='bold'
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

def flex_riddle(r):
    """رسالة اللغز - ستايل عصري"""
    return FlexSendMessage(
        alt_text="💡 لغز",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    # حاوية مع حدود مضيئة
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=C['primary'],
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='28px',
                                contents=[
                                    # الرأس
                                    BoxComponent(
                                        layout='horizontal',
                                        justifyContent='center',
                                        alignItems='center',
                                        contents=[
                                            TextComponent(text="💡", size='xxl', flex=0),
                                            TextComponent(
                                                text="لغز",
                                                size='xl',
                                                color=C['primary'],
                                                weight='bold',
                                                margin='lg',
                                                flex=0
                                            )
                                        ]
                                    ),
                                    # الخط الفاصل
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['primary'],
                                        height='3px',
                                        margin='xl',
                                        cornerRadius='2px'
                                    ),
                                    # السؤال
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='28px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=r.get('question', ''),
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                lineSpacing='10px',
                                                weight='bold'
                                            )
                                        ]
                                    ),
                                    # الأزرار
                                    BoxComponent(
                                        layout='horizontal',
                                        margin='xl',
                                        spacing='md',
                                        contents=[
                                            ButtonComponent(
                                                action=MessageAction(label='💡 تلميح', text='لمح'),
                                                style='secondary',
                                                color=C['card_light'],
                                                height='md',
                                                flex=1
                                            ),
                                            ButtonComponent(
                                                action=MessageAction(label='✓ الجواب', text='جاوب'),
                                                style='primary',
                                                color=C['primary'],
                                                height='md',
                                                flex=1
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

def flex_answer(text, is_hint=True):
    """رسالة التلميح أو الجواب"""
    title = "تلميح" if is_hint else "الجواب"
    color = C['yellow'] if is_hint else C['green']
    icon = "💡" if is_hint else "✓"
    
    return FlexSendMessage(
        alt_text=f"{icon} {title}",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=color,
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='28px',
                                contents=[
                                    BoxComponent(
                                        layout='horizontal',
                                        justifyContent='center',
                                        alignItems='center',
                                        contents=[
                                            TextComponent(text=icon, size='xxl', color=color, flex=0),
                                            TextComponent(text=title, size='xl', color=color, weight='bold', margin='lg', flex=0)
                                        ]
                                    ),
                                    BoxComponent(layout='vertical', backgroundColor=color, height='3px', margin='xl', cornerRadius='2px'),
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='28px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=text,
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                weight='bold'
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

def flex_games():
    """قائمة ألعاب التحليل"""
    games = content.data.get('تحليل', [])
    if not games: return None
    
    btns = []
    for i, g in enumerate(games[:8], 1):
        btns.append(BoxComponent(
            layout='horizontal',
            backgroundColor=C['card'],
            cornerRadius='12px',
            paddingAll='14px',
            margin='sm',
            action=MessageAction(text=str(i)),
            contents=[
                TextComponent(text=str(i), size='lg', color=C['primary'], weight='bold', flex=0),
                TextComponent(
                    text=g.get('title', f'تحليل {i}'),
                    size='md',
                    color=C['text'],
                    flex=1,
                    margin='xl'
                )
            ]
        ))
    
    return FlexSendMessage(
        alt_text="☁️ تحليل الشخصية",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    TextComponent(text="☁️", size='xxl', align='center', color=C['primary_soft']),
                    TextComponent(
                        text="تحليل الشخصية",
                        size='xl',
                        color=C['primary_soft'],
                        weight='bold',
                        align='center',
                        margin='lg'
                    ),
                    TextComponent(
                        text="اختر نوع التحليل",
                        size='sm',
                        color=C['text_muted'],
                        align='center',
                        margin='sm'
                    ),
                    BoxComponent(layout='vertical', margin='xl', contents=btns)
                ]
            )
        )
    )

def flex_game_q(game, qi):
    """سؤال في لعبة التحليل - ستايل عصري"""
    qs = game.get('questions', [])
    if qi >= len(qs): return None
    
    q = qs[qi]
    title = game.get('title', 'تحليل')
    total = len(qs)
    progress = f"{qi + 1}/{total}"
    
    opts = []
    for k, v in q.get('options', {}).items():
        opts.append(ButtonComponent(
            action=MessageAction(label=f"{k}. {v}", text=k),
            style='secondary',
            color=C['card_light'],
            height='md',
            margin='sm'
        ))
    
    return FlexSendMessage(
        alt_text=f"☁️ {title}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    # حاوية مع حدود مضيئة
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=C['primary'],
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='24px',
                                contents=[
                                    # الرأس
                                    BoxComponent(
                                        layout='horizontal',
                                        justifyContent='space-between',
                                        contents=[
                                            TextComponent(
                                                text=f"☁️ {title}",
                                                size='md',
                                                color=C['primary'],
                                                weight='bold'
                                            ),
                                            TextComponent(
                                                text=progress,
                                                size='md',
                                                color=C['text_muted']
                                            )
                                        ]
                                    ),
                                    # شريط التقدم
                                    BoxComponent(
                                        layout='horizontal',
                                        margin='lg',
                                        backgroundColor=C['card'],
                                        cornerRadius='10px',
                                        height='6px',
                                        contents=[
                                            BoxComponent(
                                                layout='vertical',
                                                backgroundColor=C['primary'],
                                                height='6px',
                                                flex=qi + 1,
                                                cornerRadius='10px'
                                            ),
                                            BoxComponent(
                                                layout='vertical',
                                                backgroundColor=C['card'],
                                                height='6px',
                                                flex=max(1, total - qi - 1),
                                                cornerRadius='10px'
                                            )
                                        ]
                                    ),
                                    # السؤال
                                    BoxComponent(
                                        layout='vertical',
                                        backgroundColor=C['card'],
                                        cornerRadius='20px',
                                        paddingAll='24px',
                                        margin='xl',
                                        contents=[
                                            TextComponent(
                                                text=q.get('question', ''),
                                                size='lg',
                                                color=C['text'],
                                                wrap=True,
                                                align='center',
                                                lineSpacing='8px'
                                            )
                                        ]
                                    ),
                                    # الخيارات
                                    BoxComponent(layout='vertical', margin='xl', contents=opts)
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    )

def flex_result(result):
    """نتيجة التحليل"""
    return FlexSendMessage(
        alt_text="☁️ النتيجة",
        quick_reply=MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='0px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='24px',
                        paddingAll='3px',
                        borderWidth='2px',
                        borderColor=C['primary'],
                        margin='md',
                        contents=[
                            BoxComponent(
                                layout='vertical',
                                backgroundColor=C['bg'],
                                cornerRadius='22px',
                                paddingAll='28px',
                                contents=[
                                    TextComponent(text="☁️", size='xxl
