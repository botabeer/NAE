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

# ألوان داكنة
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
    'text_muted': '#8C8CA3',
    'btn_secondary': '#1E1E27',
    'btn_secondary_text': '#FFFFFF'
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
        s.used = {k: [] for k in list(s.files.keys()) + ["منشن","لغز","اقتباس","موقف"]}

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

rdl_st, gm_st = {}, {}

VALID_COMMANDS = {
    "سؤال","سوال","تحدي","اعتراف","منشن","موقف","لغز","اقتباس","تحليل","تحليل شخصية","شخصية","مساعدة","لمح","جاوب"
}

def is_valid_command(txt):
    txt_lower = txt.lower().strip()
    if txt_lower in [cmd.lower() for cmd in VALID_COMMANDS]: return True
    if txt.strip().isdigit(): return True
    if txt_lower in ['1','2','3','أ','ب','ج','a','b','c']: return True
    return False

def find_cmd(t):
    t = t.lower().strip()
    if t in ["سؤال","سوال"]: return "سؤال"
    elif t=="تحدي": return "تحدي"
    elif t=="اعتراف": return "اعتراف"
    elif t=="منشن": return "منشن"
    elif t=="موقف": return "موقف"
    elif t=="لغز": return "لغز"
    elif t in ["اقتباس","حكمة"]: return "اقتباس"
    return None

def calc_res(ans, gi):
    cnt={"أ":0,"ب":0,"ج":0}
    for a in ans:
        if a in cnt: cnt[a]+=1
    mc=max(cnt,key=cnt.get)
    return cm.results.get(f"لعبة{gi+1}",{}).get(mc,"شخصيتك فريدة ومميزة!")

# Quick Reply موحد لكل الرسائل
def menu():
    items=[("سؤال","سؤال"),("منشن","منشن"),("اعتراف","اعتراف"),
           ("تحدي","تحدي"),("موقف","موقف"),("اقتباس","اقتباس"),
           ("لغز","لغز"),("تحليل","تحليل")]
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=l,text=t)) for l,t in items])

def help_flex():
    texts=["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل"]
    return FlexSendMessage(
        alt_text="مساعدة البوت",
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
                        contents=[TextComponent(text="▪️ "+ "   ".join(texts),size='md',weight='bold',color=C['text'],align='center')]
                    )
                ]
            )
        )
    )

# Flex النصوص العادية
def content_flex(title, content):
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
                    )
                ]
            )
        )
    )

# لغز
def puzzle_flex(p):
    return FlexSendMessage(
        alt_text="لغز",
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
                        contents=[TextComponent(text="▪️ لغز",size='lg',weight='bold',color=C['text'],align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='16px',
                        backgroundColor=C['card_inner'],
                        cornerRadius='12px',
                        contents=[TextComponent(text=p['question'],size='md',color=C['text'],wrap=True,align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            ButtonComponent(action=MessageAction(label="تلميح",text="لمح"),style='secondary',color=C['btn_secondary'],height='md'),
                            ButtonComponent(action=MessageAction(label="الجواب",text="جاوب"),style='primary',color=C['primary'],height='md')
                        ]
                    )
                ]
            )
        )
    )

# تحليل
def games_flex(g):
    btns=[]
    for i,x in enumerate(g[:10],1):
        btns.append(ButtonComponent(
            action=MessageAction(label=f"{i}. {x.get('title','تحليل')}",text=str(i)),
            style='primary',
            color=C['primary'],
            height='md'
        ))
    return FlexSendMessage(
        alt_text="تحليل الشخصية",
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
                        contents=[TextComponent(text="▪️ تحليل الشخصية",weight='bold',size='xl',color=C['text'],align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=btns
                    )
                ]
            )
        )
    )

def reply(tk,msg):
    try:
        if isinstance(msg, TextSendMessage) and not msg.quick_reply: msg.quick_reply=menu()
        line.reply_message(tk,msg)
    except Exception as e:
        logging.error(f"Reply error: {e}")

@app.route("/", methods=["GET"])
def home(): return "Bot is running!",200

@app.route("/callback", methods=["POST"])
def callback():
    sig=request.headers.get("X-Line-Signature","")
    body=request.get_data(as_text=True)
    try: handler.handle(body,sig)
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid=ev.source.user_id
    txt=ev.message.text.strip()
    tl=txt.lower()
    if not is_valid_command(txt): return
    
    try:
        if tl=="مساعدة":
            reply(ev.reply_token,help_flex())
            return
        cmd=find_cmd(txt)
        if cmd:
            if cmd=="لغز":
                r=cm.get_r()
                if r: rdl_st[uid]=r; reply(ev.reply_token,puzzle_flex(r))
                return
            elif cmd=="اقتباس":
                q=cm.get_q()
                if q: reply(ev.reply_token,content_flex("اقتباس",f'{q.get("text","")}'))
                return
            elif cmd=="منشن":
                q=cm.get_m()
                if q: reply(ev.reply_token,content_flex("منشن",q))
                return
            elif cmd=="موقف":
                s=cm.get_s()
                if s: reply(ev.reply_token,content_flex("موقف",s))
                return
            else:
                c=cm.get(cmd)
                if c: reply(ev.reply_token,content_flex(cmd,c))
                return
        if tl=="لمح" and uid in rdl_st: reply(ev.reply_token,content_flex("تلميح",rdl_st[uid].get('hint','لا يوجد')))
        if tl=="جاوب" and uid in rdl_st: r=rdl_st.pop(uid); reply(ev.reply_token,content_flex("الجواب",r['answer']))
        if tl in ["تحليل","تحليل شخصية","شخصية"] and cm.games: reply(ev.reply_token,games_flex(cm.games))
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
