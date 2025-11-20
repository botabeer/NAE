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

# ألوان لافندر ناعمة
C = {'bg':'#FEFCFF','glass':'#F5F0FA','card':'#FAF7FC','pri':'#B794F6','sec':'#D4B5F8','acc':'#9061F9',
     'txt':'#4A4063','txt2':'#9B8AA8','bdr':'#E8DFF0','ok':'#9061F9'}

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
        s.files = {"سؤال": s.ld_l("questions.txt"), "تحدي": s.ld_l("challenges.txt"), "اعتراف": s.ld_l("confessions.txt")}
        s.mention, s.situations, s.riddles = s.ld_l("more_questions.txt"), s.ld_l("situations.txt"), s.ld_j("riddles.json")
        s.quotes, s.results = s.ld_j("quotes.json"), s.ld_j("detailed_results.json")
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

cm = CM(); cm.init()

# ----------------- Quick Reply -----------------
def menu():
    items = ["سؤال","تحدي","اعتراف","موقف","منشن","اقتباسات","لغز","تحليل"]
    buttons = [QuickReplyButton(action=MessageAction(label=f"▫️{l}", text=l)) for l in items]
    return QuickReply(items=buttons)

# ----------------- Flex Components -----------------
def hdr(t, i=""):
    return BoxComponent(layout='vertical', backgroundColor=C['glass'], cornerRadius='16px', paddingAll='16px',
                        contents=[TextComponent(text=f"{i} {t}" if i else t, weight='bold', size='xl', color=C['txt'], align='center')])

def help_flex():
    sec = [("سؤال","أسئلة متنوعة"),("تحدي","تحديات ممتعة"),("اعتراف","اعترافات جريئة"),("موقف","مواقف للنقاش"),
           ("منشن","أسئلة منشن"),("اقتباسات","حكم واقتباسات"),("لغز","ألغاز وتلميحات"),("تحليل","تحليل الشخصية")]

    items = [
        BoxComponent(
            layout='horizontal', paddingAll='10px', backgroundColor=C['card'], cornerRadius='10px', spacing='md',
            contents=[
                TextComponent(text=f"▫️{i}", size='sm', color=C['acc'], flex=0),
                TextComponent(text=d, size='sm', color=C['txt2'], flex=1)
            ]
        )
        for i, d in sec
    ]

    return FlexSendMessage(
        alt_text="مساعدة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='20px',
                contents=[
                    hdr("بوت عناد المالكي"),
                    TextComponent(text="اختر من الأزرار أدناه", size='xs', color=C['txt2'], align='center', margin='md'),
                    SeparatorComponent(margin='lg', color=C['bdr']),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm', contents=items)
                ]
            )
        )
    )

def puzzle_flex(p):
    return FlexSendMessage(alt_text="لغز",
        contents=BubbleContainer(direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[hdr("لغز"),
                          BoxComponent(layout='vertical', margin='xl', paddingAll='24px', backgroundColor=C['card'], cornerRadius='16px',
                                       contents=[TextComponent(text=p['question'], size='xl', color=C['txt'], wrap=True, align='center', weight='bold')]),
                          BoxComponent(layout='vertical', margin='xl', spacing='md',
                                       contents=[ButtonComponent(action=MessageAction(label='لمح',text='لمح'), style='secondary', color=C['sec'], height='md'),
                                                 ButtonComponent(action=MessageAction(label='جاوب',text='جاوب'), style='primary', color=C['pri'], height='md')])])))

def ans_flex(a, t):
    i, cl = ("جاوب", C['ok']) if "جاوب" in t else ("لمح", C['sec'])
    return FlexSendMessage(alt_text=t,
        contents=BubbleContainer(direction='rtl',
            body=BoxComponent(layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[BoxComponent(layout='vertical', paddingAll='16px', backgroundColor=C['glass'], cornerRadius='16px',
                                       contents=[TextComponent(text=f"{i} {t}", weight='bold', size='xl', color=cl, align='center')]),
                          BoxComponent(layout='vertical', margin='xl', paddingAll='24px', backgroundColor=C['card'], cornerRadius='16px',
                                       contents=[TextComponent(text=a, size='xl', color=C['txt'], wrap=True, align='center', weight='bold')])])))

# ----------------- State & Commands -----------------
rdl_st, gm_st = {}, {}
CMDS = {"سؤال":["سؤال","سوال"], "تحدي":["تحدي"], "اعتراف":["اعتراف"], "منشن":["منشن"], "موقف":["موقف"], "لغز":["لغز"], "اقتباسات":["اقتباسات","اقتباس","حكمة"]}

def find_cmd(t):
    t = t.lower().strip()
    for k, v in CMDS.items():
        if t in [x.lower() for x in v]: return k
    return None

def calc_res(ans, gi):
    cnt = {"أ":0,"ب":0,"ج":0}
    for a in ans:
        if a in cnt: cnt[a]+=1
    mc = max(cnt, key=cnt.get)
    return cm.results.get(f"لعبة{gi+1}", {}).get(mc, "شخصيتك فريدة ومميزة!")

def reply(tk, msg):
    try:
        if isinstance(msg, TextSendMessage) and not msg.quick_reply: msg.quick_reply = menu()
        line.reply_message(tk, msg)
    except Exception as e: logging.error(f"Err:{e}")

# ----------------- Routes -----------------
@app.route("/", methods=["GET"])
def home(): return "OK", 200

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

# ----------------- Message Handling -----------------
@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid, txt = ev.source.user_id, ev.message.text.strip()
    tl = txt.lower()
    try:
        if tl=="مساعدة": reply(ev.reply_token, help_flex()); return

        cmd = find_cmd(txt)
        if cmd:
            if cmd=="لغز":
                r = cm.get_r()
                if r: rdl_st[uid] = r; reply(ev.reply_token, puzzle_flex(r))
                else: reply(ev.reply_token, TextSendMessage(text="لا توجد ألغاز متاحة"))
            elif cmd=="اقتباسات":
                q = cm.get_q()
                reply(ev.reply_token, TextSendMessage(text=f"اقتباس\n\n\"{q.get('text','')}\"\n\n— {q.get('author','مجهول')}") if q else TextSendMessage(text="لا توجد اقتباسات"))
            elif cmd=="منشن":
                q = cm.get_m()
                reply(ev.reply_token, TextSendMessage(text=f"سؤال منشن\n\n{q}") if q else TextSendMessage(text="لا توجد أسئلة"))
            elif cmd=="موقف":
                s = cm.get_s()
                reply(ev.reply_token, TextSendMessage(text=f"موقف للنقاش\n\n{s}") if s else TextSendMessage(text="لا توجد مواقف"))
            else:
                c = cm.get(cmd)
                reply(ev.reply_token, TextSendMessage(text=f"{cmd}\n\n{c}") if c else TextSendMessage(text=f"لا توجد بيانات"))
            return

        if tl=="لمح":
            if uid in rdl_st: reply(ev.reply_token, ans_flex(rdl_st[uid].get('hint','لا يوجد'),"لمح"))
            else: reply(ev.reply_token, TextSendMessage(text="اطلب لغز أولاً"))
            return
        if tl=="جاوب":
            if uid in rdl_st: r = rdl_st.pop(uid); reply(ev.reply_token, ans_flex(r['answer'], "جاوب"))
            else: reply(ev.reply_token, TextSendMessage(text="اطلب لغز أولاً"))
            return

        if tl in ["تحليل","تحليل شخصية","شخصية"]:
            if cm.games: reply(ev.reply_token, games_flex(cm.games))
            else: reply(ev.reply_token, TextSendMessage(text="لا توجد تحليلات متاحة"))
            return

        reply(ev.reply_token, TextSendMessage(text="اكتب 'مساعدة' لعرض الأوامر"))
    except Exception as e: logging.error(f"Err:{e}"); reply(ev.reply_token, TextSendMessage(text="حدث خطأ، حاول مرة أخرى"))

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
