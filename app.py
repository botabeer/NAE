from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os, typing

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

# تحميل الملفات
questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personality.txt")
game_file = load_file_lines("game_questions.txt")  # ملف اللعبة

# مؤشرات لكل مستخدم
user_indices = {
    "سؤال": {},
    "تحدي": {},
    "اعتراف": {},
    "شخصي": {},
    "لعبه": {}
}

# فهارس عامة لكل نوع
global_indices = {
    "سؤال": 0,
    "تحدي": 0,
    "اعتراف": 0,
    "شخصي": 0,
    "لعبه": 0
}

# --- إعدادات لعبة التحليل ---
game_questions = [
    {"text":"أي موقف يخليك تبكي أكثر؟","options":{"أ":"عجوز يقرأ رسالة من ابنه المتوفى","ب":"طفل يبيع مناديل في الشارع","ج":"كلب جريح ينظر لعيون الناس طلبًا للمساعدة"}},
    {"text":"لما يزعل منك شخص تحبه، وش تسوي؟","options":{"أ":"تحاول تراضيه بكل طاقتك","ب":"تبتعد شوي لين يهدأ","ج":"تكتب مشاعرك له برسالة طويلة"}},
    {"text":"لو أحد جرحك بكلمة قوية، وش تكون ردّة فعلك؟","options":{"أ":"تسامحه لكنك تتألم من الداخل","ب":"ترد عليه بكلمة أقوى","ج":"تسكت، لكن الكلمة تبقى في بالك فترة"}},
    {"text":"وش أكثر شيء يخوفك؟","options":{"أ":"فقدان شخص غالي","ب":"الفشل بعد تعب طويل","ج":"إنك ما تفهم نفسك أو تضيع مشاعرك"}},
    {"text":"لما أحد يمرّ بضيق، وش تسوي؟","options":{"أ":"تكون أول شخص يوقف معه","ب":"تواسيه لكن بدون ما تتعب نفسك","ج":"تتأثر جدًا وتحزن كأنك تعيش وجعه"}},
    {"text":"كيف تتعامل مع الذكريات القديمة؟","options":{"أ":"تحتفظ فيها لأنها غالية","ب":"تحاول تنساها لأنها توجعك","ج":"ترجع لها أحيانًا لأنها تعلّمك الصبر"}},
    {"text":"لما تحس بالحزن، وش طريقتك بالتعامل معه؟","options":{"أ":"تدعي وتلجأ لله","ب":"تطلع أو تشغل نفسك بشي ثاني","ج":"تكتب مشاعرك أو تبكي بصمت"}}
]

results_text = {
    "أ":"قلبك من ذهب وتضحي من دون تردد\nأنت شخص مساند بطبيعتك، وتشعر الآخرين بالأمان\nلكن تذكر دائمًا أن طيبتك غالية، فلا تهدرها لمن لا يستحق",
    "ب":"قلبك نقي لكنه حذر\nأنت تعطي بحدود وتحب بعقل\nتعرف متى تقترب ومتى تبتعد\nومشاعرك ناضجة وتتعامل مع الحياة بوعي\nلكن لا تجعل الخوف يمنعك من الحب الحقيقي",
    "ج":"قلبك مرهف كالزجاج لكنه قوي كالجبال\nأنت تشعر بكل شيء بعمق\nتتأثر بسرعة لكنك تتعافى بصمت\nجرحك يترك أثرًا، لكنه يصقل شخصيتك المميزة"
}

# جلسات اللعبة لكل مستخدم
game_sessions = {}  # user_id: {"index":0, "answers":[]}

def build_flex_question(q_index):
    question = game_questions[q_index]
    buttons = []
    for key, val in question["options"].items():
        buttons.append({
            "type":"button",
            "action":{
                "type":"message",
                "label":f"{key}: {val}",
                "text":f"game-{key}"
            }
        })
    bubble = {
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","contents":[{"type":"text","text":f"السؤال {q_index+1}","weight":"bold","size":"lg"}]},
        "body":{"type":"box","layout":"vertical","contents":[{"type":"text","text":question["text"]},*buttons]}
    }
    return bubble

def build_flex_result(user_id):
    answers = game_sessions[user_id]["answers"]
    counts = {"أ":0,"ب":0,"ج":0}
    for a in answers:
        counts[a] += 1
    max_ans = max(counts, key=counts.get)
    bubble = {
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","contents":[{"type":"text","text":"نتيجتك","weight":"bold","size":"lg"}]},
        "body":{"type":"box","layout":"vertical","contents":[{"type":"text","text":results_text[max_ans]}]}
    }
    return bubble

@app.route("/", methods=["GET"])
def home():
    return "البوت يعمل", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    # مساعدة
    if text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال\n"
            "- تحدي\n"
            "- اعتراف\n"
            "- شخصي\n"
            "- لعبه\n"
            "- تحليل"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # بدء لعبة التحليل مباشرة
    if text.lower() == "تحليل":
        game_sessions[user_id] = {"index":0, "answers":[]}
        bubble = build_flex_question(0)
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="السؤال 1", contents=bubble))
        return

    # التعامل مع إجابات اللعبة
    if text.startswith("game-") and user_id in game_sessions:
        answer = text.split("-")[1]
        game_sessions[user_id]["answers"].append(answer)
        game_sessions[user_id]["index"] += 1
        q_index = game_sessions[user_id]["index"]

        if q_index < len(game_questions):
            bubble = build_flex_question(q_index)
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"السؤال {q_index+1}", contents=bubble))
        else:
            bubble = build_flex_result(user_id)
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="النتيجة", contents=bubble))
            del game_sessions[user_id]
        return

    # التعامل مع الأوامر السابقة (سؤال، تحدي، اعتراف، شخصي، لعبه)
    if text in ["سؤال", "تحدي", "اعتراف", "شخصي", "لعبه"]:
        if text == "سؤال":
            file_list = questions_file
        elif text == "تحدي":
            file_list = challenges_file
        elif text == "اعتراف":
            file_list = confessions_file
        elif text == "شخصي":
            file_list = personal_file
        else:  # لعبه
            file_list = game_file

        if not file_list:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {text} حالياً."))
            return

        index = global_indices[text]
        msg = file_list[index]

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

        global_indices[text] = (index + 1) % len(file_list)
        user_indices[text][user_id] = global_indices[text]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
