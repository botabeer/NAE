import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage,
    FlexBubble, FlexBox, FlexText,
    FlexSeparator, FlexButton, MessageAction,
    QuickReply, QuickReplyItem
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# إعدادات LINE Bot
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ألوان لافندر ناعمة
C = {
    'bg': '#FEFCFF', 'glass': '#F5F0FA', 'card': '#FAF7FC',
    'pri': '#B794F6', 'sec': '#D4B5F8', 'acc': '#9061F9',
    'txt': '#4A4063', 'txt2': '#9B8AA8', 'bdr': '#E8DFF0', 'ok': '#9061F9'
}

class CM:
    def __init__(self):
        self.files = {}
        self.mention = []
        self.riddles = []
        self.games = []
        self.quotes = []
        self.situations = []
        self.results = {}
        self.used = {}

    def ld_l(self, f):
        if not os.path.exists(f):
            return []
        try:
            return [l.strip() for l in open(f, 'r', encoding='utf-8') if l.strip()]
        except:
            return []

    def ld_j(self, f):
        if not os.path.exists(f):
            return [] if 's.json' in f else {}
        try:
            return json.load(open(f, 'r', encoding='utf-8'))
        except:
            return [] if 's.json' in f else {}

    def init(self):
        self.files = {
            "سؤال": self.ld_l("questions.txt"),
            "تحدي": self.ld_l("challenges.txt"),
            "اعتراف": self.ld_l("confessions.txt")
        }
        self.mention = self.ld_l("more_questions.txt")
        self.situations = self.ld_l("situations.txt")
        self.riddles = self.ld_j("riddles.json")
        self.quotes = self.ld_j("quotes.json")
        self.results = self.ld_j("detailed_results.json")
        d = self.ld_j("personality_games.json")
        self.games = [d[k] for k in sorted(d.keys())] if isinstance(d, dict) else []
        self.used = {k: [] for k in list(self.files.keys()) + ["منشن", "لغز", "اقتباس", "موقف"]}

    def rnd(self, k, mx):
        if mx == 0:
            return 0
        if len(self.used.get(k, [])) >= mx:
            self.used[k] = []
        av = [i for i in range(mx) if i not in self.used.get(k, [])]
        idx = random.choice(av) if av else random.randint(0, mx - 1)
        if k not in self.used:
            self.used[k] = []
        self.used[k].append(idx)
        return idx

    def get(self, c):
        l = self.files.get(c, [])
        return l[self.rnd(c, len(l))] if l else None

    def get_m(self):
        return self.mention[self.rnd("منشن", len(self.mention))] if self.mention else None

    def get_s(self):
        return self.situations[self.rnd("موقف", len(self.situations))] if self.situations else None

    def get_r(self):
        return self.riddles[self.rnd("لغز", len(self.riddles))] if self.riddles else None

    def get_q(self):
        return self.quotes[self.rnd("اقتباس", len(self.quotes))] if self.quotes else None

cm = CM()
cm.init()
rdl_st, gm_st = {}, {}

# دوال إنشاء الرسائل
def menu():
    items = [
        ("سؤال", "سؤال"), ("منشن", "منشن"), ("اعتراف", "اعتراف"),
        ("تحدي", "تحدي"), ("موقف", "موقف"), ("اقتباسات", "اقتباسات"),
        ("لغز", "لغز"), ("تحليل", "تحليل")
    ]
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=l, text=t)) for l, t in items
    ])

def hdr(t, i=""):
    return FlexBox(
        layout='vertical', background_color=C['glass'], corner_radius='16px',
        padding_all='16px',
        contents=[FlexText(
            text=f"{i} {t}" if i else t,
            weight='bold', size='xl', color=C['txt'], align='center'
        )]
    )

def help_flex():
    cmds = ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]
    items = [FlexText(text=f"• {c}", size='md', color=C['txt'], margin='sm') for c in cmds]
    
    return FlexMessage(
        alt_text="مساعدة",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='20px',
                contents=[
                    hdr("بوت عناد المالكي"),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexText(text="أوامر البوت:", weight='bold', size='lg', color=C['acc'], margin='lg'),
                    FlexBox(layout='vertical', margin='md', spacing='xs', contents=items),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexBox(
                        layout='vertical', margin='md', padding_all='12px',
                        background_color=C['glass'], corner_radius='8px',
                        contents=[FlexText(
                            text="ملاحظة: تقدر تستخدم البوت بالخاص والقروبات",
                            size='sm', color=C['txt2'], wrap=True, align='center'
                        )]
                    ),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexText(
                        text="تم إنشاء هذا البوت بواسطة عبير الدوسري 2025",
                        size='xxs', color=C['txt2'], align='center', margin='md'
                    )
                ]
            )
        )
    )

def puzzle_flex(p):
    return FlexMessage(
        alt_text="لغز",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='24px',
                contents=[
                    hdr("لغز"),
                    FlexBox(
                        layout='vertical', margin='xl', padding_all='24px',
                        background_color=C['card'], corner_radius='16px',
                        contents=[FlexText(
                            text=p['question'], size='xl', color=C['txt'],
                            wrap=True, align='center', weight='bold'
                        )]
                    ),
                    FlexBox(
                        layout='vertical', margin='xl', spacing='md',
                        contents=[
                            FlexButton(
                                action=MessageAction(label='لمح', text='لمح'),
                                style='secondary', color=C['sec'], height='md'
                            ),
                            FlexButton(
                                action=MessageAction(label='جاوب', text='جاوب'),
                                style='primary', color=C['pri'], height='md'
                            )
                        ]
                    )
                ]
            )
        )
    )

def games_flex(g):
    btns = [
        FlexButton(
            action=MessageAction(label=f"{i}. {x.get('title', f'تحليل {i}')}", text=str(i)),
            style='secondary', color=C['pri'], height='sm'
        ) for i, x in enumerate(g[:10], 1)
    ]
    
    return FlexMessage(
        alt_text="تحليل الشخصية",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='24px',
                contents=[
                    hdr("تحليل الشخصية"),
                    FlexBox(layout='vertical', margin='xl', spacing='sm', contents=btns)
                ]
            )
        )
    )

def ans_flex(a, t):
    i, cl = ("جاوب", C['ok']) if "جاوب" in t else ("لمح", C['sec'])
    
    return FlexMessage(
        alt_text=t,
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='24px',
                contents=[
                    FlexBox(
                        layout='vertical', padding_all='16px',
                        background_color=C['glass'], corner_radius='16px',
                        contents=[FlexText(
                            text=i, weight='bold', size='xl',
                            color=cl, align='center'
                        )]
                    ),
                    FlexBox(
                        layout='vertical', margin='xl', padding_all='24px',
                        background_color=C['card'], corner_radius='16px',
                        contents=[FlexText(
                            text=a, size='xl', color=C['txt'],
                            wrap=True, align='center', weight='bold'
                        )]
                    )
                ]
            )
        )
    )

def gq_flex(t, q, p):
    btns = [
        FlexButton(
            action=MessageAction(label=f"{k}. {v}", text=k),
            style='secondary', color=C['pri'], height='sm'
        ) for k, v in q['options'].items()
    ]
    
    return FlexMessage(
        alt_text=t,
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='20px',
                contents=[
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text=t, weight='bold', size='lg', color=C['acc'], flex=1),
                            FlexText(text=p, size='xs', color=C['txt2'], flex=0, align='end')
                        ]
                    ),
                    FlexSeparator(margin='md', color=C['bdr']),
                    FlexBox(
                        layout='vertical', margin='lg', padding_all='16px',
                        background_color=C['glass'], corner_radius='8px',
                        contents=[FlexText(
                            text=q['question'], size='md',
                            color=C['txt'], wrap=True
                        )]
                    ),
                    FlexBox(layout='vertical', margin='lg', spacing='sm', contents=btns)
                ]
            )
        )
    )

def calc_res(ans, gi):
    cnt = {"أ": 0, "ب": 0, "ج": 0}
    for a in ans:
        if a in cnt:
            cnt[a] += 1
    mc = max(cnt, key=cnt.get)
    return cm.results.get(f"لعبة{gi + 1}", {}).get(mc, "شخصيتك فريدة ومميزة")

def gr_flex(r):
    return FlexMessage(
        alt_text="النتيجة",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical', background_color=C['bg'], padding_all='20px',
                contents=[
                    FlexText(
                        text='نتيجة التحليل', weight='bold',
                        size='xl', color=C['acc'], align='center'
                    ),
                    FlexSeparator(margin='md', color=C['bdr']),
                    FlexBox(
                        layout='vertical', margin='lg', padding_all='16px',
                        background_color=C['glass'], corner_radius='8px',
                        contents=[FlexText(
                            text=r, size='md', color=C['txt'],
                            wrap=True, line_spacing='6px'
                        )]
                    ),
                    FlexBox(
                        layout='vertical', margin='xl',
                        contents=[FlexButton(
                            action=MessageAction(label='تحليل جديد', text='تحليل'),
                            style='primary', color=C['pri'], height='sm'
                        )]
                    )
                ]
            )
        )
    )

# أوامر البوت
CMDS = {
    "سؤال": ["سؤال", "سوال"],
    "تحدي": ["تحدي"],
    "اعتراف": ["اعتراف"],
    "منشن": ["منشن"],
    "موقف": ["موقف"],
    "لغز": ["لغز"],
    "اقتباسات": ["اقتباسات", "اقتباس", "حكمة"]
}

def find_cmd(t):
    t = t.lower().strip()
    for k, v in CMDS.items():
        if t in [x.lower() for x in v]:
            return k
    return None

def reply(tk, msgs):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=tk, messages=msgs)
            )
    except Exception as e:
        logging.error(f"خطأ في الرد: {e}")

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        logging.error(f"خطأ في المعالج: {e}")
        abort(500)
    
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_msg(event):
    uid = event.source.user_id
    txt = event.message.text.strip()
    tl = txt.lower()
    
    try:
        if tl == "مساعدة":
            reply(event.reply_token, [
                help_flex(),
                TextMessage(text="اختر من الأزرار:", quick_reply=menu())
            ])
            return
        
        cmd = find_cmd(txt)
        if cmd:
            if cmd == "لغز":
                r = cm.get_r()
                if r:
                    rdl_st[uid] = r
                    reply(event.reply_token, [puzzle_flex(r)])
                else:
                    reply(event.reply_token, [TextMessage(text="لا توجد ألغاز متاحة")])
            elif cmd == "اقتباسات":
                q = cm.get_q()
                if q:
                    reply(event.reply_token, [
                        TextMessage(text=f"اقتباس\n\n\"{q.get('text', '')}\"\n\n— {q.get('author', 'مجهول')}")
                    ])
                else:
                    reply(event.reply_token, [TextMessage(text="لا توجد اقتباسات")])
            elif cmd == "منشن":
                q = cm.get_m()
                if q:
                    reply(event.reply_token, [TextMessage(text=f"سؤال منشن\n\n{q}")])
                else:
                    reply(event.reply_token, [TextMessage(text="لا توجد أسئلة")])
            elif cmd == "موقف":
                s = cm.get_s()
                if s:
                    reply(event.reply_token, [TextMessage(text=f"موقف للنقاش\n\n{s}")])
                else:
                    reply(event.reply_token, [TextMessage(text="لا توجد مواقف")])
            else:
                c = cm.get(cmd)
                if c:
                    reply(event.reply_token, [TextMessage(text=f"{cmd}\n\n{c}")])
                else:
                    reply(event.reply_token, [TextMessage(text="لا توجد بيانات")])
            return
        
        if tl == "لمح":
            if uid in rdl_st:
                reply(event.reply_token, [ans_flex(rdl_st[uid].get('hint', 'لا يوجد'), "لمح")])
            return
        
        if tl == "جاوب":
            if uid in rdl_st:
                r = rdl_st.pop(uid)
                reply(event.reply_token, [ans_flex(r['answer'], "جاوب")])
            return
        
        if tl in ["تحليل", "تحليل شخصية", "شخصية"]:
            if cm.games:
                reply(event.reply_token, [games_flex(cm.games)])
            else:
                reply(event.reply_token, [TextMessage(text="لا توجد تحليلات متاحة")])
            return
        
        if txt.isdigit() and uid not in gm_st and 1 <= int(txt) <= len(cm.games):
            gi = int(txt) - 1
            gm_st[uid] = {"gi": gi, "qi": 0, "ans": []}
            g = cm.games[gi]
            reply(event.reply_token, [
                gq_flex(g.get('title', f'تحليل {int(txt)}'), g["questions"][0], f"1/{len(g['questions'])}")
            ])
            return
        
        if uid in gm_st:
            st = gm_st[uid]
            amap = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج", "أ": "أ", "ب": "ب", "ج": "ج"}
            ans = amap.get(tl, None)
            
            if ans:
                st["ans"].append(ans)
                g = cm.games[st["gi"]]
                st["qi"] += 1
                
                if st["qi"] < len(g["questions"]):
                    reply(event.reply_token, [
                        gq_flex(g.get('title', 'تحليل'), g["questions"][st["qi"]], f"{st['qi'] + 1}/{len(g['questions'])}")
                    ])
                else:
                    reply(event.reply_token, [gr_flex(calc_res(st["ans"], st["gi"]))])
                    del gm_st[uid]
                return
    
    except Exception as e:
        logging.error(f"خطأ: {e}")
        reply(event.reply_token, [TextMessage(text="حدث خطأ، حاول مرة أخرى")])

# Keep Alive
def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG")
    if url and not url.startswith("http"):
        url = f"https://{url}.onrender.com"
    
    while True:
        try:
            if url:
                requests.get(f"{url}/health", timeout=5)
            time.sleep(840)
        except:
            pass

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG"):
        threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
