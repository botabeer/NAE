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

# Lavender Glassmorphism Design
C = {
    'bg': '#F8F5FF', 'glass': '#FEFCFF', 'card': '#FFFFFF',
    'primary': '#B794F6', 'secondary': '#D4B5F8', 'accent': '#9061F9',
    'text': '#4A4063', 'text2': '#9B8AA8', 'border': '#E8DFF0',
    'overlay': '#F5F0FA', 'success': '#9061F9'
}

class ContentManager:
    def __init__(self):
        self.data, self.used = {}, {}
    
    def _load(self, f, js=False):
        if not os.path.exists(f): return [] if js or 's.json' in f else {}
        try:
            if js: return json.load(open(f, 'r', encoding='utf-8'))
            return [l.strip() for l in open(f, 'r', encoding='utf-8') if l.strip()]
        except: return [] if js or 's.json' in f else {}
    
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
    'qt': ['اقتباسات','اقتباس','حكمة'], 'a': ['تحليل','شخصية','تحليل شخصية']
}

def parse(t):
    t = t.lower().strip()
    for k, v in CMDS.items():
        if t in [x.lower() for x in v]: return k
    return None

def qr():
    items = ['سؤال','تحدي','اعتراف','موقف','منشن','اقتباسات','لغز','تحليل']
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=f"✦ {i}", text=i)) for i in items])

def hdr(title, icon=''):
    return BoxComponent(
        layout='vertical',
        backgroundColor=C['overlay'],
        cornerRadius='20px',
        paddingAll='18px',
        contents=[
            TextComponent(
                text=f"{icon} {title}" if icon else title,
                weight='bold',
                size='xxl',
                color=C['text'],
                align='center'
            ),
            BoxComponent(
                layout='vertical',
                height='3px',
                backgroundColor=C['primary'],
                cornerRadius='2px',
                margin='md'
            )
        ]
    )

def help_msg():
    sections = [
        ('سؤال','أسئلة متنوعة','❓'), ('تحدي','تحديات شيقة','🎯'),
        ('اعتراف','اعترافات جريئة','💭'), ('موقف','مواقف للنقاش','🤔'),
        ('منشن','أسئلة للأصدقاء','👥'), ('اقتباسات','حكم ملهمة','📖'),
        ('لغز','ألغاز وتلميحات','🧩'), ('تحليل','تحليل الشخصية','🔮')
    ]
    
    items = []
    for t, d, ic in sections:
        items.append(
            BoxComponent(
                layout='horizontal',
                paddingAll='14px',
                backgroundColor=C['card'],
                cornerRadius='16px',
                spacing='md',
                margin='sm',
                contents=[
                    TextComponent(text=ic, size='xl', flex=0, color=C['primary']),
                    BoxComponent(
                        layout='vertical',
                        flex=1,
                        spacing='xs',
                        contents=[
                            TextComponent(text=t, size='md', weight='bold', color=C['text']),
                            TextComponent(text=d, size='xs', color=C['text2'], wrap=True)
                        ]
                    )
                ]
            )
        )
    
    return FlexSendMessage(
        alt_text="القائمة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    hdr('بوت عناد المالكي', '🤖'),
                    TextComponent(
                        text='اختر من القائمة أدناه',
                        size='xs',
                        color=C['text2'],
                        align='center',
                        margin='md'
                    ),
                    SeparatorComponent(margin='lg', color=C['border']),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm', contents=items)
                ]
            )
        )
    )

def riddle_msg(r):
    return FlexSendMessage(
        alt_text="لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    hdr('لغز', '🧩'),
                    BoxComponent(
                        layout='vertical',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='20px',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=r['question'],
                                size='lg',
                                color=C['text'],
                                wrap=True,
                                align='center',
                                weight='bold'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            ButtonComponent(
                                action=MessageAction(label='💡 تلميح', text='لمح'),
                                style='secondary',
                                color=C['secondary'],
                                height='md'
                            ),
                            ButtonComponent(
                                action=MessageAction(label='✓ الجواب', text='جاوب'),
                                style='primary',
                                color=C['primary'],
                                height='md'
                            )
                        ]
                    )
                ]
            )
        )
    )

def ans_msg(answer, t):
    is_sol = 'جاوب' in t
    ic = '✓' if is_sol else '💡'
    title = 'الجواب' if is_sol else 'تلميح'
    
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        paddingAll='16px',
                        backgroundColor=C['overlay'],
                        cornerRadius='18px',
                        contents=[
                            TextComponent(
                                text=f"{ic} {title}",
                                weight='bold',
                                size='xl',
                                color=C['success'] if is_sol else C['secondary'],
                                align='center'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='20px',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=answer,
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
        )
    )

def reply(tk, msg):
    try:
        msgs = []
        if isinstance(msg, FlexSendMessage):
            msgs = [msg, TextSendMessage(text='✦', quick_reply=qr())]
        elif isinstance(msg, TextSendMessage):
            msg.quick_reply = qr()
            msgs = [msg]
        else:
            msgs = [msg]
        bot.reply_message(tk, msgs)
    except Exception as e: 
        logging.error(f"Reply error: {e}")

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
    uid = ev.source.user_id
    t = ev.message.text.strip()
    tl = t.lower()
    
    try:
        # مساعدة
        if tl == 'مساعدة':
            reply(ev.reply_token, help_msg())
            return
        
        # محاولة تحليل الأمر
        cmd = parse(t)
        
        # إذا لم يكن أمر معروف
        if not cmd:
            # لمح
            if tl == 'لمح':
                if uid in state:
                    hint = state[uid].get('hint', 'لا يوجد تلميح')
                    reply(ev.reply_token, ans_msg(hint, 'لمح'))
                return
            
            # جاوب
            if tl == 'جاوب':
                if uid in state:
                    r = state.pop(uid)
                    answer = r.get('answer', 'غير متوفر')
                    reply(ev.reply_token, ans_msg(answer, 'جاوب'))
                return
            
            # تجاهل أي رسالة أخرى
            return
        
        # معالجة الأوامر
        # لغز
        if cmd == 'r':
            r = cm.get('r')
            if r:
                state[uid] = r
                reply(ev.reply_token, riddle_msg(r))
            else:
                reply(ev.reply_token, TextSendMessage(text="❌ لا توجد ألغاز متاحة"))
            return
        
        # اقتباس
        if cmd == 'qt':
            q = cm.get('qt')
            if q:
                msg = f"📖 اقتباس\n\n\"{q.get('text','')}\"\n\n— {q.get('author','مجهول')}"
                reply(ev.reply_token, TextSendMessage(text=msg))
            else:
                reply(ev.reply_token, TextSendMessage(text="❌ لا توجد اقتباسات متاحة"))
            return
        
        # تحليل
        if cmd == 'a':
            reply(ev.reply_token, TextSendMessage(text="🔮 تحليل الشخصية قريباً..."))
            return
        
        # باقي الأوامر
        c = cm.get(cmd)
        if c:
            icons = {'q':'❓','ch':'🎯','cf':'💭','m':'👥','s':'🤔'}
            names = {'q':'سؤال','ch':'تحدي','cf':'اعتراف','m':'منشن','s':'موقف'}
            msg = f"{icons.get(cmd,'▫️')} {names.get(cmd,'')}\n\n{c}"
            reply(ev.reply_token, TextSendMessage(text=msg))
        else:
            reply(ev.reply_token, TextSendMessage(text="❌ لا توجد بيانات متاحة"))
    
    except Exception as e: 
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
