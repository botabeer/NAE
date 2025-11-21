import json, os, logging, random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
TOKEN, SECRET = os.getenv("LINE_CHANNEL_ACCESS_TOKEN"), os.getenv("LINE_CHANNEL_SECRET")
if not TOKEN or not SECRET:
    raise RuntimeError("Set LINE tokens")
line, handler = LineBotApi(TOKEN), WebhookHandler(SECRET)

# ألوان داكنة مع نصوص سوداء
C = {
    'bg': '#0a0a0c',
    'card': '#13131a',
    'card_inner': '#1a1a22',
    'primary': '#9C6BFF',
    'primary_light': '#C7A3FF',
    'accent': '#A67CFF',
    'border': '#B58CFF',
    'text': '#000000',
    'text_dim': '#333333',
    'text_muted': '#555555',
    'btn_secondary': '#1E1E27',
    'btn_secondary_text': '#000000'
}

class CM:
    def __init__(s):
        s.files = {}
        s.mention = []
        s.riddles = []
        s.games = []
        s.quotes = []
        s.situations = []
        s.results = {}
        s.used = {}

    def ld_l(s, f):
        if not os.path.exists(f): return []
        try: return [l.strip() for l in open(f,'r',encoding='utf-8') if l.strip()]
        except: return []

    def ld_j(s, f):
        if not os.path.exists(f): return [] if 's.json' in f else {}
        try: return json.load(open(f,'r',encoding='utf-8'))
        except: return [] if 's.json' in f else {}

    def init(s):
        s.files = {
            "سؤال": s.ld_l("questions.txt"), 
            "تحدي": s.ld_l("challenges.txt"), 
            "اعتراف": s.ld_l("confessions.txt")
        }
        s.mention = s.ld_l("more_questions.txt")
        s.situations = s.ld_l("situations.txt")
        s.riddles = s.ld_j("riddles.json")
        s.quotes = s.ld_j("quotes.json")
        s.results = s.ld_j("detailed_results.json")
        d = s.ld_j("personality_games.json")
        s.games = [d[k] for k in sorted(d.keys())] if isinstance(d, dict) else []
        s.used = {k: [] for k in list(s.files.keys()) + ["منشن", "لغز", "اقتباس", "موقف"]}

    def rnd(s, k, mx):
        if mx == 0: return 0
        if len(s.used.get(k, [])) >= mx: s.used[k] = []
        av = [i for i in range(mx) if i not in s.used.get(k, [])]
        idx = random.choice(av) if av else random.randint(0, mx-1)
        if k not in s.used: s.used[k] = []
        s.used[k].append(idx)
        return idx

    def get(s, c):
        l = s.files.get(c, [])
        return l[s.rnd(c, len(l))] if l else None

    def get_m(s): return s.mention[s.rnd("منشن", len(s.mention))] if s.mention else None
    def get_s(s): return s.situations[s.rnd("موقف", len(s.situations))] if s.situations else None
    def get_r(s): return s.riddles[s.rnd("لغز", len(s.riddles))] if s.riddles else None
    def get_q(s): return s.quotes[s.rnd("اقتباس", len(s.quotes))] if s.quotes else None

cm = CM()
cm.init()

def menu():
    items = [
        ("سؤال","سؤال"),
        ("منشن","منشن"),
        ("اعتراف","اعتراف"),
        ("تحدي","تحدي"),
        ("موقف","موقف"),
        ("اقتباس","اقتباس"),
        ("لغز","لغز"),
        ("تحليل","تحليل")
    ]
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=l,text=t)) for l,t in items])

def help_flex():
    items = []
    for title in ["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل"]:
        items.append(
            BoxComponent(
                layout='horizontal',
                paddingAll='12px',
                backgroundColor=C['card_inner'],
                cornerRadius='10px',
                contents=[TextComponent(text=title, size='md', color=C['text'], flex=1, weight='bold')]
            )
        )
    return FlexSendMessage(
        alt_text="الأوامر",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='14px',
                        paddingAll='18px',
                        contents=[TextComponent(text="قائمة الأوامر", weight='bold', size='xxl', color=C['text'], align='center')]
                    ),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm', contents=items)
                ]
            )
        )
    )

def content_flex(title, content, cmd_type):
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['card'],
                        cornerRadius='14px',
                        paddingAll='16px',
                        contents=[TextComponent(text=title, weight='bold', size='xl', color=C['text'], align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        paddingAll='20px',
                        backgroundColor=C['card_inner'],
                        cornerRadius='12px',
                        contents=[TextComponent(text=content, size='lg', color=C['text'], wrap=True, align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[ButtonComponent(action=MessageAction(label='التالي', text=cmd_type), style='primary', color=C['primary'], height='md')]
                    )
                ]
            )
        )
    )

def puzzle_flex(p):
    return FlexSendMessage(
        alt_text="لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[
                    BoxComponent(layout='vertical', backgroundColor=C['card'], cornerRadius='14px', paddingAll='16px',
                        contents=[TextComponent(text="لغز", weight='bold', size='xl', color=C['text'], align='center')]),
                    BoxComponent(layout='vertical', margin='lg', paddingAll='20px', backgroundColor=C['card_inner'], cornerRadius='12px',
                        contents=[TextComponent(text=p['question'], size='lg', color=C['text'], wrap=True, align='center', weight='bold')]),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm',
                        contents=[
                            ButtonComponent(action=MessageAction(label='تلميح', text='تلميح'), style='secondary', color=C['btn_secondary'], height='md'),
                            ButtonComponent(action=MessageAction(label='جواب', text='جواب'), style='primary', color=C['primary'], height='md'),
                            ButtonComponent(action=MessageAction(label='التالي', text='لغز'), style='primary', color=C['primary'], height='md')
                        ]
                    )
                ]
            )
        )
    )

def ans_flex(a, t):
    title = "جواب" if "جواب" in t else "تلميح"
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='20px',
                contents=[
                    BoxComponent(layout='vertical', backgroundColor=C['card'], cornerRadius='14px', paddingAll='16px',
                        contents=[TextComponent(text=title, weight='bold', size='xl', color=C['text'], align='center')]),
                    BoxComponent(layout='vertical', margin='lg', paddingAll='20px', backgroundColor=C['card_inner'], cornerRadius='12px',
                        contents=[TextComponent(text=a, size='lg', color=C['text'], wrap=True, align='center')])
                ]
            )
        )
    )

rdl_st, gm_st = {}, {}
VALID_COMMANDS = {"سؤال","سوال","تحدي","اعتراف","منشن","موقف","لغز","اقتباس","تحليل","مساعدة","تلميح","جواب"}

def is_valid_command(txt):
    txt_lower = txt.lower().strip()
    if txt_lower in [cmd.lower() for cmd in VALID_COMMANDS]: return True
    if txt.strip().isdigit(): return True
    return False

def find_cmd(t):
    t = t.lower().strip()
    if t in ["سؤال","سوال"]: return "سؤال"
    if t == "تحدي": return "تحدي"
    if t == "اعتراف": return "اعتراف"
    if t == "منشن": return "منشن"
    if t == "موقف": return "موقف"
    if t == "لغز": return "لغز"
    if t == "اقتباس": return "اقتباس"
    if t == "تحليل": return "تحليل"
    return None

def reply(tk, msg):
    try:
        if isinstance(msg, TextSendMessage) and not msg.quick_reply:
            msg.quick_reply = menu()
        line.reply_message(tk, msg)
    except Exception as e:
        logging.error(f"Reply error: {e}")

@app.route("/", methods=["GET"])
def home(): return "Bot is running!", 200
@app.route("/health", methods=["GET"])
def health(): return {"status":"ok"}, 200
@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature","")
    body = request.get_data(as_text=True)
    try: handler.handle(body, sig)
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid = ev.source.user_id
    txt = ev.message.text.strip()
    tl = txt.lower()
    if not is_valid_command(txt): return
    try:
        if tl=="مساعدة": reply(ev.reply_token, help_flex()); return
        cmd = find_cmd(txt)
        if cmd:
            if cmd=="لغز": r=cm.get_r(); rdl_st[uid]=r; reply(ev.reply_token, puzzle_flex(r)); return
            if cmd=="اقتباس": q=cm.get_q(); reply(ev.reply_token, content_flex("اقتباس", f'"{q.get("text","")}"', "اقتباس")); return
            if cmd=="منشن": m=cm.get_m(); reply(ev.reply_token, content_flex("سؤال منشن", m, "منشن")); return
            if cmd=="موقف": s=cm.get_s(); reply(ev.reply_token, content_flex("موقف للنقاش", s, "موقف")); return
            c=cm.get(cmd); reply(ev.reply_token, content_flex(cmd, c, cmd)); return
        if tl in ["تلميح"]: reply(ev.reply_token, ans_flex(rdl_st[uid].get('hint','لا يوجد'), "تلميح")); return
        if tl in ["جواب"]: r=rdl_st.pop(uid); reply(ev.reply_token, ans_flex(r['answer'], "جواب")); return
    except Exception as e: logging.error(f"Error: {e}")

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
