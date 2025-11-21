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

# ألوان داكنة أنيقة وعصرية
C = {
    'bg': '#0F0B1A',           # خلفية داكنة عميقة
    'glass': '#1A1525',        # زجاج داكن
    'card': '#251E35',         # كرت داكن
    'pri': '#A78BFA',          # بنفسجي فاتح
    'sec': '#7C3AED',          # بنفسجي متوسط
    'acc': '#C4B5FD',          # أكسنت فاتح
    'txt': '#E9D5FF',          # نص فاتح
    'txt2': '#A78BFA',         # نص ثانوي
    'bdr': '#2D2440',          # حدود
    'ok': '#A78BFA'            # تأكيد
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
        ("سؤال 💭","سؤال"),
        ("تحدي 🎯","تحدي"),
        ("اعتراف 💬","اعتراف"),
        ("موقف 🤔","موقف"),
        ("منشن 📱","منشن"),
        ("اقتباسات 📖","اقتباسات"),
        ("لغز 🧩","لغز"),
        ("تحليل 🧠","تحليل")
    ]
    return QuickReply(items=[QuickReplyButton(action=MessageAction(label=l,text=t)) for l,t in items])

def help_flex():
    sections = [
        ("💭 سؤال", "أسئلة متنوعة وممتعة"),
        ("🎯 تحدي", "تحديات مسلية"),
        ("💬 اعتراف", "اعترافات جريئة"),
        ("🤔 موقف", "مواقف للنقاش"),
        ("📱 منشن", "أسئلة منشن"),
        ("📖 اقتباسات", "حكم واقتباسات"),
        ("🧩 لغز", "ألغاز وتلميحات"),
        ("🧠 تحليل", "تحليل الشخصية")
    ]
    
    items = []
    for icon_title, desc in sections:
        items.append(
            BoxComponent(
                layout='horizontal',
                paddingAll='14px',
                backgroundColor=C['card'],
                cornerRadius='12px',
                spacing='md',
                contents=[
                    TextComponent(
                        text=icon_title,
                        size='sm',
                        color=C['acc'],
                        flex=0,
                        weight='bold'
                    ),
                    TextComponent(
                        text=desc,
                        size='sm',
                        color=C['txt2'],
                        flex=1
                    )
                ]
            )
        )
    
    return FlexSendMessage(
        alt_text="مساعدة البوت",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان الرئيسي
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='20px',
                        contents=[
                            TextComponent(
                                text="✨ بوت عناد المالكي",
                                weight='bold',
                                size='xxl',
                                color=C['txt'],
                                align='center'
                            ),
                            TextComponent(
                                text="اختر من الأزرار أدناه",
                                size='sm',
                                color=C['txt2'],
                                align='center',
                                margin='sm'
                            )
                        ]
                    ),
                    
                    # فاصل
                    SeparatorComponent(margin='xl', color=C['bdr']),
                    
                    # الأقسام
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=items
                    ),
                    
                    # ملاحظة
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='16px',
                        backgroundColor=C['glass'],
                        cornerRadius='12px',
                        contents=[
                            TextComponent(
                                text="💡 ملاحظة",
                                size='sm',
                                color=C['acc'],
                                weight='bold',
                                margin='none'
                            ),
                            TextComponent(
                                text="تقدر تستخدم البوت في الخاص والمجموعات",
                                size='xs',
                                color=C['txt2'],
                                margin='sm',
                                wrap=True
                            )
                        ]
                    )
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='16px',
                contents=[
                    TextComponent(
                        text="تم إنشاء هذا البوت بواسطة عبير الدوسري",
                        size='xxs',
                        color=C['txt2'],
                        align='center'
                    )
                ]
            )
        )
    )

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
                    # العنوان مع الأيقونة
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text=f"{icon} {title}",
                                weight='bold',
                                size='xl',
                                color=C['txt'],
                                align='center'
                            )
                        ]
                    ),
                    
                    # المحتوى
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        contents=[
                            TextComponent(
                                text=content,
                                size='lg',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                lineSpacing='8px'
                            )
                        ]
                    ),
                    
                    # زر التالي
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=MessageAction(label=f'✨ {title} التالي', text=cmd_type),
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
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text="🧩 لغز",
                                weight='bold',
                                size='xl',
                                color=C['txt'],
                                align='center'
                            )
                        ]
                    ),
                    
                    # السؤال
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        contents=[
                            TextComponent(
                                text=p['question'],
                                size='xl',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                weight='bold',
                                lineSpacing='8px'
                            )
                        ]
                    ),
                    
                    # الأزرار
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            ButtonComponent(
                                action=MessageAction(label='💡 تلميح', text='لمح'),
                                style='secondary',
                                color=C['sec'],
                                height='md'
                            ),
                            ButtonComponent(
                                action=MessageAction(label='✅ الجواب', text='جاوب'),
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

def ans_flex(a, t):
    is_answer = "جاوب" in t
    icon = "✅" if is_answer else "💡"
    title = "الجواب" if is_answer else "تلميح"
    color = C['ok'] if is_answer else C['sec']
    
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text=f"{icon} {title}",
                                weight='bold',
                                size='xl',
                                color=color,
                                align='center'
                            )
                        ]
                    ),
                    
                    # المحتوى
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        contents=[
                            TextComponent(
                                text=a,
                                size='xl',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                weight='bold',
                                lineSpacing='8px'
                            )
                        ]
                    )
                ]
            )
        )
    )

def games_flex(g):
    btns = []
    for i, x in enumerate(g[:10], 1):
        btns.append(
            ButtonComponent(
                action=MessageAction(
                    label=f"{i}. {x.get('title', f'تحليل {i}')}",
                    text=str(i)
                ),
                style='primary',
                color=C['pri'],
                height='md'
            )
        )
    
    return FlexSendMessage(
        alt_text="تحليل الشخصية",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text="🧠 تحليل الشخصية",
                                weight='bold',
                                size='xl',
                                color=C['txt'],
                                align='center'
                            )
                        ]
                    ),
                    
                    # الأزرار
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

def gq_flex(t, q, p):
    btns = []
    for k, v in q['options'].items():
        btns.append(
            ButtonComponent(
                action=MessageAction(label=f"{k}. {v}", text=k),
                style='primary',
                color=C['pri'],
                height='md'
            )
        )
    
    return FlexSendMessage(
        alt_text=t,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان مع التقدم
                    BoxComponent(
                        layout='horizontal',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text=t,
                                weight='bold',
                                size='lg',
                                color=C['txt'],
                                flex=1
                            ),
                            TextComponent(
                                text=p,
                                size='sm',
                                color=C['txt2'],
                                flex=0,
                                align='end'
                            )
                        ]
                    ),
                    
                    # السؤال
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='20px',
                        backgroundColor=C['card'],
                        cornerRadius='12px',
                        contents=[
                            TextComponent(
                                text=q['question'],
                                size='lg',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                lineSpacing='6px'
                            )
                        ]
                    ),
                    
                    # الخيارات
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

def gr_flex(r):
    return FlexSendMessage(
        alt_text="النتيجة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=C['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        backgroundColor=C['glass'],
                        cornerRadius='16px',
                        paddingAll='16px',
                        contents=[
                            TextComponent(
                                text='🎊 نتيجة التحليل',
                                weight='bold',
                                size='xl',
                                color=C['txt'],
                                align='center'
                            )
                        ]
                    ),
                    
                    # النتيجة
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        paddingAll='24px',
                        backgroundColor=C['card'],
                        cornerRadius='16px',
                        contents=[
                            TextComponent(
                                text=r,
                                size='md',
                                color=C['txt'],
                                wrap=True,
                                lineSpacing='8px'
                            )
                        ]
                    ),
                    
                    # زر تحليل جديد
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=MessageAction(label='🔄 تحليل جديد', text='تحليل'),
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

rdl_st, gm_st = {}, {}

# الأوامر المسموحة
VALID_COMMANDS = {
    "سؤال", "سوال", "تحدي", "اعتراف", "منشن", "موقف", 
    "لغز", "اقتباسات", "اقتباس", "حكمة", "تحليل", 
    "تحليل شخصية", "شخصية", "مساعدة", "لمح", "جاوب"
}

def is_valid_command(txt):
    """التحقق إذا كان النص أمر صحيح"""
    txt_lower = txt.lower().strip()
    
    # التحقق من الأوامر الأساسية
    if txt_lower in [cmd.lower() for cmd in VALID_COMMANDS]:
        return True
    
    # التحقق من الأرقام (للتحليل)
    if txt.strip().isdigit():
        return True
    
    # التحقق من خيارات الأسئلة
    if txt_lower in ['1', '2', '3', 'a', 'b', 'c', 'أ', 'ب', 'ج']:
        return True
    
    return False

def find_cmd(t):
    """تحديد نوع الأمر"""
    t = t.lower().strip()
    
    if t in ["سؤال", "سوال"]:
        return "سؤال"
    elif t == "تحدي":
        return "تحدي"
    elif t == "اعتراف":
        return "اعتراف"
    elif t == "منشن":
        return "منشن"
    elif t == "موقف":
        return "موقف"
    elif t == "لغز":
        return "لغز"
    elif t in ["اقتباسات", "اقتباس", "حكمة"]:
        return "اقتباسات"
    
    return None

def calc_res(ans, gi):
    """حساب النتيجة"""
    cnt = {"أ": 0, "ب": 0, "ج": 0}
    for a in ans:
        if a in cnt:
            cnt[a] += 1
    mc = max(cnt, key=cnt.get)
    return cm.results.get(f"لعبة{gi+1}", {}).get(mc, "شخصيتك فريدة ومميزة!")

def reply(tk, msg):
    """إرسال الرد"""
    try:
        if isinstance(msg, TextSendMessage) and not msg.quick_reply:
            msg.quick_reply = menu()
        line.reply_message(tk, msg)
    except Exception as e:
        logging.error(f"Reply error: {e}")

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

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

@handler.add(MessageEvent, message=TextMessage)
def handle_msg(ev):
    uid = ev.source.user_id
    txt = ev.message.text.strip()
    tl = txt.lower()
    
    # تجاهل الرسائل غير الصحيحة
    if not is_valid_command(txt):
        return  # لا يرد على أي شيء غير الأوامر
    
    try:
        # أمر المساعدة
        if tl == "مساعدة":
            reply(ev.reply_token, help_flex())
            return
        
        # الأوامر الأساسية
        cmd = find_cmd(txt)
        if cmd:
            if cmd == "لغز":
                r = cm.get_r()
                if r:
                    rdl_st[uid] = r
                    reply(ev.reply_token, puzzle_flex(r))
                return
                
            elif cmd == "اقتباسات":
                q = cm.get_q()
                if q:
                    reply(ev.reply_token, content_flex(
                        "اقتباس",
                        "📖",
                        f'"{q.get("text", "")}"\\n\\n— {q.get("author", "مجهول")}',
                        "اقتباسات"
                    ))
                return
                
            elif cmd == "منشن":
                q = cm.get_m()
                if q:
                    reply(ev.reply_token, content_flex("سؤال منشن", "📱", q, "منشن"))
                return
                
            elif cmd == "موقف":
                s = cm.get_s()
                if s:
                    reply(ev.reply_token, content_flex("موقف للنقاش", "🤔", s, "موقف"))
                return
                
            else:
                c = cm.get(cmd)
                if c:
                    icons = {"سؤال": "💭", "تحدي": "🎯", "اعتراف": "💬"}
                    reply(ev.reply_token, content_flex(cmd, icons.get(cmd, ""), c, cmd))
                return
        
        # أوامر اللغز
        if tl == "لمح":
            if uid in rdl_st:
                reply(ev.reply_token, ans_flex(rdl_st[uid].get('hint', 'لا يوجد'), "لمح"))
            return
            
        if tl == "جاوب":
            if uid in rdl_st:
                r = rdl_st.pop(uid)
                reply(ev.reply_token, ans_flex(r['answer'], "جاوب"))
            return
        
        # أمر التحليل
        if tl in ["تحليل", "تحليل شخصية", "شخصية"]:
            if cm.games:
                reply(ev.reply_token, games_flex(cm.games))
            return
        
        # اختيار تحليل
        if txt.isdigit() and uid not in gm_st and 1 <= int(txt) <= len(cm.games):
            gi = int(txt) - 1
            gm_st[uid] = {"gi": gi, "qi": 0, "ans": []}
            g = cm.games[gi]
            reply(ev.reply_token, gq_flex(
                g.get('title', f'تحليل {int(txt)}'),
                g["questions"][0],
                f"1/{len(g['questions'])}"
            ))
            return
        
        # الإجابة على أسئلة التحليل
        if uid in gm_st:
            st = gm_st[uid]
            amap = {
                "1": "أ", "2": "ب", "3": "ج",
                "a": "أ", "b": "ب", "c": "ج",
                "أ": "أ", "ب": "ب", "ج": "ج"
            }
            ans = amap.get(tl, None)
            
            if ans:
                st["ans"].append(ans)
                g = cm.games[st["gi"]]
                st["qi"] += 1
                
                if st["qi"] < len(g["questions"]):
                    reply(ev.reply_token, gq_flex(
                        g.get('title', 'تحليل'),
                        g["questions"][st["qi"]],
                        f"{st['qi']+1}/{len(g['questions'])}"
                    ))
                else:
                    reply(ev.reply_token, gr_flex(calc_res(st["ans"], st["gi"])))
                    del gm_st[uid]
                return
        
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
