from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceUser, SourceGroup
import random, os

app = Flask(__name__)

# ----- مفاتيح LINE -----
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ----- تحميل البيانات من الملفات -----
def load_file(filename):
    try:
        with open(filename, encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

questions = load_file('questions.txt')          # أسئلة حب وصراحة
love_challenges = load_file('challenges.txt')  # تحديات
confessions = load_file('confessions.txt')     # اعترافات
personality_questions = load_file('personality.txt') # أسئلة شخصية

# ----- جلسات المستخدمين -----
user_asked_questions = {}   # لتجنب تكرار السؤال للفرد
user_sessions = {}          # جلسات تحليل شخصي
group_sessions = {}         # جلسات جماعية للألعاب والتحليل

# ----- ألعاب جماعية -----
game1_questions = [
    "تخيّل أنك في غابة كثيفة، أمامك 4 طرق، أي طريق تختار؟ 1- طريق مضيء 2- طريق مظلم 3- طريق مليء بالزهور 4- طريق صخري ووعر",
    "وجدت كوخ قديم وسط الغابة، كيف تتصرف؟ 1- تدخل بحذر 2- تنتظر وتراقب 3- تتحسس حوله قبل الدخول 4- تبتعد تمامًا",
    "رأيت بحيرة صغيرة، ماذا تفعل؟ 1- تسبح 2- تشرب من الماء 3- تجلس على الشاطئ تتأمل 4- تتجاهلها وتكمل الطريق",
    "سمعت صوت حيوان بري، كيف تتصرف؟ 1- تبتعد بسرعة 2- تراقبه بصمت 3- تقترب بحذر 4- تصرخ",
    "وجدت طريقًا سريًا، ماذا تفعل؟ 1- تتبعه بحذر 2- تتجاهله 3- تكتب ملاحظة للعودة 4- تصرخ وتلفت الانتباه",
    "رأيت ضوء بعيد بين الأشجار، ماذا تفعل؟ 1- تقترب لاستكشافه 2- تبقى مكانك 3- تبتعد 4- تنادي للتأكد من الآخرين",
    "وجدت فاكهة غريبة، ماذا تفعل؟ 1- تأكلها بحذر 2- تتجاهلها 3- تقطع قطعة صغيرة للتجربة 4- تجمعها للآخرين",
    "رأيت طائر غريب، ماذا تفعل؟ 1- تراقبه 2- تقترب بحذر 3- تحاول الاقتراب ببطء 4- تهرب",
    "سمعت صوت خطوات، كيف تتصرف؟ 1- تختبئ 2- تراقب 3- تصرخ 4- تمشي بحذر نحو الصوت",
    "وجدت خريطة قديمة، ماذا تفعل؟ 1- تتبعها بحماس 2- تتركها 3- تدرسها قبل التحرك 4- تشاركها مع الآخرين"
]

game2_questions = [
    "أنت على جزيرة غامضة، أول ما تراه؟ 1- شاطئ واسع 2- غابة كثيفة 3- جبل شاهق 4- كهف مظلم",
    "وجدت أثر أقدام غريبة، ماذا تفعل؟ 1- تتبعها بحذر 2- تتجاهلها 3- تراقب المنطقة 4- تصرخ",
    "رأيت كوخ مهجور، هل تدخل؟ 1- نعم بحذر 2- لا أبدًا 3- أراقب من بعيد 4- أدخل لفحص سريع",
    "اقتربت عاصفة، كيف تتصرف؟ 1- تبني مأوى مؤقت 2- تبحث عن مأوى جاهز 3- تنتظر المكان 4- تحاول الوصول لشاطئ آمن",
    "وجدت صندوق غامض، ماذا تفعل؟ 1- تفتحه بحذر 2- تتجاهله 3- تنقله لمكان آمن 4- تسأله للآخرين",
    "رأيت طريقًا مقفلًا، كيف تتصرف؟ 1- تبحث عن مفتاح 2- تتجاهله 3- تبحث عن طريق آخر 4- تنتظر المساعدة",
    "سمعت صوت نار، ماذا تفعل؟ 1- تقترب بحذر 2- تبقى في مكانك 3- تبتعد 4- تبحث عن مصدر النار",
    "وجدت كتابًا غامضًا، ماذا تفعل؟ 1- تقرأه 2- تتجاهله 3- تحمله معك 4- تشارك محتواه مع الآخرين",
    "احتجت عبور نهر عميق، كيف تفعل؟ 1- تبني جسرًا 2- تسبح بحذر 3- تبحث عن طريق آخر 4- تنتظر حتى يهدأ التيار",
    "رأيت ضوءًا غريبًا على الشاطئ، ماذا تفعل؟ 1- تقترب 2- تبقى مكانك 3- تبتعد بحذر 4- تنادي الآخرين"
]

game3_questions = [
    "أنت في مدينة غريبة، ماذا تفعل أولاً؟ 1- تستكشف الشوارع 2- تبحث عن مأوى 3- تبحث عن طعام 4- تنتظر لتتأمل",
    "رأيت بابًا مغلقًا، ماذا تفعل؟ 1- تفتحه بحذر 2- تبحث عن طريق آخر 3- تنتظر 4- تصرخ لجذب الانتباه",
    "شخص غريب يقترب منك، كيف تتصرف؟ 1- تتحدث معه 2- تراقبه بصمت 3- تهرب 4- تصرخ",
    "وجدت حقيبة مهجورة، ماذا تفعل؟ 1- تفتحها بحذر 2- تتجاهلها 3- تحملها معك 4- تبحث عن صاحبها",
    "رأيت حيوان أليف في الشارع، ماذا تفعل؟ 1- تقترب 2- تتجاهله 3- تتبعه 4- تصرخ",
    "سمعت صوتًا غريبًا خلفك، ماذا تفعل؟ 1- تلتفت بحذر 2- تهرب 3- تستمر 4- تصرخ",
    "وجدت مطعماً مغلقاً، ماذا تفعل؟ 1- تنتظر 2- تبحث عن مطعم آخر 3- تدخل بالقوة 4- تتجاهل",
    "رأيت نافذة مفتوحة، ماذا تفعل؟ 1- تتسلق 2- تراقب 3- تتجاهل 4- تصرخ",
    "وجدت سيارة مهجورة، ماذا تفعل؟ 1- تفحصها بحذر 2- تتجاهلها 3- تدخلها 4- تصرخ",
    "احتجت عبور نهر صغير، ماذا تفعل؟ 1- تمشي عبره 2- تبحث عن جسر 3- تسبح بحذر 4- تنتظر"
]

# ----- تحليل الشخصية مفصل وطويل -----
def analyze_personality_detailed(answers):
    score_active = 0
    score_calm = 0
    score_love = 0
    score_cautious = 0

    for a in answers:
        t = a.strip().lower()
        if any(x in t for x in ["1", "مضيء", "مغامرة", "تستكشف"]):
            score_active += 1
        if any(x in t for x in ["2", "هدوء", "تفكر", "تراقب"]):
            score_calm += 1
        if any(x in t for x in ["3", "حب", "عاطفي", "تأمل"]):
            score_love += 1
        if any(x in t for x in ["4", "تصرف بحذر", "تبتعد", "تنتظر"]):
            score_cautious += 1

    analysis = "🔍 **تحليل شخصيتك المفصل:**\n"
    analysis += f"- النشاط والطاقة: {score_active}\n"
    analysis += f"- الهدوء والتأمل: {score_calm}\n"
    analysis += f"- العاطفة والحساسية: {score_love}\n"
    analysis += f"- الحذر والتفكير قبل التصرف: {score_cautious}\n\n"

    analysis += "استنادًا إلى إجاباتك:\n"
    if score_love >= max(score_active, score_calm):
        analysis += "• شخصية عاطفية وحساسة، تهتم بالآخرين وتقدر التفاصيل الصغيرة.\n"
    if score_active >= max(score_love, score_calm):
        analysis += "• شخصية نشيطة ومغامرة، تحب استكشاف الجديد وتجربة المواقف.\n"
    if score_calm >= max(score_active, score_love):
        analysis += "• شخصية هادئة ومتأملة، تفكر قبل اتخاذ أي قرار.\n"
    if score_cautious > 0:
        analysis += "• حذرة، توازن بين الجرأة والحذر في تصرفاتها.\n"

    analysis += "هذه الإجابات تكشف ميولك، أسلوب تعاملك مع الآخرين وطريقة مواجهتك للتحديات."
    return analysis

# ----- Webhook -----
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ----- الرد على الرسائل -----
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip().lower()

    # ----- مساعدة -----
    if "مساعدة" in text:
        help_text = (
            "أوامر البوت:\n"
            "- سؤال أو سوال → سؤال حب وصراحة.\n"
            "- تحدي → تحدي عاطفي.\n"
            "- اعتراف → اعتراف صريح.\n"
            "- اسألة شخصيه → اسئلة شخصية.\n"
            "- لعبه1 / لعبه2 / لعبه3 → ألعاب جماعية.\n"
            "- تحليل → يعطي تحليل مفصل لشخصيتك.\n"
            "- مساعدة → عرض الأوامر."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # ----- أسئلة حب وصراحة -----
    if "سؤال" in text or "سوال" in text:
        asked = user_asked_questions.get(user_id, set())
        available = [q for q in questions if q not in asked]
        if not available:
            user_asked_questions[user_id] = set()
            available = questions.copy()
        q = random.choice(available)
        user_asked_questions.setdefault(user_id, set()).add(q)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # ----- تحدي -----
    if "تحدي" in text:
        c = random.choice(love_challenges)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💌 {c}"))
        return

    # ----- اعتراف -----
    if "اعتراف" in text:
        conf = random.choice(confessions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🩷 {conf}"))
        return

    # ----- اسئلة شخصية -----
    if "اسألة شخصية" in text:
        q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🧠 {q}"))
        return

    # ----- تحليل مفصل -----
    if "تحليل" in text:
        user_sessions[user_id] = {"step": 0, "answers": []}
        q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"🧩 نبدأ تحليل شخصيتك!\nالسؤال 1:\n{q}"
        ))
        return

    # ----- ألعاب جماعية -----
    for idx, game in enumerate([game1_questions, game2_questions, game3_questions], start=1):
        if f"لعبه{idx}" in text and group_id:
            group_sessions[group_id] = {}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"🎲 لعبة {idx} بدأت!\nكل شخص يرسل 'ابدأ' للانضمام."
            ))
            return

    # ----- الانضمام للعبة -----
    if group_id in group_sessions and text == "ابدأ":
        if user_id not in group_sessions[group_id]:
            group_sessions[group_id][user_id] = {"step": 0, "answers": []}
            q = random.choice(game1_questions)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"✨ {q}"
            ))
        return

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
