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

# =======================
# ألوان داكنة
# =======================
C = {
    'bg': '#0a0a0c',
    'card': '#13131a',
    'card_inner': '#1a1a22',
    'primary': '#9C6BFF',
    'primary_light': '#C7A3FF',
    'accent': '#A67CFF',
    'border': '#B58CFF',
    'text': '#FFFFFF',
    'text_dim': '#BFBFD9',
    'btn_secondary': '#1E1E27',
    'btn_secondary_text': '#FFFFFF'
}

# =======================
# إدارة الملفات والمحتوى
# =======================
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

    def ld_l(s,f):
        try: return [l.strip() for l in open(f,'r',encoding='utf-8') if l.strip()]
        except: return []

    def ld_j(s,f):
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
        s.used = {k: [] for k in list(s.files.keys()) + ["منشن","لغز","اقتباس","موقف"]}

    def rnd(s,k,mx):
        if mx==0: return 0
        if len(s.used.get(k,[]))>=mx: s.used[k]=[]
        av=[i for i in range(mx) if i not in s.used.get(k,[])]
        idx=random.choice(av) if av else random.randint(0,mx-1)
        if k not in s.used: s.used[k]=[]
        s.used[k].append(idx)
        return idx

    def get(s,c):
        l=s.files.get(c,[])
        return l[s.rnd(c,len(l))] if l else None

    def get_m(s): return s.mention[s.rnd("منشن",len(s.mention))] if s.mention else None
    def get_s(s): return s.situations[s.rnd("موقف",len(s.situations))] if s.situations else None
    def get_r(s): return s.riddles[s.rnd("لغز",len(s.riddles))] if s.riddles else None
    def get_q(s): return s.quotes[s.rnd("اقتباس",len(s.quotes))] if s.quotes else None

cm = CM()
cm.init()

# =======================
# حالة الجلسات
# =======================
rdl_st, gm_st = {}, {}

# =======================
# الأوامر
# =======================
VALID_COMMANDS = {"سؤال","تحدي","اعتراف","منشن","موقف","اقتباس","لغز","تحليل","مساعدة","لمح","جاوب"}

def is_valid_command(txt):
    txt_lower=txt.lower().strip()
    if txt_lower in [cmd.lower() for cmd in VALID_COMMANDS]: return True
    if txt.strip().isdigit(): return True
    return False

def find_cmd(t):
    t=t.lower().strip()
    if t=="سؤال": return "سؤال"
    if t=="تحدي": return "تحدي"
    if t=="اعتراف": return "اعتراف"
    if t=="منشن": return "منشن"
    if t=="موقف": return "موقف"
    if t=="لغز": return "لغز"
    if t=="اقتباس": return "اقتباس"
    return None

def calc_res(ans,gi):
    cnt={"أ":0,"ب":0,"ج":0}
    for a in ans:
        if a in cnt: cnt[a]+=1
    mc=max(cnt,key=cnt.get)
    return cm.results.get(f"لعبة{gi+1}",{}).get(mc,"شخصيتك فريدة ومميزة!")

def reply(tk,msg):
    try:
        if isinstance(msg,TextSendMessage) and not msg.quick_reply: msg.quick_reply=menu()
        line.reply_message(tk,msg)
    except Exception as e:
        logging.error(f"Reply error: {e}")

# =======================
# أزرار ثابتة
# =======================
def menu():
    items = ["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل"]
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=f"▪️ {i}", text=i)) for i in items])

# =======================
# نافذة محتوى Flex
# =======================
def content_flex(title, content, cmd_type=None):
    btns=[]
    if cmd_type:
        btns.append(
            ButtonComponent(
                action=MessageAction(label=f"▪️ {title} التالي", text=cmd_type),
                style='primary',
                color=C['primary'],
                height='md'
            )
        )
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
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[TextComponent(text=f"▪️ {title}",size='lg',weight='bold',color=C['text'],align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='16px',
                        backgroundColor=C['card_inner'],
                        cornerRadius='12px',
                        contents=[TextComponent(text=content,size='md',color=C['text'],wrap=True,align='center')]
                    ),
                    *btns
                ]
            )
        )
    )

# =======================
# Flex لغز
# =======================
def puzzle_flex(p):
    return content_flex("لغز", p['question'], "لغز")

# =======================
# Flex تحليل
# =======================
def games_flex(g):
    btns=[]
    for i,x in enumerate(g[:10],1):
        btns.append(ButtonComponent(
            action=MessageAction(label=f"▪️ {i}. {x.get('title','تحليل')}", text=str(i)),
            style='primary', color=C['primary'], height='md'))
    return FlexSendMessage(
        alt_text="تحليل الشخصية",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='24px', contents=[
                BoxComponent(layout='vertical', backgroundColor=C['card'], cornerRadius='16px', paddingAll='16px',
                             contents=[TextComponent(text="▪️ تحليل الشخصية", size='lg', weight='bold', color=C['text'], align='center')]),
                BoxComponent(layout='vertical', margin='xl', spacing='md', contents=btns)
            ])
        )
    )

# =======================
# ROUTES
# =======================
@app.route("/", methods=["GET"])
def home(): return "Bot is running!",200
@app.route("/health", methods=["GET"])
def health(): return {"status":"ok"},200

@app.route("/callback", methods=["POST"])
def callback():
    sig=request.headers.get("X-Line-Signature","")
    body=request.get_data(as_text=True)
    try: handler.handle(body,sig)
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

# =======================
# HANDLER
# =======================
@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid=ev.source.user_id
    txt=ev.message.text.strip()
    tl=txt.lower()
    if not is_valid_command(txt): return

    try:
        if tl=="مساعدة": reply(ev.reply_token, content_flex("مساعدة","▪️ "+"\n▪️ ".join(["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل"])))
        else:
            cmd=find_cmd(txt)
            if cmd:
                if cmd=="لغز":
                    r=cm.get_r()
                    if r: rdl_st[uid]=r; reply(ev.reply_token,puzzle_flex(r))
                    return
                elif cmd=="اقتباس":
                    q=cm.get_q()
                    if q: reply(ev.reply_token, content_flex("اقتباس", q.get("text",""), "اقتباس"))
                    return
                elif cmd=="منشن":
                    q=cm.get_m()
                    if q: reply(ev.reply_token, content_flex("منشن", q, "منشن"))
                    return
                elif cmd=="موقف":
                    s=cm.get_s()
                    if s: reply(ev.reply_token, content_flex("موقف", s, "موقف"))
                    return
                else:
                    c=cm.get(cmd)
                    if c: reply(ev.reply_token, content_flex(cmd,c,cmd))
                    return
            if tl=="لمح" and uid in rdl_st: reply(ev.reply_token, content_flex("تلميح", rdl_st[uid].get('hint','لا يوجد')))
            if tl=="جاوب" and uid in rdl_st: r=rdl_st.pop(uid); reply(ev.reply_token, content_flex("الجواب", r['answer']))
            if tl in ["تحليل","شخصية"]:
                if cm.games: reply(ev.reply_token,games_flex(cm.games))
                return
    except Exception as e: logging.error(f"Error: {e}")

# =======================
# RUN
# =======================
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
