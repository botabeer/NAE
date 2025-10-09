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

# ------------------ قراءة الملفات ------------------
def read_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

questions = read_file("questions.txt")
love_challenges = read_file("challenges.txt")
confessions = read_file("confessions.txt")
personality_questions = read_file("personality_questions.txt")

# ------------------ الألعاب في الكود ------------------
games = {
    "1": {"name": "الغابة", "questions":[
        {"q":"أنت في غابة، ترى كوخ قديم. ماذا تفعل؟", "options":["تدخل الكوخ","تستكشف الغابة","تنتظر مساعدة","ترجع للمنزل"]},
        {"q":"تسمع صوت غريب. ماذا تختار؟", "options":["تجاهله","تتبعه","تصرخ","تختبئ"]},
        {"q":"ترى نهر سريع. ماذا تفعل؟", "options":["تعبره","تمشي على الجسر","تتراجع","تجلس على الضفة"]},
        {"q":"تجد طريقان، أيهما تختار؟", "options":["اليمين","اليسار","العودة","الاستراحة"]},
        {"q":"تجد ثمرة غريبة. ماذا تفعل؟", "options":["تأكلها","تتركها","تأخذها معك","تتجاهل"]},
        {"q":"سمعت صوت حيوان مفترس. ماذا تفعل؟", "options":["تختبئ","تصرخ","تركض","تتسلق شجرة"]},
        {"q":"تجد خيمة مهجورة. ماذا تفعل؟", "options":["تدخلها","تستكشف المنطقة","تتجاهلها","تبني مكانك"]},
        {"q":"أمطار غزيرة، كيف تتصرف؟", "options":["تبحث عن مأوى","تستمر","ترجع","تصنع مظلة"]},
        {"q":"ترى ضوء بعيد. ماذا تفعل؟", "options":["تقترب","تتجاهل","تراقبه","تختبئ"]},
        {"q":"تجد خريطة قديمة. ماذا تفعل؟", "options":["تتبعها","تتركها","تحرقها","تحتفظ بها"]},
    ]},
    "2": {"name": "الجزيرة", "questions":[
        {"q":"أنت على جزيرة مهجورة، ترى كهف. ماذا تفعل؟", "options":["تدخل الكهف","تستكشف الشاطئ","تنتظر مساعدة","تصنع مأوى"]},
        {"q":"تجد طائر غريب. ماذا تفعل؟", "options":["تراقبه","تصطاده","تتركه","تصوره"]},
        {"q":"هناك شجرة مليئة فواكه. ماذا تفعل؟", "options":["تقطفها","تتركها","تأكل مباشرة","تخزنها"]},
        {"q":"ترى قارب بعيد. ماذا تفعل؟", "options":["تسبح نحوه","تراقبه","تجهز نفسك","تتجاهله"]},
        {"q":"تمطر فجأة. ماذا تفعل؟", "options":["تبني مأوى","تظل مبتلاً","تبحث عن كهف","تصنع مظلة"]},
        {"q":"تسمع صوت غريب بالليل. ماذا تفعل؟", "options":["تختبئ","تراقب","تصرخ","تجلس"]},
        {"q":"تجد حيوانات صغيرة. ماذا تفعل؟", "options":["تطعمها","تتركها","تصورها","تصطادها"]},
        {"q":"ترى ضوء بعيد في الغابة. ماذا تفعل؟", "options":["تقترب","تتجاهل","تراقبه","تختبئ"]},
        {"q":"تجد خريطة كنز. ماذا تفعل؟", "options":["تتبعها","تتركها","تحرقها","تحتفظ بها"]},
        {"q":"تجد طعام محفوظ. ماذا تفعل؟", "options":["تأكله","تتركه","تحتفظ به","تشارك مع الآخرين"]},
    ]},
    "3": {"name": "المدينة", "questions":[
        {"q":"أنت في مدينة غريبة، ترى مترو. ماذا تفعل؟", "options":["تركبه","تمشي على الأقدام","تسأل عن الطريق","تراقب المكان"]},
        {"q":"ترى مطعم جديد. ماذا تفعل؟", "options":["تدخل","تمر","تسأل عن الطعام","تصور"]},
        {"q":"تجد شخص ضائع. ماذا تفعل؟", "options":["تساعده","تتجاهله","تسأل الآخرين","تصوره"]},
        {"q":"هناك شارع مزدحم. ماذا تفعل؟", "options":["تمشي","تركب تاكسي","تتوقف","تراقب"]},
        {"q":"ترى نافورة جميلة. ماذا تفعل؟", "options":["تصورها","تجلس","تجاهلها","تستمتع"]},
        {"q":"تجد متجر غريب. ماذا تفعل؟", "options":["تدخل","تمر","تراقب","تسأل"]},
        {"q":"تسمع موسيقى في الشارع. ماذا تفعل؟", "options":["تستمع","تمشي","تصور","تتجاهل"]},
        {"q":"ترى قطة صغيرة. ماذا تفعل؟", "options":["تطعمها","تتركها","تصورها","تراقب"]},
        {"q":"تجد خريطة المدينة. ماذا تفعل؟", "options":["تتبعها","تتركها","تصورها","تسأل"]},
        {"q":"تمطر فجأة، ماذا تفعل؟", "options":["تبحث عن مأوى","تستمر","ترجع","تصنع مظلة"]},
    ]}
}

# ------------------ الجلسات ------------------
user_sessions = {}        # تحليل فردي
group_sessions = {}       # اللعب الجماعي
user_asked_questions = {} # لمنع تكرار الأسئلة

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
        analysis_text += "شخصية عاطفية حساسة، مشاعرك عميقة وتحب تهتم بالناس 💗"
    elif score_active > score_calm:
        analysis_text += "شخصية منفتحة ونشيطة، تحب الحياة والتجارب الجديدة 🔥"
    elif score_calm > score_active:
        analysis_text += "شخصية هادئة ومتزنة، تحب الأمان والاستقرار 🌿"
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

# ------------------ المنطق ------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source,"group_id",None)
    text = event.message.text.strip()
    text_lower = text.lower()

    # أسئلة حب وصراحة
    if "سؤال" in text_lower or "سوال" in text_lower:
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
    if "تحدي" in text_lower:
        c = random.choice(love_challenges)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=f"💌 {c}"))
        return

    # اعتراف
    if "اعتراف" in text_lower:
        conf = random.choice(confessions)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=f"🩷 {conf}"))
        return

    # تحليل شخصية فردي
    if "حلل شخصيتي" in text_lower or "تحليل" in text_lower:
        user_sessions[user_id] = {"step":0,"answers":[]}
        q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token,TextSendMessage(
            text=f"🧠 نبدأ تحليل شخصيتك!\nالسؤال 1:\n{q}"
        ))
        return

    # لعب جماعي
    if text_lower.startswith("لعبه") and group_id:
        game_id = text_lower[-1]
        if game_id in games:
            group_sessions.setdefault(group_id,{})
            group_sessions[group_id][user_id] = {"game":game_id,"step":0,"answers":[]}
            first_q = games[game_id]["questions"][0]
            opts = "\n".join([f"{i+1}. {o}" for i,o in enumerate(first_q["options"])])
            line_bot_api.reply_message(event.reply_token,TextSendMessage(
                text=f"🎮 {games[game_id]['name']} - سؤال 1:\n{first_q['q']}\n{opts}"))
        return

if __name__ == "__main__":
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)
