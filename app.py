import json, os, logging, random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
app = Flask(__name__)

TOKEN, SECRET = os.getenv("LINE_CHANNEL_ACCESS_TOKEN"), os.getenv("LINE_CHANNEL_SECRET")
if not TOKEN or not SECRET: raise RuntimeError("Set LINE tokens")

line, handler = LineBotApi(TOKEN), WebhookHandler(SECRET)

# ألوان لافندر ناعمة
C = {'bg':'#FEFCFF','glass':'#F5F0FA','card':'#FAF7FC','pri':'#B794F6','sec':'#D4B5F8','acc':'#9061F9',
     'txt':'#4A4063','txt2':'#9B8AA8','bdr':'#E8DFF0','ok':'#9061F9'}

class CM:
    def __init__(s):
        s.files, s.mention, s.riddles, s.games, s.quotes, s.situations, s.results, s.used = {}, [], [], [], [], [], {}, {}

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
rdl_st, gm_st = {}, {}

CMDS = {"سؤال":["سؤال","سوال"], "تحدي":["تحدي"], "اعتراف":["اعتراف"], "منشن":["منشن"], 
        "موقف":["موقف"], "لغز":["لغز"], "اقتباسات":["اقتباسات","اقتباس","حكمة"]}

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

def menu():
    items = ["سؤال","تحدي","اعتراف","موقف","منشن","اقتباسات","لغز","تحليل"]
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=f"✦ {l}", text=l)) for l in items])

def hdr(t, i=""):
    return BoxComponent(
        layout='vertical', backgroundColor=C['glass'], cornerRadius='18px', paddingAll='16px',
        contents=[
            TextComponent(text=f"{i} {t}" if i else t, weight='bold', size='xl', color=C['txt'], align='center'),
            BoxComponent(layout='vertical', height='3px', backgroundColor=C['pri'], cornerRadius='2px', margin='md')
        ]
    )

def help_flex():
    sec = [("سؤال","أسئلة متنوعة","❓"),("تحدي","تحديات ممتعة","🎯"),("اعتراف","اعترافات جريئة","💭"),
           ("موقف","مواقف للنقاش","🤔"),("منشن","أسئلة منشن","👥"),("اقتباسات","حكم واقتباسات","📖"),
           ("لغز","ألغاز وتلميحات","🧩"),("تحليل","تحليل الشخصية","🔮")]

    items = [
        BoxComponent(
            layout='horizontal', paddingAll='12px', backgroundColor=C['card'], cornerRadius='14px', spacing='md', margin='sm',
            contents=[
                TextComponent(text=ic, size='xl', color=C['acc'], flex=0),
                BoxComponent(layout='vertical', flex=1, spacing='xs', contents=[
                    TextComponent(text=i, size='md', color=C['txt'], weight='bold'),
                    TextComponent(text=d, size='xs', color=C['txt2'], wrap=True)
                ])
            ]
        )
        for i, d, ic in sec
    ]

    return FlexSendMessage(
        alt_text="مساعدة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr("بوت عناد المالكي", "🤖"),
                    TextComponent(text="اختر من الأزرار أدناه", size='xs', color=C['txt2'], align='center', margin='md'),
                    SeparatorComponent(margin='lg', color=C['bdr']),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm', contents=items)
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
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr("لغز", "🧩"),
                    BoxComponent(
                        layout='vertical', margin='xl', paddingAll='24px', backgroundColor=C['card'], 
                        cornerRadius='18px',
                        contents=[TextComponent(text=p['question'], size='lg', color=C['txt'], wrap=True, align='center', weight='bold')]
                    ),
                    BoxComponent(
                        layout='vertical', margin='xl', spacing='md',
                        contents=[
                            ButtonComponent(action=MessageAction(label='💡 تلميح',text='لمح'), style='secondary', color=C['sec'], height='md'),
                            ButtonComponent(action=MessageAction(label='✓ الجواب',text='جاوب'), style='primary', color=C['pri'], height='md')
                        ]
                    )
                ]
            )
        )
    )

def ans_flex(a, t):
    is_ans = "جاوب" in t
    ic = "✓" if is_ans else "💡"
    title = "الجواب" if is_ans else "تلميح"
    cl = C['ok'] if is_ans else C['sec']
    
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    BoxComponent(
                        layout='vertical', paddingAll='16px', backgroundColor=C['glass'], cornerRadius='18px',
                        contents=[TextComponent(text=f"{ic} {title}", weight='bold', size='xl', color=cl, align='center')]
                    ),
                    BoxComponent(
                        layout='vertical', margin='xl', paddingAll='24px', backgroundColor=C['card'], cornerRadius='18px',
                        contents=[TextComponent(text=a, size='lg', color=C['txt'], wrap=True, align='center', weight='bold')]
                    )
                ]
            )
        )
    )

def games_flex(games):
    items = [
        BoxComponent(
            layout='horizontal', paddingAll='14px', backgroundColor=C['card'], cornerRadius='14px', 
            spacing='md', margin='sm',
            contents=[
                TextComponent(text=f"{i+1}", size='xl', color=C['pri'], flex=0, weight='bold'),
                TextComponent(text=g['title'], size='md', color=C['txt'], flex=1, weight='bold'),
                ButtonComponent(
                    action=MessageAction(label='ابدأ', text=f"لعبة {i+1}"),
                    style='primary', color=C['acc'], height='sm', flex=0
                )
            ]
        )
        for i, g in enumerate(games)
    ]
    
    return FlexSendMessage(
        alt_text="تحليل الشخصية",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr("تحليل الشخصية", "🔮"),
                    TextComponent(text="اختر لعبة لتحليل شخصيتك", size='xs', color=C['txt2'], align='center', margin='md'),
                    SeparatorComponent(margin='lg', color=C['bdr']),
                    BoxComponent(layout='vertical', margin='lg', spacing='sm', contents=items)
                ]
            )
        )
    )

def game_q_flex(game, qi, total):
    q = game['questions'][qi]
    opts = [
        ButtonComponent(
            action=MessageAction(label=f"أ. {q['options']['أ']}", text=f"اختار أ"),
            style='secondary', color=C['card'], height='md', margin='sm'
        ),
        ButtonComponent(
            action=MessageAction(label=f"ب. {q['options']['ب']}", text=f"اختار ب"),
            style='secondary', color=C['card'], height='md', margin='sm'
        ),
        ButtonComponent(
            action=MessageAction(label=f"ج. {q['options']['ج']}", text=f"اختار ج"),
            style='secondary', color=C['card'], height='md', margin='sm'
        )
    ]
    
    return FlexSendMessage(
        alt_text=f"سؤال {qi+1}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    BoxComponent(
                        layout='horizontal', paddingAll='12px', backgroundColor=C['glass'], cornerRadius='12px',
                        contents=[
                            TextComponent(text=f"سؤال {qi+1} من {total}", weight='bold', size='md', color=C['txt'], flex=1),
                            TextComponent(text=game['title'], size='sm', color=C['txt2'], flex=1, align='end')
                        ]
                    ),
                    BoxComponent(
                        layout='vertical', margin='xl', paddingAll='20px', backgroundColor=C['card'], cornerRadius='16px',
                        contents=[TextComponent(text=q['question'], size='lg', color=C['txt'], wrap=True, weight='bold')]
                    ),
                    BoxComponent(layout='vertical', margin='xl', spacing='sm', contents=opts)
                ]
            )
        )
    )

def result_flex(result, title):
    return FlexSendMessage(
        alt_text="نتيجة التحليل",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical', backgroundColor=C['bg'], paddingAll='24px',
                contents=[
                    hdr("نتيجة التحليل", "✨"),
                    TextComponent(text=title, size='md', color=C['pri'], align='center', margin='md', weight='bold'),
                    SeparatorComponent(margin='lg', color=C['bdr']),
                    BoxComponent(
                        layout='vertical', margin='xl', paddingAll='24px', backgroundColor=C['card'], cornerRadius='18px',
                        contents=[TextComponent(text=result, size='md', color=C['txt'], wrap=True, lineHeight='1.8')]
                    )
                ]
            )
        )
    )

def reply(tk, msg):
    try:
        if isinstance(msg, list):
            if isinstance(msg[-1], TextSendMessage): msg[-1].quick_reply = menu()
            line.reply_message(tk, msg)
        else:
            if isinstance(msg, FlexSendMessage):
                line.reply_message(tk, [msg, TextSendMessage(text="✦", quick_reply=menu())])
            else:
                if isinstance(msg, TextSendMessage): msg.quick_reply = menu()
                line.reply_message(tk, msg)
    except Exception as e: logging.error(f"Err:{e}")

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

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid, txt = ev.source.user_id, ev.message.text.strip()
    tl = txt.lower()
    
    try:
        # مساعدة
        if tl == "مساعدة":
            reply(ev.reply_token, help_flex())
            return

        # تحقق من اللعبة النشطة
        if uid in gm_st:
            if tl.startswith("اختار "):
                choice = tl.split()[-1]
                if choice in ["أ", "ب", "ج"]:
                    gm_st[uid]['answers'].append(choice)
                    qi = len(gm_st[uid]['answers'])
                    game = gm_st[uid]['game']
                    
                    if qi < len(game['questions']):
                        reply(ev.reply_token, game_q_flex(game, qi, len(game['questions'])))
                    else:
                        result = calc_res(gm_st[uid]['answers'], gm_st[uid]['game_idx'])
                        reply(ev.reply_token, result_flex(result, game['title']))
                        del gm_st[uid]
                return
            elif tl == "إلغاء":
                del gm_st[uid]
                reply(ev.reply_token, TextSendMessage(text="تم إلغاء اللعبة"))
                return

        # لعبة جديدة
        if tl.startswith("لعبة "):
            try:
                gi = int(tl.split()[-1]) - 1
                if 0 <= gi < len(cm.games):
                    gm_st[uid] = {'game': cm.games[gi], 'game_idx': gi, 'answers': []}
                    reply(ev.reply_token, game_q_flex(cm.games[gi], 0, len(cm.games[gi]['questions'])))
                return
            except: pass

        # الأوامر العادية
        cmd = find_cmd(txt)
        
        if not cmd:
            if tl == "لمح":
                if uid in rdl_st:
                    reply(ev.reply_token, ans_flex(rdl_st[uid].get('hint','لا يوجد'), "لمح"))
                return
            
            if tl == "جاوب":
                if uid in rdl_st:
                    r = rdl_st.pop(uid)
                    reply(ev.reply_token, ans_flex(r.get('answer','غير متوفر'), "جاوب"))
                return
            
            if tl in ["تحليل","تحليل شخصية","شخصية"]:
                if cm.games:
                    reply(ev.reply_token, games_flex(cm.games))
                else:
                    reply(ev.reply_token, TextSendMessage(text="لا توجد تحليلات"))
                return
            
            return

        # معالجة الأوامر
        if cmd == "لغز":
            r = cm.get_r()
            if r:
                rdl_st[uid] = r
                reply(ev.reply_token, puzzle_flex(r))
            else:
                reply(ev.reply_token, TextSendMessage(text="لا توجد ألغاز"))
        
        elif cmd == "اقتباسات":
            q = cm.get_q()
            if q:
                reply(ev.reply_token, TextSendMessage(text=f"📖 اقتباس\n\n\"{q.get('text','')}\"\n\n— {q.get('author','مجهول')}"))
            else:
                reply(ev.reply_token, TextSendMessage(text="لا توجد اقتباسات"))
        
        elif cmd == "منشن":
            m = cm.get_m()
            if m:
                reply(ev.reply_token, TextSendMessage(text=f"👥 سؤال منشن\n\n{m}"))
            else:
                reply(ev.reply_token, TextSendMessage(text="لا توجد أسئلة"))
        
        elif cmd == "موقف":
            s = cm.get_s()
            if s:
                reply(ev.reply_token, TextSendMessage(text=f"🤔 موقف للنقاش\n\n{s}"))
            else:
                reply(ev.reply_token, TextSendMessage(text="لا توجد مواقف"))
        
        else:
            c = cm.get(cmd)
            if c:
                icons = {"سؤال":"❓","تحدي":"🎯","اعتراف":"💭"}
                reply(ev.reply_token, TextSendMessage(text=f"{icons.get(cmd,'▫️')} {cmd}\n\n{c}"))
            else:
                reply(ev.reply_token, TextSendMessage(text="لا توجد بيانات"))
    
    except Exception as e:
        logging.error(f"Err:{e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
