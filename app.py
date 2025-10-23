from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, json, typing

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل ملف الألعاب ---
with open("personality_games.json", "r", encoding="utf-8") as f:
    games_data = json.load(f)

# --- مؤشرات لكل مستخدم ---
user_indices: typing.Dict[str, typing.Dict[str, int]] = {}  # user_id -> {"current_game": "لعبة1", "question_index": 0, "answers": []}

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
    user_id = event.source.user_id
    text = event.message.text.strip()

    # --- التحقق إذا المستخدم بدأ لعبة ---
    if user_id not in user_indices or "current_game" not in user_indices[user_id]:
        # عرض الألعاب المتاحة
        games_list = "\n".join([f"- {name}" for name in games_data.keys()])
        reply_text = f"اختر اللعبة لتبدأ:\n{games_list}\n\nاكتب اسم اللعبة (مثلاً: لعبة1)"
        user_indices[user_id] = {"current_game": None, "question_index": 0, "answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # --- المستخدم اختار اللعبة ---
    if user_indices[user_id]["current_game"] is None:
        chosen_game = text
        if chosen_game not in games_data:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء اختيار لعبة صحيحة من القائمة."))
            return
        user_indices[user_id]["current_game"] = chosen_game
        user_indices[user_id]["question_index"] = 0
        user_indices[user_id]["answers"] = []

        first_question = games_data[chosen_game]["questions"][0]
        options_text = "\n".join([f"{key}: {val}" for key, val in first_question["options"].items()])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{first_question['question']}\n{options_text}"
        ))
        return

    # --- المستخدم يجاوب على سؤال ---
    current_game = user_indices[user_id]["current_game"]
    question_index = user_indices[user_id]["question_index"]
    answers = user_indices[user_id]["answers"]
    game_questions = games_data[current_game]["questions"]

    # تحقق من صحة الإجابة
    if text not in ["أ", "ب", "ج"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء اختيار: أ، ب، أو ج."))
        return

    answers.append(text)
    question_index += 1

    # --- سؤال جديد أو إنهاء اللعبة ---
    if question_index < len(game_questions):
        next_question = game_questions[question_index]
        options_text = "\n".join([f"{key}: {val}" for key, val in next_question["options"].items()])
        user_indices[user_id]["question_index"] = question_index
        user_indices[user_id]["answers"] = answers
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{next_question['question']}\n{options_text}"
        ))
    else:
        # حساب النتيجة بناءً على أغلب الاختيارات
        counts = {"أ": 0, "ب": 0, "ج": 0}
        for a in answers:
            counts[a] += 1
        max_choice = max(counts, key=counts.get)
        results_text = games_data[current_game]["results_text"]
        # اختر النتيجة المطابقة لأغلب الاختيارات
        result_lines = results_text.split("\n")
        for line in result_lines:
            if line.startswith(f"أغلب ({max_choice})"):
                final_result = line
                break
        else:
            final_result = "النتيجة غير محددة."

        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"تم الانتهاء من {current_game}.\nنتيجتك:\n{final_result}"
        ))
        # إعادة تعيين المستخدم
        user_indices[user_id] = {"current_game": None, "question_index": 0, "answers": []}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
