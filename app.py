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

# ألوان داكنة ونصوص أسود
C = {
    'bg': '#0F0B1A',           # خلفية داكنة
    'glass': '#1A1525',        # زجاج داكن
    'card': '#251E35',         # كرت داكن
    'pri': '#A78BFA',          # بنفسجي فاتح
    'sec': '#7C3AED',          # بنفسجي متوسط
    'acc': '#C4B5FD',          # أكسنت فاتح
    'txt': '#000000',           # نص أسود
    'txt2': '#000000',          # نص ثانوي أسود
    'bdr': '#2D2440',          # حدود
    'ok': '#A78BFA'             # تأكيد
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

rdl_st, gm_st = {}, {}

# Quick Reply موحد
def menu():
    items = ["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل"]
    return QuickReply(
        items=[QuickReplyButton(action=MessageAction(label=f"▪️ {i}", text=i)) for i in items]
    )

# Flex للمحتوى
def content_flex(title, icon, content, cmd_type):
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
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[TextComponent(text=f"{icon} {title}", weight='bold', size='xl', color=C['txt'], align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        contents=[TextComponent(text=content, size='lg', color=C['txt'], wrap=True, align='center')]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=MessageAction(label=f"✨ {title} التالي", text=cmd_type),
                                style='primary',
                                color=C['pri'],
                                height='md'
                            )
                        ]
                    )
                ]
            )
        )
    )

# أمر مساعدة يظهر قائمة الأوامر فقط
def help_flex():
    return content_flex(
        "مساعدة",
        "📜",
        "▪️ سؤال\n▪️ منشن\n▪️ اعتراف\n▪️ تحدي\n▪️ موقف\n▪️ اقتباس\n▪️ لغز\n▪️ تحليل",
        "مساعدة"
    )

# أوامر اللغز
def puzzle_flex(p): return content_flex("لغز","🧩",p['question'],"لغز")
def ans_flex(a, t):
    title = "الجواب" if "جاوب" in t else "تلميح"
    icon = "✅" if "جاوب" in t else "💡"
    return content_flex(title, icon, a, t)

# Flex تحليل الشخصية
def games_flex(g):
    btns = [ButtonComponent(
        action=MessageAction(label=f"{i+1}. {x.get('title', f'تحليل {i+1}')}", text=str(i+1)),
        style='primary',
        color=C['pri'],
        height='md'
    ) for i, x in enumerate(g[:10])]
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
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[TextComponent(text="🧠 تحليل الشخصية", weight='bold', size='xl', color=C['txt'], align='center')]
                    ),
                    BoxComponent(layout='vertical', margin='xl', spacing='md', contents=btns)
                ]
            )
        )
    )

# التحقق من الأوامر
VALID_COMMANDS = {"سؤال","منشن","اعتراف","تحدي","موقف","اقتباس","لغز","تحليل","مساعدة","لمح","جاوب"}
def is_valid_command(txt):
    txt_lower = txt.lower().strip()
    if txt_lower in [cmd.lower() for cmd in VALID_COMMANDS]: return True
    if txt.strip().isdigit(): return True
    if txt_lower in ['1','2','3','a','b','c','أ','ب','ج']: return True
    return False
def find_cmd(t):
    mapping = {"سؤال":"سؤال","سوال":"سؤال","تحدي":"تحدي","اعتراف":"اعتراف","منشن":"منشن",
               "موقف":"موقف","لغز":"لغز","اقتباس":"اقتباس"}
    return mapping.get(t.strip().lower(), None)

# إرسال الرد
def reply(tk, msg):
    try:
        if isinstance(msg, TextSendMessage) and not msg.quick_reply:
            msg.quick_reply = menu()
        line.reply_message(tk, msg)
    except Exception as e:
        logging.error(f"Reply error: {e}")

# مسارات Flask
@app.route("/", methods=["GET"])
def home(): return "Bot is running!", 200
@app.route("/health", methods=["GET"])
def health(): return {"status":"ok"}, 200
@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature","")
    body = request.get_data(as_text=True)
    try: handler.handle(body,sig)
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

# معالجة الرسائل
@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid = ev.source.user_id
    txt = ev.message.text.strip()
    tl = txt.lower()
    if not is_valid_command(txt): return  # تجاهل الرسائل غير الأوامر
    try:
        if tl == "مساعدة": reply(ev.reply_token, help_flex()); return
        cmd = find_cmd(txt)
        if cmd:
            if cmd == "لغز":
                r = cm.get_r()
                if r: rdl_st[uid] = r; reply(ev.reply_token, puzzle_flex(r))
                return
            elif cmd == "اقتباس":
                q = cm.get_q()
                if q: reply(ev.reply_token, content_flex("اقتباس","📖",f'"{q.get("text","")}"\n\n— {q.get("author","مجهول")}',"اقتباس"))
                return
            elif cmd == "منشن":
                q = cm.get_m()
                if q: reply(ev.reply_token, content_flex("سؤال منشن","📱",q,"منشن"))
                return
            elif cmd == "موقف":
                s = cm.get_s()
                if s: reply(ev.reply_token, content_flex("موقف للنقاش","🤔",s,"موقف"))
                return
            else:
                c = cm.get(cmd)
                if c:
                    icons = {"سؤال":"💭","تحدي":"🎯","اعتراف":"💬"}
                    reply(ev.reply_token, content_flex(cmd,icons.get(cmd,""),c,cmd))
                return
        if tl == "لمح" and uid in rdl_st: reply(ev.reply_token, ans_flex(rdl_st[uid].get('hint','لا يوجد'),"لمح")); return
        if tl == "جاوب" and uid in rdl_st:
            r = rdl_st.pop(uid)
            reply(ev.reply_token, ans_flex(r['answer'],"جاوب"))
            return
        if tl in ["تحليل","تحليل شخصية","شخصية"] and cm.games: reply(ev.reply_token, games_flex(cm.games)); return
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
