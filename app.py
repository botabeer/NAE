from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction,
    PostbackEvent, PostbackAction
)
import random, os, urllib.parse

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("حط متغيرات البيئة LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ------------------------------------------------------------------
# قواعد البيانات المؤقّتة بالذاكرة (كل مستخدم سجل خاص به)
# ------------------------------------------------------------------
user_asked_questions = {}   # user_id -> set()  (صراحة)
user_asked_confessions = {} # user_id -> set()  (اعتراف)
user_asked_challenges = {}  # user_id -> set()  (تحدي)
user_analysis_progress = {} # user_id -> {questions:list(idx), current:int, scores:dict}

# ------------------------------------------------------------------
# مجموعة الأسئلة (عامية سعودية)
# ==== صراحة (مختصر هنا كمثال)
truth_questions = [
    "وش أكثر شي تخاف يخسره منك شريكك",
    "هل كذبت عليهم عشان تهون موقف",
    "هل تعطيه خصوصية كاملة ولا تحب تطلع على جواله",
    "هل مر عليك أيام حبيت فيها البعد",
] * 25  # لتكملة الـ100

# ==== اعترافات
confession_questions = [
    "اعترف بأول شخص خاطرك في حياتك",
    "اعترف بشي ندمت عليه من قبل",
] * 50  # لتكملة الـ100

# ==== تحديات
challenges = [
    "ارسل له رسالة تقول فيها اشوفك بتكون محبوب",
    "صف شريكك بثلاث كلمات قدام احد الاشخاص",
] * 50  # لتكملة الـ100

# ==== تحليل الشخصية: 20 سؤال + خيارات
analysis_questions = [
    {
        "q": "لو ضايقك موقف، وش تسوي؟",
        "opts": [
            ("أهدى وافكر قبل ما رد", "calm"),
            ("أنفعل وأتكلم على طول", "strong"),
            ("أجلس واطلع عن الموضوع بعد شوي", "sensitive"),
            ("أسوي خطة وأتعامل عملي", "social")
        ]
    },
    {
        "q": "لما أحد يمدحك، وش شعورك؟",
        "opts": [
            ("أفرح لكن استحِ", "sensitive"),
            ("أستغل الموقف وابني عليه", "strong"),
            ("أضحك وأغير الموضوع", "social"),
            ("أخذها بهدوء وما أبالغ", "calm")
        ]
    },
] * 10  # لتكملة الـ20 سؤال

# ------------------------------------------------------------------
# واجهة الأزرار الرئيسية
# ------------------------------------------------------------------
def main_menu_buttons():
    buttons_template = ButtonsTemplate(
        title="أبغاك تستمتع",
        text="اختار اللي تبي تسويه الحين:",
        actions=[
            MessageAction(label="🎯 تحليل الشخصية", text="تحليل"),
            MessageAction(label="💬 صراحة وجرأة", text="صراحة"),
            MessageAction(label="🗣️ اعترافات", text="اعتراف"),
            MessageAction(label="🔥 تحديات", text="تحدي"),
            MessageAction(label="❓ مساعدة", text="مساعدة")
        ]
    )
    return TemplateSendMessage(alt_text="القائمة", template=buttons_template)

# ------------------------------------------------------------------
# وظائف تحليل الشخصية
# ------------------------------------------------------------------
def start_analysis(user_id):
    pool = list(range(len(analysis_questions)))
    chosen = random.sample(pool, k=len(analysis_questions))
    user_analysis_progress[user_id] = {
        "questions": chosen,
        "current": 0,
        "scores": {"strong":0, "sensitive":0, "social":0, "calm":0}
    }
    qidx = user_analysis_progress[user_id]["questions"][0]
    return build_analysis_question_message(qidx, 1, len(chosen))

def build_analysis_question_message(qidx, number, total):
    item = analysis_questions[qidx]
    title = f"سؤال {number}/{total}: {item['q']}"
    actions = []
    for choice_index, (label, trait) in enumerate(item["opts"]):
        data = urllib.parse.urlencode({"action":"analysis_answer","q":str(qidx),"c":str(choice_index),"t":trait})
        actions.append(PostbackAction(label=label, data=data))
    buttons = ButtonsTemplate(title="تحليل الشخصية", text=title, actions=actions)
    return TemplateSendMessage(alt_text="سؤال تحليل", template=buttons)

def handle_analysis_postback(user_id, qidx, choice_idx, trait):
    data = user_analysis_progress.get(user_id)
    if not data:
        return "ما فيه اختبار شغال عندك، اكتب 'تحليل' لتبدأ."
    if trait in data["scores"]:
        data["scores"][trait] += 1
    data["current"] += 1
    if data["current"] >= len(data["questions"]):
        scores = data["scores"]
        del user_analysis_progress[user_id]
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary, secondary = sorted_scores[0][0], sorted_scores[1][0]
        return generate_analysis_text(primary, secondary, scores)
    else:
        next_qidx = data["questions"][data["current"]]
        return build_analysis_question_message(next_qidx, data["current"]+1, len(data["questions"]))

def generate_analysis_text(primary, secondary, scores):
    mapping = {
        "strong": ("قوي وواثق", "تميل تاخذ زمام الأمور بسرعة."),
        "sensitive": ("حساس وعاطفي", "تقدّر التفاصيل الصغيرة وتعطي قلبك الكبير."),
        "social": ("اجتماعي ومتحمس", "تكون وسط الناس وتحب تجاربهم."),
        "calm": ("هادي ومتفكر", "تفكر قبل ما تتصرف وما تنجر وراك الحماس.")
    }
    p_title, p_text = mapping[primary]
    s_title, s_text = mapping[secondary]
    extra = ""
    if scores[primary] - scores[secondary] >= 5:
        extra = "واضح ان هالطابع يسيطر عليك بشكل كبير."
    elif scores[primary] - scores[secondary] <= 1:
        extra = "شكل شخصيتك مزيج متوازن."
    else:
        extra = "عندك توازن بين الجوانب، لكن جانب واحد يبرز شوي عن الباقي."
    result = f"🎯 تحليلك:\nأبرز طابع: {p_title}\n{p_text}\n\nالثاني اللي يبين: {s_title}\n{s_text}\n\n{extra}"
    return result

# ------------------------------------------------------------------
# Webhook
# ------------------------------------------------------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    if text in ["ابدأ","ابدا","start","لعبة"]:
        line_bot_api.reply_message(event.reply_token, main_menu_buttons())
        return
    if "مساعدة" in text:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📘 أوامر البوت:\nابدأ, تحليل, صراحة, اعتراف, تحدي, إعادة"))
        return
    if "إعادة" in text or "restart" in text:
        user_asked_questions.pop(user_id,None)
        user_asked_confessions.pop(user_id,None)
        user_asked_challenges.pop(user_id,None)
        user_analysis_progress.pop(user_id,None)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة الإعداد"))
        return
    if "صراحة" in text or "جرأة" in text:
        asked = user_asked_questions.get(user_id,set())
        available = [q for q in truth_questions if q not in asked]
        if not available: user_asked_questions[user_id]=set(); available=truth_questions.copy()
        q=random.choice(available)
        user_asked_questions.setdefault(user_id,set()).add(q)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❖ سؤال صراحة:\n{q}"))
        return
    if "اعتراف" in text or "اعترف" in text:
        asked = user_asked_confessions.get(user_id,set())
        available = [q for q in confession_questions if q not in asked]
        if not available: user_asked_confessions[user_id]=set(); available=confession_questions.copy()
        q=random.choice(available)
        user_asked_confessions.setdefault(user_id,set()).add(q)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🗣️ اعتراف:\n{q}"))
        return
    if "تحدي" in text:
        asked = user_asked_challenges.get(user_id,set())
        available = [q for q in challenges if q not in asked]
        if not available: user_asked_challenges[user_id]=set(); available=challenges.copy()
        c=random.choice(available)
        user_asked_challenges.setdefault(user_id,set()).add(c)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🔥 تحدي:\n{c}"))
        return
    if "تحليل" in text:
        msg = start_analysis(user_id)
        line_bot_api.reply_message(event.reply_token, msg)
        return

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    params = dict(urllib.parse.parse_qsl(event.postback.data))
    action = params.get("action")
    if action=="analysis_answer":
        qidx = int(params.get("q",0))
        choice_idx = int(params.get("c",0))
        trait = params.get("t","")
        msg = handle_analysis_postback(user_id,qidx,choice_idx,trait)
        if isinstance(msg,str):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        else:
            line_bot_api.reply_message(event.reply_token, msg)
