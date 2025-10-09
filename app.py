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

# -------------------------------------------------------
# أسئلة الحب، التحديات، الاعترافات
# -------------------------------------------------------
questions = [
"ما أكثر شيء تحبه في شريك حياتك؟",
"اعترف بشيء تخفيه عنه.",
"هل سبق وندمت على تصرف مع شريكك؟",
"هل تغار عليه كثير؟",
"هل تشعر أنه يفهمك بدون كلام؟",
"ما أول شيء جذبك فيه؟",
"هل تعتبر نفسك الطرف الأكثر حباً؟",
"هل تحب المفاجآت الرومانسية؟",
"ما أكثر شيء يجعلك تبتسم معه؟",
"ما أجمل ذكرى بينكما؟"
]

love_challenges = [
"اكتب له رسالة تبدأ بكلمة (أحبك لأن...).",
"شارك معه ذكرى ما تنساها.",
"قل له شي تحبه فيه ما قد قلته.",
"ارسله صورة قديمة تجمعكم.",
"احكي له أول لحظة خفق فيها قلبك له."
]

confessions = [
"اعترف بأول شخص جذبك في حياتك.",
"اعترف بأكثر عادة سيئة عندك.",
"اعترف بشي ندمت عليه.",
"اعترف باسم أول حب في حياتك.",
"اعترف بسر ما قلته لأحد."
]

# -------------------------------------------------------
# الألعاب الثلاث (كل لعبة 10 أسئلة، 4 خيارات)
# -------------------------------------------------------
games = {
    "1": {
        "name": "الغابة",
        "questions": [
            {"q": "أنت في غابة وقدامك كوخ مهجور، تختار:", "options": ["تدخل الكوخ", "تتجاهله وتكمل المشي", "تدور حوله وتستكشف", "تجلس قريب وتراقب المكان"]},
            {"q": "وجدت جدول مياه صغير في الغابة، تختار:", "options": ["تشرب منه", "تملأ زجاجتك", "تتبع مجرى الماء", "تتركه"]},
            {"q": "رأيت طائر غريب في السماء، تختار:", "options": ["تتبع الطائر", "تتركه", "تحاول تصويره", "تجلس تتأمل"]},
            {"q": "وجدت ثمرة غريبة على الأرض، تختار:", "options": ["تأكلها", "تتركها", "تجمعها", "تفحصها"]},
            {"q": "صوت غريب يأتي من الأشجار، تختار:", "options": ["تستكشف الصوت", "تغادر المكان", "تراقب بهدوء", "تصرخ لتعرف ردة فعل"]},
            {"q": "وجدت جسر خشبي قديم، تختار:", "options": ["تعبره", "تتجاهله", "تفحصه أولاً", "تقف للتفكير"]},
            {"q": "سمعت حيوان يزمجر، تختار:", "options": ["تقترب بحذر", "تختبئ", "تصرخ", "تتراجع"]},
            {"q": "وجدت خريطة قديمة، تختار:", "options": ["تتبعها", "تتركها", "تحرقها", "تحللها"]},
            {"q": "رائحة عطر غريبة، تختار:", "options": ["تتبعها", "تتجاهلها", "تحذر", "تستمتع بها"]},
            {"q": "ليلة هادئة والغابة مظلمة، تختار:", "options": ["تخيم", "تواصل المشي", "تستريح على الأرض", "تراقب النجوم"]}
        ]
    },
    "2": {
        "name": "الجزيرة",
        "questions": [
            {"q": "أنت على شاطئ جزيرة مهجورة، تختار:", "options": ["تستكشف الشاطئ", "تجلس على الرمال", "تبحث عن مأوى", "تسبح في البحر"]},
            {"q": "وجدت كهوف على الجزيرة، تختار:", "options": ["تدخل الكهف", "تراقبه فقط", "تتجاهله", "تبحث عن مدخل آخر"]},
            {"q": "رأيت قارب مهجور، تختار:", "options": ["تفحصه", "تركه", "تحاول تشغيله", "تخبئه"]},
            {"q": "وجدت فاكهة غريبة، تختار:", "options": ["تأكلها", "تجمعها", "تتركها", "تستشير الآخرين"]},
            {"q": "سمعت صوت أمواج غريبة، تختار:", "options": ["تستكشف الصوت", "تترك المكان", "تسجل الصوت", "تراقب الأمواج"]},
            {"q": "رأيت حيوان غريب، تختار:", "options": ["تقترب بحذر", "تتركه", "تصوره", "تراقبه"]},
            {"q": "وجدت خريطة جزيرة، تختار:", "options": ["تتبعها", "تتركها", "تحللها", "تحرقها"]},
            {"q": "رائحة دخان من بعيد، تختار:", "options": ["تتجه نحوه", "تتجاهله", "تحذر", "تراقب من بعيد"]},
            {"q": "ليل الجزيرة مظلم، تختار:", "options": ["تخيم", "تواصل المشي", "تراقب النجوم", "تجلس بجانب النار"]},
            {"q": "وجدت صندوق قديم، تختار:", "options": ["تفتحه", "تتركه", "تفحصه", "تحمله معك"]}
        ]
    },
    "3": {
        "name": "المدينة",
        "questions": [
            {"q": "أنت في شارع مزدحم، تختار:", "options": ["تسير مع الناس", "تتوقف وتتأمل", "تدخل محل قريب", "تسأل عن الاتجاه"]},
            {"q": "وجدت نافورة جميلة، تختار:", "options": ["تصورها", "تجلس بجانبها", "تتجاهلها", "تراقب الناس حولها"]},
            {"q": "رأيت قطة ضائعة، تختار:", "options": ["تقترب منها", "تتركها", "تحاول إطعامها", "تبحث عن صاحبها"]},
            {"q": "سمعت موسيقى من بعيد، تختار:", "options": ["تتبع الصوت", "تتجاهله", "تستمتع من مكانك", "تسجل الصوت"]},
            {"q": "رأيت متجر غريب، تختار:", "options": ["تدخل المتجر", "تتجاهله", "تراقبه", "تسأل عن منتجاته"]},
            {"q": "رائحة طعام لذيذ، تختار:", "options": ["تتبع الرائحة", "تستمتع بها من بعيد", "تتجاهلها", "تسأل من صاحبها"]},
            {"q": "وجدت كتاب مهمل على الرصيف، تختار:", "options": ["تفتحه", "تتركه", "تصوره", "تحمله معك"]},
            {"q": "رأيت طفل يبكي، تختار:", "options": ["تساعده", "تتركه", "تسأل عن سبب البكاء", "تراقبه"]},
            {"q": "ليل المدينة مظلم، تختار:", "options": ["تسير بسرعة", "تتوقف وتتأمل", "تدخل مطعم", "تراقب الشارع"]},
            {"q": "وجدت رسالة غريبة، تختار:", "options": ["تقرأها", "تتركها", "تصورها", "تحللها"]}
        ]
    }
}

# -------------------------------------------------------
# جلسات المستخدم
# -------------------------------------------------------
user_sessions = {}  # لكل مستخدم: {"game": "1", "step": 0, "answers": []}
user_asked_questions = {}  # لتجنب تكرار أسئلة الحب والتحديات

# -------------------------------------------------------
# تحليل الشخصية
# -------------------------------------------------------
def analyze_personality(answers, user_name="مشارك"):
    score_active = 0
    score_calm = 0
    score_love = 0

    for a in answers:
        t = a.strip().lower()
        if any(x in t for x in ["1", "تدخل", "تسير", "مغامرة", "نشاط", "استكشاف", "تجربة", "قائد"]):
            score_active += 1
        if any(x in t for x in ["2", "تجلس", "هدوء", "صبر", "تفكر", "راقب"]):
            score_calm += 1
        if any(x in t for x in ["3", "4", "عاطفي", "حب", "مشاعر", "قلب", "تهتم"]):
            score_love += 1

    total = score_active + score_calm + score_love
    def pct(n):
        return int((n / total) * 100) if total > 0 else 0

    result = f"🔹 تحليل شخصية {user_name}:\n"
    result += f"السمة الرئيسية: "
    if score_love > max(score_active, score_calm):
        result += "عاطفية وحساسة 💗\n\n"
    elif score_active > score_calm:
        result += "منفتحة ونشيطة 🔥\n\n"
    elif score_calm > score_active:
        result += "هادئة ومتزنة 🌿\n\n"
    else:
        result += "متوازنة 👌\n\n"

    result += f"💥 النشاط والطاقة: {pct(score_active)}%\n"
    result += "- تحب المبادرة والمغامرة، وتجربة أشياء جديدة.\n"
    result += f"🌿 الهدوء والصبر: {pct(score_calm)}%\n"
    result += "- تميل للتفكير قبل اتخاذ القرارات، صبور وتحافظ على توازنك.\n"
    result += f"💖 العاطفة والمشاعر: {pct(score_love)}%\n"
    result += "- حساس وتهتم بالآخرين، تعبر عن مشاعرك بوضوح.\n\n"
    result += "✨ نصيحة: حاول موازنة طاقتك، صبرك، وعاطفتك لتعيش حياتك وعلاقاتك بأفضل شكل."
    return result

# -------------------------------------------------------
# Webhook
# -------------------------------------------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# -------------------------------------------------------
# الردود الرئيسية
# -------------------------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    user_name = "مشارك"
    try:
        user_name = line_bot_api.get_profile(user_id).display_name
    except:
        pass

    # ------------------- ألعاب -------------------
    if "ابدأ لعبة 1" in text or "ابدأ لعبة 2" in text or "ابدأ لعبة 3" in text:
        game_num = text[-1]
        user_sessions[user_id] = {"game": game_num, "step": 0, "answers": []}
        q = games[game_num]["questions"][0]
        opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(q["options"])])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"🎮 بدأت لعبة {games[game_num]['name']}!\nالسؤال 1:\n{q['q']}\n{opts}"
        ))
        return

    # ------------------- إجابة على اللعبة -------------------
    if user_id in user_sessions:
        session = user_sessions[user_id]
        game_num = session["game"]
        step = session["step"]
        qlist = games[game_num]["questions"]

        # تسجيل الإجابة
        session["answers"].append(text)
        session["step"] += 1

        # السؤال التالي
        if session["step"] >= len(qlist):
            analysis = analyze_personality(session["answers"], user_name)
            del user_sessions[user_id]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=analysis))
        else:
            q = qlist[session["step"]]
            opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(q["options"])])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"السؤال {session['step']+1}:\n{q['q']}\n{opts}"
            ))
        return

    # ------------------- أسئلة الحب -------------------
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

    # ------------------- تحدي -------------------
    if "تحدي" in text:
        c = random.choice(love_challenges)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💌 {c}"))
        return

    # ------------------- اعتراف -------------------
    if "اعتراف" in text:
        conf = random.choice(confessions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🩷 {conf}"))
        return

    # ------------------- تحليل الشخصية -------------------
    if "حلل شخصيتي" in text:
        # تحليل جميع إجابات المستخدم السابقة في الألعاب
        if user_id in user_sessions:
            answers = user_sessions[user_id]["answers"]
        else:
            answers = []
        analysis = analyze_personality(answers, user_name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=analysis))
        return

    # ------------------- مساعدة -------------------
    if "مساعدة" in text:
        help_text = (
            "❤️ أوامر البوت:\n"
            "- 'سؤال' أو 'سوال' → سؤال حب أو صراحة عشوائي.\n"
            "- 'تحدي' → تحدي حب رومانسي.\n"
            "- 'اعتراف' → سؤال اعتراف صريح.\n"
            "- 'ابدأ لعبة 1/2/3' → تبدأ أي من الألعاب الثلاث.\n"
            "- 'حلل شخصيتي' → يعطي تحليل تفصيلي من إجاباتك.\n"
            "- 'مساعدة' → عرض الأوامر.\n"
            "💡 تقدر تجاوب بالرقم، النص، أو 'التالي' لتكمل الأسئلة."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # أي شيء آخر
    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text="ما فهمت، حاول تكتب الرقم أو الإجابة الصحيحة أو ‘التالي’ أو أحد أوامر البوت."
    ))
    return

# -------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
