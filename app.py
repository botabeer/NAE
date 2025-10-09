from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ------------------ الأسئلة والتحديات والاعترافات ------------------
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
    "اعترف بأكثر شيء تخاف منه."
]

# ------------------ الألعاب ------------------
games = {
    "1": {"name": "الغابة", "questions":[
        {"q":"أنت في غابة، ترى كوخ قديم. ماذا تفعل؟", "options":["تدخل الكوخ","تستكشف الغابة","تنتظر مساعدة","ترجع للمنزل"]},
        {"q":"تسمع صوت غريب. ماذا تختار؟", "options":["تجاهله","تتبعه","تصرخ","تختبئ"]},
        {"q":"وجدت نهر صغير. ماذا تفعل؟", "options":["تشرب منه","تعبره","تجلس بجانبه","تلتقط صور"]},
        {"q":"رأيت آثار أقدام غريبة. ماذا تفعل؟", "options":["تتبعها","تتجاهلها","تصنع فخ","تستدعي المساعدة"]},
        {"q":"بدأ المطر يهطل. ماذا تفعل؟", "options":["تبحث عن مأوى","تستمر بالمغامرة","تجمع أوراق لتغطية نفسك","تعود"]},
        {"q":"سمعت صوت حيوان مفترس. ماذا تختار؟", "options":["تهرب","تختبئ","تصدر صوت لتخيفه","تتسلق شجرة"]},
        {"q":"وجدت فاكهة غريبة. ماذا تفعل؟", "options":["تأكلها","تتركها","تأخذها معك","تدرسها"]},
        {"q":"شاهدت ضوء غريب بين الأشجار. ماذا تختار؟", "options":["تقترب","تبتعد","تراقب من بعيد","تسجل الضوء بالهاتف"]},
        {"q":"رأيت جسر متهدم. ماذا تفعل؟", "options":["تعبر بحذر","تعود","تبني جسر صغير","تستكشف المنطقة"]},
        {"q":"وصلت إلى ساحة مفتوحة. ماذا تختار؟", "options":["تستريح","تجري","تبحث عن مكان مخفي","تصور المكان"]},
    ]},
    "2": {"name": "الجزيرة", "questions":[
        {"q":"على جزيرة مهجورة، ترى خيمة. ماذا تفعل؟", "options":["تدخل الخيمة","تسير على الشاطئ","تبحث عن طعام","تجلس للراحة"]},
        {"q":"وجدت قارورة تحتوي رسالة. ماذا تختار؟", "options":["تفتحها","تتركها","تأخذها معك","تبحث عن صاحبها"]},
        {"q":"رأيت قارب صغير على الشاطئ. ماذا تفعل؟", "options":["تستعمله","تتركه","تتفقده","تدمره"]},
        {"q":"تسمع أصوات غريبة من الغابة. ماذا تختار؟", "options":["تذهب للتحقق","تتجاهلها","تصرخ","تختبئ"]},
        {"q":"وجدت فاكهة نادرة. ماذا تفعل؟", "options":["تأكلها","تتركها","تجمعها","تدرسها"]},
        {"q":"بدأت السماء تمطر فجأة. ماذا تفعل؟", "options":["تبحث عن مأوى","تستمر في التجوال","تجمع مياه المطر","تعود للشاطئ"]},
        {"q":"وجدت كهف مظلم. ماذا تختار؟", "options":["تدخل","تبتعد","تراقب من الخارج","تضيء بالكشاف"]},
        {"q":"رأيت علامة غريبة على الأرض. ماذا تفعل؟", "options":["تتبعها","تتجاهلها","تصورها","تحللها"]},
        {"q":"وجدت جسر مهجور. ماذا تختار؟", "options":["تعبره","تعود","تفحصه","تصوره"]},
        {"q":"وصلت إلى شاطئ آخر. ماذا تفعل؟", "options":["تستريح","تسبح","تبحث عن مورد","تصور المنظر"]},
    ]},
    "3": {"name": "المدينة", "questions":[
        {"q":"في مدينة كبيرة، تجد خريطة غامضة. ماذا تختار؟", "options":["تتبع الخريطة","تسأل السكان","تتجاهلها","تأخذ صورة"]},
        {"q":"رأيت متجر مغلق غريب. ماذا تفعل؟", "options":["تفتحه","تسأل عن السبب","تتجاهله","تصور واجهته"]},
        {"q":"وجدت صندوق غامض في الشارع. ماذا تختار؟", "options":["تفتحه","تتركه","تأخذه معك","تصوره"]},
        {"q":"رأيت ساحة مزدحمة. ماذا تفعل؟", "options":["تدخل الساحة","تتجنبها","تصور المشهد","تسأل أحد"]},
        {"q":"وجدت حديقة صغيرة هادئة. ماذا تختار؟", "options":["تجلس فيها","تجري","تصور الطبيعة","تبحث عن حيوان"]},
        {"q":"شاهدت جسر قديم. ماذا تفعل؟", "options":["تعبره","تجلس بجانبه","تصوره","تستكشف المنطقة"]},
        {"q":"رأيت نافورة قديمة. ماذا تختار؟", "options":["تصورها","تجلس بجانبها","تبحث عن تاريخها","تتجاهلها"]},
        {"q":"وجدت مكتبة مهجورة. ماذا تفعل؟", "options":["تدخلها","تبحث حولها","تصورها","تتجاهلها"]},
        {"q":"رأيت لوحة جدارية غريبة. ماذا تختار؟", "options":["تصورها","تفسرها","تتجاهلها","تسأل السكان"]},
        {"q":"وصلت إلى شارع رئيسي مزدحم. ماذا تفعل؟", "options":["تسير في الشارع","تبحث عن مطعم","تصور المشهد","تتوقف للراحة"]},
    ]}
}

# ------------------ جلسات المستخدمين ------------------
user_asked_questions = {}
user_sessions = {}      # فردي
group_sessions = {}     # جماعي

# ------------------ تحليل الشخصية ------------------
def analyze_personality(answers, name):
    score_active = 0
    score_calm = 0
    score_love = 0
    for a in answers:
        t = str(a).strip().lower()
        if any(x in t for x in ["1","أ","تدخل","تسير","تبحث","تتبع","اجتماعي","قائد","عفوي"]):
            score_active +=1
        if any(x in t for x in ["2","ب","تنتظر","تجلس","تختبئ","هدوء","وحدي","سكوت"]):
            score_calm +=1
        if any(x in t for x in ["3","ج","ص","مشاعر","حب","عاطفي","قلب"]):
            score_love +=1

    analysis_text = f"🔍 تحليل شخصية {name}:\n"
    if score_love > max(score_active, score_calm):
        analysis_text += "شخصية عاطفية حساسة، مشاعرك عميقة وتحب تهتم بالناس وتقدّر التفاصيل 💗"
    elif score_active > score_calm:
        analysis_text += "شخصية منفتحة ونشيطة، تحب الحياة والتجارب الجديدة ومليان طاقة 🔥"
    elif score_calm > score_active:
        analysis_text += "شخصية هادئة ومتزنة، تفكر قبل ما تتكلم وتحب الأمان والاستقرار 🌿"
    else:
        analysis_text += "شخصية متوازنة، تعرف متى تكون هادي ومتى تكون جريء 👌"
    return analysis_text

# ------------------ Webhook ------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature','')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ------------------ المنطق الرئيسي ------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    group_id = getattr(event.source,"group_id",None)

    text_lower = text.lower()

    # مساعدة
    if text_lower=="مساعدة":
        help_text = (
            "❤️ أوامر البوت:\n"
            "- 'سؤال' → سؤال حب/صراحة.\n"
            "- 'تحدي' → تحدي حب.\n"
            "- 'اعتراف' → اعتراف.\n"
            "- 'لعبه 1' → تبدأ لعبة الغابة.\n"
            "- 'لعبه 2' → تبدأ لعبة الجزيرة.\n"
            "- 'لعبه 3' → تبدأ لعبة المدينة.\n"
            "- 'حلل شخصيتي' → يعطيك التحليل بعد انتهاء اللعب.\n"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # أسئلة حب/صراحة
    if text_lower in ["سؤال","سوال"]:
        asked = user_asked_questions.get(user_id,set())
        available = [q for q in questions if q not in asked]
        if not available:
            user_asked_questions[user_id] = set()
            available = questions.copy()
        q = random.choice(available)
        user_asked_questions.setdefault(user_id,set()).add(q)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=q))
        return

    # تحدي
    if text_lower=="تحدي":
        c = random.choice(love_challenges)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=f"💌 {c}"))
        return

    # اعتراف
    if text_lower=="اعتراف":
        conf = random.choice(confessions)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=f"🩷 {conf}"))
        return

    # بدء الألعاب
    if text_lower in ["لعبه 1","لعبه 2","لعبه 3"]:
        game_id = text_lower[-1]
        session = {"game":game_id,"step":0,"answers":[],"answers_map":{}}
        if group_id:
            group_sessions.setdefault(group_id,{})
            group_sessions[group_id][user_id] = session
        else:
            user_sessions[user_id] = session
        first_q = games[game_id]["questions"][0]
        opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(first_q["options"])])
        line_bot_api.reply_message(event.reply_token,TextSendMessage(
            text=f"🎮 لعبة {games[game_id]['name']} - سؤال 1:\n{first_q['q']}\n{opts}"))
        return

    # التعامل مع الجلسة
    if group_id in group_sessions and user_id in group_sessions[group_id]:
        session = group_sessions[group_id][user_id]
    elif user_id in user_sessions:
        session = user_sessions[user_id]
    else:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(
            text="⚠️ لم أفهم. اكتب 'مساعدة' لرؤية الأوامر."))
        return

    # تسجيل الإجابة
    session["answers"].append(text)
    session["answers_map"][session["step"]] = text
    session["step"] +=1

    # متابعة الأسئلة
    game_id = session["game"]
    if session["step"] < len(games[game_id]["questions"]):
        q = games[game_id]["questions"][session["step"]]
        opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(q["options"])])
        line_bot_api.reply_message(event.reply_token,TextSendMessage(
            text=f"🎮 سؤال {session['step']+1}:\n{q['q']}\n{opts}"))
    else:
        # نهاية اللعبة → التحليل
        try:
            name = line_bot_api.get_profile(user_id).display_name
        except:
            name = "مشارك"
        analysis = analyze_personality(session["answers"],name)
        if group_id:
            mention_text = f"@{name}\n{analysis}"
            line_bot_api.push_message(group_id,TextSendMessage(text=mention_text))
            del group_sessions[group_id][user_id]
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text=analysis))
            del user_sessions[user_id]

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
