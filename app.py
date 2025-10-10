from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random, os

app = Flask(__name__)

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

questions = load_file('questions.txt')
love_challenges = load_file('challenges.txt')
confessions = load_file('confessions.txt')
personality_questions = load_file('personality.txt')

# ----- جلسات المستخدمين -----
user_asked_questions = {}
user_sessions = {}
group_sessions = {}

# ----- الألعاب الثلاثة -----
games = {
    "لعبة1": [
        "أنت في غابة كثيفة، أمامك 4 طرق، أي تختار؟ 1- طريق مضيء 2- طريق مظلم 3- طريق مليء بالزهور 4- طريق صخري",
        "وجدت كوخ قديم، ماذا تفعل؟ 1- تدخل بحذر 2- تنتظر 3- تتحسس 4- تبتعد",
        "رأيت بحيرة صغيرة، ماذا تفعل؟ 1- تسبح 2- تشرب من الماء 3- تجلس على الشاطئ 4- تتجاهلها",
        "سمعت صوت حيوان بري، كيف تتصرف؟ 1- تبتعد 2- تراقبه 3- تقترب بحذر 4- تصرخ",
        "وجدت طريقًا سريًا، ماذا تفعل؟ 1- تتبعه 2- تتجاهله 3- تكتب ملاحظة 4- تصرخ",
        "رأيت ضوء بعيد بين الأشجار، ماذا تفعل؟ 1- تقترب 2- تبقى مكانك 3- تبتعد 4- تنادي الآخرين",
        "وجدت فاكهة غريبة، ماذا تفعل؟ 1- تأكلها 2- تتجاهلها 3- تجرب قطعة صغيرة 4- تجمعها",
        "رأيت طائر غريب، ماذا تفعل؟ 1- تراقبه 2- تقترب 3- تحاول الاقتراب 4- تهرب",
        "سمعت صوت خطوات، كيف تتصرف؟ 1- تختبئ 2- تراقب 3- تصرخ 4- تمشي بحذر",
        "وجدت خريطة قديمة، ماذا تفعل؟ 1- تتبعها 2- تتركها 3- تدرسها 4- تشاركها"
    ],
    "لعبة2": [
        "أنت على جزيرة غامضة، أول ما تراه؟ 1- شاطئ واسع 2- غابة كثيفة 3- جبل شاهق 4- كهف مظلم",
        "وجدت أثر أقدام غريبة، ماذا تفعل؟ 1- تتبعها 2- تتجاهلها 3- تراقب 4- تصرخ",
        "رأيت كوخ مهجور، هل تدخل؟ 1- نعم 2- لا 3- أراقب 4- أدخل لفحص سريع",
        "اقتربت عاصفة، كيف تتصرف؟ 1- تبني مأوى 2- تبحث عن مأوى 3- تنتظر 4- تصل للشاطئ",
        "وجدت صندوق غامض، ماذا تفعل؟ 1- تفتحه 2- تتجاهله 3- تنقله 4- تسأله للآخرين",
        "رأيت طريقًا مقفلًا، كيف تتصرف؟ 1- تبحث عن مفتاح 2- تتجاهله 3- تبحث عن طريق آخر 4- تنتظر المساعدة",
        "سمعت صوت نار، ماذا تفعل؟ 1- تقترب 2- تبقى 3- تبتعد 4- تبحث عن المصدر",
        "وجدت كتابًا غامضًا، ماذا تفعل؟ 1- تقرأه 2- تتجاهله 3- تحمله معك 4- تشارك محتواه",
        "عبور نهر عميق، ماذا تفعل؟ 1- تبني جسر 2- تسبح 3- تبحث عن طريق آخر 4- تنتظر",
        "رأيت ضوءًا غريبًا، ماذا تفعل؟ 1- تقترب 2- تبقى 3- تبتعد 4- تنادي الآخرين"
    ],
    "لعبة3": [
        "أنت في مدينة غريبة، ماذا تفعل أولاً؟ 1- تستكشف الشوارع 2- تبحث عن مأوى 3- تبحث عن طعام 4- تنتظر لتتأمل",
        "رأيت بابًا مغلقًا، ماذا تفعل؟ 1- تفتحه 2- تبحث عن طريق آخر 3- تنتظر 4- تصرخ",
        "شخص غريب يقترب منك، كيف تتصرف؟ 1- تتحدث 2- تراقب 3- تهرب 4- تصرخ",
        "وجدت حقيبة مهجورة، ماذا تفعل؟ 1- تفتحها 2- تتجاهلها 3- تحملها 4- تبحث عن صاحبها",
        "رأيت حيوان أليف، ماذا تفعل؟ 1- تقترب 2- تتجاهله 3- تتبعه 4- تصرخ",
        "سمعت صوتًا غريبًا خلفك، ماذا تفعل؟ 1- تلتفت 2- تهرب 3- تستمر 4- تصرخ",
        "وجدت مطعماً مغلقاً، ماذا تفعل؟ 1- تنتظر 2- تبحث عن مطعم آخر 3- تدخل بالقوة 4- تتجاهل",
        "رأيت نافذة مفتوحة، ماذا تفعل؟ 1- تتسلق 2- تراقب 3- تتجاهل 4- تصرخ",
        "وجدت سيارة مهجورة، ماذا تفعل؟ 1- تفحصها 2- تتجاهلها 3- تدخلها 4- تصرخ",
        "عبور نهر صغير، ماذا تفعل؟ 1- تمشي 2- تبحث عن جسر 3- تسبح 4- تنتظر"
    ]
}

# ----- تحليل مفصل -----
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
        if any(x in t for x in ["4", "تصرف", "تبتعد", "تنتظر"]):
            score_cautious += 1

    analysis = f"🔍 تحليل شخصيتك المفصل:\n"
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
    text = event.message.text.strip().lower()
    group_id = getattr(event.source, "group_id", None)

    # ----- مساعدة -----
    if "مساعدة" in text:
        help_text = (
            "أوامر البوت:\n"
            "- سؤال أو سوال → سؤال حب وصراحة.\n"
            "- تحدي → تحدي عاطفي.\n"
            "- اعتراف → اعتراف صريح.\n"
            "- اسئلة شخصية → أسئلة شخصية.\n"
            "- لعبة1 / لعبة2 / لعبة3 → ألعاب جماعية.\n"
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

    # ----- أسئلة شخصية -----
    if "اسئلة شخصية" in text:
        q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # ----- ألعاب جماعية -----
    if group_id and any(game in text for game in ["لعبة1","لعبة2","لعبة3"]):
        selected_game = None
        for game in ["لعبة1","لعبة2","لعبة3"]:
            if game in text:
                selected_game = game
        if selected_game:
            group_sessions[group_id] = group_sessions.get(group_id,{})
            if user_id not in group_sessions[group_id]:
                group_sessions[group_id][user_id] = {"game": selected_game, "step":0, "answers":[]}
                first_q = games[selected_game][0]
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=first_q))
        return

    # ----- متابعة الإجابات داخل الألعاب -----
    if group_id in group_sessions and user_id in group_sessions[group_id]:
        session = group_sessions[group_id][user_id]
        answer = text.strip()
        if answer:
            # حفظ الإجابة
            session["answers"].append(answer)
            session["step"] += 1

            # إرسال السؤال التالي أو التحليل النهائي
            if session["step"] >= len(games[session["game"]]):
                try:
                    name = line_bot_api.get_profile(user_id).display_name
                except:
                    name = "مشارك"
                analysis = analyze_personality_detailed(session["answers"])
                line_bot_api.push_message(group_id, TextSendMessage(
                    text=f"@{name} انتهت لعبتك، تحليل شخصيتك المفصل:\n{analysis}"
                ))
                del group_sessions[group_id][user_id]
            else:
                next_q = games[session["game"]][session["step"]]
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=next_q))
        return

    # ----- أي شيء آخر -----
    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text="لم أفهم، اكتب 'مساعدة' لرؤية الأوامر."
    ))
    return

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
