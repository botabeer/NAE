from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# أسئلة اللعبة
game_questions = [
    {"text":"أي موقف يخليك تبكي أكثر؟","options":{"أ":"عجوز يقرأ رسالة من ابنه المتوفى","ب":"طفل يبيع مناديل في الشارع","ج":"كلب جريح ينظر لعيون الناس طلبًا للمساعدة"}},
    {"text":"لما يزعل منك شخص تحبه، وش تسوي؟","options":{"أ":"تحاول تراضيه بكل طاقتك","ب":"تبتعد شوي لين يهدأ","ج":"تكتب مشاعرك له برسالة طويلة"}}
]

results_text = {
    "أ":"قلبك من ذهب",
    "ب":"قلبك نقي لكنه حذر",
    "ج":"قلبك مرهف كالزجاج"
}

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

    if text.lower() == "تحليل":
        game_sessions[user_id] = {"index":0, "answers":[]}
        bubble = build_flex_question(0)
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="السؤال 1", contents=bubble))
        return

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
