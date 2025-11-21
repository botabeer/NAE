import json
import os
import logging
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

# ═══════════════════════════════════════════════════════════
# إعدادات التطبيق
# ═══════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise RuntimeError("❌ Missing LINE credentials")

bot = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ═══════════════════════════════════════════════════════════
# الألوان - ستايل ليلي داكن (مطابق للصورة)
# ═══════════════════════════════════════════════════════════
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
# الأوامر المتاحة
# ═══════════════════════════════════════════════════════════
COMMANDS = {
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

# معلومات كل أمر
CMD_INFO = {
    'سؤال': ('💭', 'أسئلة للنقاش'),
    'منشن': ('💬', 'أسئلة منشن'),
    'اعتراف': ('💗', 'اعترافات جريئة'),
    'تحدي': ('🎯', 'تحديات ممتعة'),
    'موقف': ('🤔', 'مواقف للنقاش'),
    'اقتباسات': ('✨', 'حكم وأقوال'),
    'لغز': ('💡', 'ألغاز ذهنية'),
    'تحليل': ('🎭', 'تحليل الشخصية')
}

# الكلمات المفتاحية
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
# مدير المحتوى
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
# مدير الجلسات
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
# القائمة السريعة
# ═══════════════════════════════════════════════════════════
def quick_menu():
    items = [QuickReplyButton(action=MessageAction(label=f"{CMD_INFO[c][0]} {c}", text=c)) 
             for c in ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]]
    return QuickReply(items=items)

# ═══════════════════════════════════════════════════════════
# Flex Components - ستايل ليلي داكن
# ═══════════════════════════════════════════════════════════

def card_box(inner, border_color=None):
    """بطاقة بحدود مضيئة"""
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
    """زر"""
    bg = color if is_primary else C['btn_secondary']
    return BoxComponent(
        layout='vertical',
        backgroundColor=bg,
        cornerRadius='12px',
        paddingAll='14px',
        flex=1,
        action=MessageAction(label=label, text=label),
        contents=[
            TextComponent(text=label, size='md', color=C['text'], weight='bold', align='center')
        ]
    )

# ═══════════════════════════════════════════════════════════
# Flex Messages
# ═══════════════════════════════════════════════════════════

def flex_help():
    """رسالة المساعدة"""
    rows = []
    for cmd, (icon, desc) in CMD_INFO.items():
        rows.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=C['card'],
                cornerRadius='12px',
                paddingAll='14px',
                margin='sm',
                contents=[
                    TextComponent(text=icon, size='lg', flex=0),
                    BoxComponent(layout='vertical', paddingStart='12px', flex=1, contents=[
                        TextComponent(text=cmd, size='md', color=C['primary'], weight='bold'),
                        TextComponent(text=desc, size='sm', color=C['text_muted'], margin='xs')
                    ])
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
                contents=[
                    TextComponent(text="بوت عناد المالكي", size='xl', color=C['primary_light'], weight='bold', align='center'),
                    TextComponent(text="─────────", size='sm', color=C['card'], align='center', margin='md'),
                    BoxComponent(layout='vertical', margin='lg', contents=rows)
                ]
            )
        )
    )

def flex_simple(cmd, text):
    """رسالة بسيطة - مطابق للصورة"""
    icon, title = CMD_INFO.get(cmd, ('💬', cmd))
    if not text or not text.strip():
        text = "المحتوى غير متوفر حالياً"
    
    inner = [
        # العنوان مع الأيقونة
        BoxComponent(
            layout='vertical',
            alignItems='center',
            contents=[
                TextComponent(text=icon, size='xxl'),
                TextComponent(text=title, size='xl', color=C['primary'], weight='bold', margin='md')
            ]
        ),
        # خط فاصل
        BoxComponent(layout='vertical', height='2px', backgroundColor=C['primary'], margin='lg'),
        # المحتوى
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='xl',
            contents=[
                TextComponent(text=str(text).strip(), size='lg', color=C['text'], wrap=True, align='center')
            ]
        ),
        # الأزرار
        BoxComponent(
            layout='horizontal',
            spacing='md',
            margin='xl',
            contents=[
                btn("💡 تلميح", C['btn_secondary'], False),
                btn("✓ التالي", C['primary'], True)
            ]
        )
    ]
    
    return FlexSendMessage(
        alt_text=f"{icon} {title}",
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='16px',
                contents=[card_box(inner)]
            )
        )
    )

def flex_quote(q):
    """رسالة اقتباس"""
    text = q.get('quote', q.get('text', ''))
    author = q.get('author', 'مجهول')
    
    inner = [
        TextComponent(text="✨", size='xxl', align='center'),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='xl',
            contents=[
                TextComponent(text=f"« {text} »", size='lg', color=C['text'], wrap=True, align='center')
            ]
        ),
        TextComponent(text=f"— {author}", size='md', color=C['primary'], align='center', margin='lg'),
        BoxComponent(layout='horizontal', margin='xl', contents=[btn("✨ اقتباس آخر", C['primary'], True)])
    ]
    
    return FlexSendMessage(
        alt_text="✨ اقتباس",
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='16px', contents=[card_box(inner)])
        )
    )

def flex_riddle(r):
    """رسالة لغز"""
    q = r.get('question', '')
    
    inner = [
        BoxComponent(layout='vertical', alignItems='center', contents=[
            TextComponent(text="💡", size='xxl'),
            TextComponent(text="لغز", size='xl', color=C['primary'], weight='bold', margin='md')
        ]),
        BoxComponent(layout='vertical', height='2px', backgroundColor=C['primary'], margin='lg'),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='xl',
            contents=[TextComponent(text=q, size='lg', color=C['text'], wrap=True, align='center')]
        ),
        BoxComponent(
            layout='horizontal',
            spacing='md',
            margin='xl',
            contents=[
                btn("💡 تلميح", C['btn_secondary'], False),
                btn("✓ جاوب", C['primary'], True)
            ]
        )
    ]
    
    return FlexSendMessage(
        alt_text="💡 لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='16px', contents=[card_box(inner)])
        )
    )

def flex_answer(text, is_hint):
    """رسالة الجواب/التلميح"""
    title = "💡 تلميح" if is_hint else "✅ الجواب"
    
    inner = [
        TextComponent(text=title, size='xl', color=C['primary'], weight='bold', align='center'),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='xl',
            contents=[TextComponent(text=text, size='lg', color=C['text'], wrap=True, align='center')]
        )
    ]
    
    return FlexSendMessage(
        alt_text=title,
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='16px', contents=[card_box(inner)])
        )
    )

def flex_games():
    """قائمة الألعاب"""
    games = cm.data.get('تحليل', [])
    if not games:
        return None
    
    rows = []
    for i, g in enumerate(games[:10], 1):
        rows.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=C['card'],
                cornerRadius='12px',
                paddingAll='14px',
                margin='sm',
                action=MessageAction(label=str(i), text=str(i)),
                contents=[
                    TextComponent(text=str(i), size='xl', color=C['primary'], weight='bold', flex=0),
                    TextComponent(text=g.get('title', 'لعبة'), size='md', color=C['text'], margin='md', flex=1)
                ]
            )
        )
    
    return FlexSendMessage(
        alt_text="🎭 اختبارات الشخصية",
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[
                    TextComponent(text="🎭", size='xxl', align='center'),
                    TextComponent(text="اختبارات الشخصية", size='xl', color=C['primary_light'], weight='bold', align='center', margin='md'),
                    BoxComponent(layout='vertical', margin='xl', contents=rows)
                ]
            )
        )
    )

def flex_game_q(game, qi):
    """سؤال اختبار"""
    questions = game.get('questions', [])
    if qi >= len(questions):
        return None
    
    q = questions[qi]
    q_text = q.get('q', '')
    opts = q.get('options', {})
    
    opt_boxes = []
    for k, v in opts.items():
        opt_boxes.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=C['card'],
                cornerRadius='12px',
                paddingAll='14px',
                margin='sm',
                action=MessageAction(label=k, text=k),
                contents=[
                    TextComponent(text=k, size='lg', color=C['primary'], weight='bold', flex=0),
                    TextComponent(text=v, size='md', color=C['text'], margin='md', flex=1)
                ]
            )
        )
    
    inner = [
        TextComponent(text=f"سؤال {qi+1} من {len(questions)}", size='sm', color=C['text_dim'], align='center'),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='lg',
            contents=[TextComponent(text=q_text, size='lg', color=C['text'], wrap=True, align='center', weight='bold')]
        ),
        BoxComponent(layout='vertical', spacing='sm', margin='xl', contents=opt_boxes)
    ]
    
    return FlexSendMessage(
        alt_text=f"السؤال {qi+1}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='16px', contents=[card_box(inner)])
        )
    )

def calc_result(answers, gi):
    """حساب النتيجة"""
    games = cm.data.get('تحليل', [])
    results = cm.data.get('نتائج', {})
    
    if gi >= len(games):
        return {'type': '?', 'title': 'نتيجة', 'text': 'نتيجة مميزة!', 'emoji': '✨'}
    
    game = games[gi]
    gid = game.get('id', '')
    
    cnt = {'أ': 0, 'ب': 0, 'ج': 0}
    for a in answers:
        cnt[a] = cnt.get(a, 0) + 1
    
    rt = max(cnt, key=cnt.get)
    rd = results.get(gid, {}).get(rt, {})
    if not rd:
        rd = game.get('results', {}).get(rt, {})
    
    return {
        'type': rt,
        'title': rd.get('title', 'نتيجتك'),
        'text': rd.get('text', 'نتيجة مميزة!'),
        'emoji': rd.get('emoji', '✨')
    }

def flex_result(r):
    """عرض النتيجة"""
    inner = [
        TextComponent(text=r.get('emoji', '✨'), size='xxl', align='center'),
        TextComponent(text="🎉 نتيجتك 🎉", size='md', color=C['text_dim'], align='center', margin='md'),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['primary'],
            cornerRadius='16px',
            paddingAll='16px',
            margin='xl',
            contents=[TextComponent(text=r.get('title', ''), size='xl', color=C['text'], weight='bold', align='center')]
        ),
        BoxComponent(
            layout='vertical',
            backgroundColor=C['card'],
            cornerRadius='16px',
            paddingAll='20px',
            margin='lg',
            contents=[TextComponent(text=r.get('text', ''), size='md', color=C['text'], wrap=True, align='center')]
        ),
        BoxComponent(layout='horizontal', margin='xl', contents=[btn("🎭 اختبار آخر", C['primary'], True)])
    ]
    
    return FlexSendMessage(
        alt_text="🎉 نتيجتك",
        quick_reply=quick_menu(),
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='16px', contents=[card_box(inner)])
        )
    )

# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

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
# ═══════════════════════════════════════════════════════════

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
        
        # المساعدة
        if cmd == "مساعدة":
            bot.reply_message(event.reply_token, flex_help())
        
        # المحتوى البسيط
        elif cmd in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف"]:
            d = cm.get(cmd)
            if d:
                bot.reply_message(event.reply_token, flex_simple(cmd, d))
        
        # التالي
        elif tl in ["التالي", "💫 التالي"]:
            # إرسال سؤال جديد
            d = cm.get("سؤال")
            if d:
                bot.reply_message(event.reply_token, flex_simple("سؤال", d))
        
        # الاقتباسات
        elif cmd == "اقتباسات":
            q = cm.get('اقتباس')
            if q:
                bot.reply_message(event.reply_token, flex_quote(q))
        
        # اللغز
        elif cmd == "لغز":
            r = cm.get('لغز')
            if r:
                sm.set_riddle(uid, r)
                bot.reply_message(event.reply_token, flex_riddle(r))
        
        # تلميح
        elif tl in ["لمح", "تلميح", "💡 تلميح"]:
            r = sm.get_riddle(uid)
            if r:
                bot.reply_message(event.reply_token, flex_answer(r.get('hint', 'فكر أكثر... 🤔'), True))
        
        # جاوب
        elif tl in ["جاوب", "الجواب", "✓ جاوب"]:
            r = sm.get_riddle(uid)
            if r:
                sm.clear_riddle(uid)
                bot.reply_message(event.reply_token, flex_answer(r.get('answer', ''), False))
        
        # التحليل
        elif cmd == "تحليل":
            msg = flex_games()
            if msg:
                bot.reply_message(event.reply_token, msg)
        
        # اختيار لعبة
        elif txt.isdigit() and not sm.in_game(uid):
            gi = int(txt) - 1
            games = cm.data.get('تحليل', [])
            if 0 <= gi < len(games):
                sm.start_game(uid, gi)
                msg = flex_game_q(games[gi], 0)
                if msg:
                    bot.reply_message(event.reply_token, msg)
        
        # الإجابة على اختبار
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
# تشغيل التطبيق
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
