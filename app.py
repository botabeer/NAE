import json, os, logging, random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
app = Flask(__name__)

TOKEN, SECRET = os.getenv("LINE_CHANNEL_ACCESS_TOKEN"), os.getenv("LINE_CHANNEL_SECRET")
if not TOKEN or not SECRET: raise RuntimeError("Missing LINE credentials")

bot, handler = LineBotApi(TOKEN), WebhookHandler(SECRET)

# Modern Gradient Design
C = {
    'bg': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'card': '#FFFFFF', 'overlay': 'rgba(102, 126, 234, 0.05)',
    'primary': '#667eea', 'secondary': '#764ba2', 'accent': '#f093fb',
    'text': '#2d3748', 'text2': '#718096', 'border': '#e2e8f0',
    'success': '#48bb78', 'warning': '#ed8936'
}

class ContentManager:
    def __init__(self):
        self.data, self.used = {}, {}
    
    def _load(self, f, is_json=False):
        if not os.path.exists(f): return [] if is_json or 's.json' in f else {}
        try:
            if is_json: return json.load(open(f, 'r', encoding='utf-8'))
            return [l.strip() for l in open(f, 'r', encoding='utf-8') if l.strip()]
        except: return [] if is_json or 's.json' in f else {}
    
    def init(self):
        self.data = {
            'q': self._load('questions.txt'), 'ch': self._load('challenges.txt'),
            'cf': self._load('confessions.txt'), 'm': self._load('more_questions.txt'),
            's': self._load('situations.txt'), 'r': self._load('riddles.json', True),
            'qt': self._load('quotes.json', True), 'res': self._load('detailed_results.json', True)
        }
        g = self._load('personality_games.json', True)
        self.data['g'] = [g[k] for k in sorted(g.keys())] if isinstance(g, dict) else []
        self.used = {k: [] for k in ['q','ch','cf','m','s','r','qt']}
    
    def _rnd(self, k, items):
        if not items: return None
        n = len(items)
        if len(self.used.get(k, [])) >= n: self.used[k] = []
        av = [i for i in range(n) if i not in self.used.get(k, [])]
        idx = random.choice(av) if av else random.randint(0, n-1)
        self.used[k].append(idx)
        return items[idx]
    
    def get(self, t):
        return self._rnd(t, self.data.get(t, []))

cm = ContentManager(); cm.init()
state = {}

CMDS = {
    'q': ['سؤال','سوال'], 'ch': ['تحدي'], 'cf': ['اعتراف'],
    'm': ['منشن'], 's': ['موقف'], 'r': ['لغز'],
    'qt': ['اقتباسات','اقتباس','حكمة'], 'a': ['تحليل','شخصية']
}

def parse(t):
    t = t.lower().strip()
    for k, v in CMDS.items():
        if t in [x.lower() for x in v]: return k
    return None

def qr():
    items = ['سؤال','تحدي','اعتراف','موقف','منشن','اقتباسات','لغز','تحليل']
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=f"✦ {i}", text=i)) for i in items])

def box(layout='vertical', **kw):
    return BoxComponent(layout=layout, **kw)

def txt(text, **kw):
    return TextComponent(text=text, **kw)

def btn(label, text, **kw):
    return ButtonComponent(action=MessageAction(label=label, text=text), **kw)

def hdr(title, icon=''):
    return box(
        paddingAll='20px', backgroundColor=C['card'], cornerRadius='20px',
        contents=[
            box(
                layout='horizontal', spacing='sm', contents=[
                    txt(icon, size='xxl', flex=0) if icon else None,
                    txt(title, weight='bold', size='xxl', color=C['text'], flex=1, align='center')
                ]
            ),
            box(
                height='4px', backgroundColor=C['primary'], cornerRadius='2px',
                margin='md', width='60px', offsetStart='50%', offsetTop='0px'
            )
        ]
    )

def card(content, **kw):
    return box(
        paddingAll='24px', backgroundColor=C['card'], cornerRadius='20px',
        margin='lg', contents=content if isinstance(content, list) else [content],
        **kw
    )

def help_msg():
    sections = [
        ('سؤال','أسئلة متنوعة','❓'), ('تحدي','تحديات شيقة','🎯'),
        ('اعتراف','اعترافات جريئة','💭'), ('موقف','مواقف للنقاش','🤔'),
        ('منشن','أسئلة للأصدقاء','👥'), ('اقتباسات','حكم ملهمة','📖'),
        ('لغز','ألغاز وتلميحات','🧩'), ('تحليل','تحليل الشخصية','🔮')
    ]
    
    items = [
        box(
            layout='horizontal', paddingAll='16px', backgroundColor=C['overlay'],
            cornerRadius='16px', spacing='md', margin='sm',
            contents=[
                txt(ic, size='xl', flex=0, color=C['primary']),
                box(
                    layout='vertical', flex=1, spacing='xs',
                    contents=[
                        txt(t, size='md', weight='bold', color=C['text']),
                        txt(d, size='xs', color=C['text2'], wrap=True)
                    ]
                )
            ]
        )
        for t, d, ic in sections
    ]
    
    return FlexSendMessage(
        alt_text="القائمة",
        contents=BubbleContainer(
            direction='rtl',
            body=box(
                backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr('بوت عناد المالكي', '🤖'),
                    txt('اختر من القائمة أدناه', size='xs', color=C['text2'], align='center', margin='md'),
                    SeparatorComponent(margin='lg', color=C['border']),
                    box(layout='vertical', margin='lg', spacing='sm', contents=items)
                ]
            )
        )
    )

def riddle_msg(r):
    return FlexSendMessage(
        alt_text="لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=box(
                backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr('لغز', '🧩'),
                    card(txt(r['question'], size='lg', color=C['text'], wrap=True, align='center', weight='bold')),
                    box(
                        layout='vertical', margin='xl', spacing='md',
                        contents=[
                            btn('💡 تلميح', 'لمح', style='secondary', color=C['secondary'], height='md'),
                            btn('✓ الجواب', 'جاوب', style='primary', color=C['primary'], height='md')
                        ]
                    )
                ]
            )
        )
    )

def ans_msg(answer, t):
    is_sol = 'جاوب' in t
    return FlexSendMessage(
        alt_text=t,
        contents=BubbleContainer(
            direction='rtl',
            body=box(
                backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr('الجواب' if is_sol else 'تلميح', '✓' if is_sol else '💡'),
                    card(
                        txt(answer, size='lg', color=C['text'], wrap=True, align='center', weight='bold'),
                        backgroundColor=C['success'] + '10' if is_sol else C['card']
                    )
                ]
            )
        )
    )

def reply(tk, msg):
    try:
        msgs = [msg]
        if not isinstance(msg, list):
            if isinstance(msg, FlexSendMessage):
                msgs.append(TextSendMessage(text='✦', quick_reply=qr()))
            elif isinstance(msg, TextSendMessage):
                msg.quick_reply = qr()
                msgs = [msg]
        bot.reply_message(tk, msgs)
    except Exception as e: logging.error(f"Reply error: {e}")

@app.route("/")
def home(): return "OK", 200

@app.route("/health")
def health(): return {"status":"ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try: handler.handle(body, sig)
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def msg_handler(ev):
    uid, t = ev.source.user_id, ev.message.text.strip()
    tl = t.lower()
    
    try:
        if tl == 'مساعدة': reply(ev.reply_token, help_msg()); return
        
        cmd = parse(t)
        
        if not cmd:
            if tl == 'لمح':
                if uid in state:
                    reply(ev.reply_token, ans_msg(state[uid].get('hint','لا يوجد'), 'لمح'))
                return
            if tl == 'جاوب':
                if uid in state:
                    r = state.pop(uid)
                    reply(ev.reply_token, ans_msg(r.get('answer','غير متوفر'), 'جاوب'))
                return
            return
        
        if cmd == 'r':
            r = cm.get('r')
            if r:
                state[uid] = r
                reply(ev.reply_token, riddle_msg(r))
            else:
                reply(ev.reply_token, TextSendMessage(text="❌ لا توجد ألغاز"))
        
        elif cmd == 'qt':
            q = cm.get('qt')
            if q:
                msg = f"📖 اقتباس\n\n\"{q.get('text','')}\"\n\n— {q.get('author','مجهول')}"
                reply(ev.reply_token, TextSendMessage(text=msg))
            else:
                reply(ev.reply_token, TextSendMessage(text="❌ لا توجد اقتباسات"))
        
        elif cmd == 'a':
            reply(ev.reply_token, TextSendMessage(text="🔜 قريباً..."))
        
        else:
            c = cm.get(cmd)
            if c:
                icons = {'q':'❓','ch':'🎯','cf':'💭','m':'👥','s':'🤔'}
                names = {'q':'سؤال','ch':'تحدي','cf':'اعتراف','m':'منشن','s':'موقف'}
                msg = f"{icons.get(cmd,'▫️')} {names.get(cmd,'')}\n\n{c}"
                reply(ev.reply_token, TextSendMessage(text=msg))
            else:
                reply(ev.reply_token, TextSendMessage(text="❌ لا توجد بيانات"))
    
    except Exception as e: logging.error(f"Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
