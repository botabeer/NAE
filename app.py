import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الألعاب من الملف ---
with open("personality_games.json", "r", encoding="utf-8") as f:
    games_data = json.load(f)

# ترتيب الألعاب حسب الرقم
games_list = [games_data[key] for key in sorted(games_data.keys())]

# --- متابعة حالة كل مستخدم ---
user_game_state = {}  # user_id: {"game_index": 0, "question_index": 0, "answers": []}

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

    # --- إذا المستخدم يبدأ اللعبة ---
    if text.lower() == "لعبه":
        games_titles = "\n".join([f"{i+1}. {g['title']}" for i, g in enumerate(games_list)])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"اختر اللعبة لتبدأ:\n{games_titles}")
        )
        return

    # --- اختيار رقم اللعبة ---
    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(games_list):
            game_index = num - 1
            user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
            first_question = games_list[game_index]["questions"][0]
            options_text = "\n".join([f"{k}: {v}" for k, v in first_question["options"].items()])
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{first_question['question']}\n{options_text}")
            )
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرقم غير صالح."))
        return

    # --- الرد على سؤال داخل اللعبة ---
    if user_id in user_game_state:
        state = user_game_state[user_id]
        answer = text.strip()
        # قبول أ أو ١ أو 1
        if answer in ["أ", "ب", "ج", "1", "2", "3"]:
            # تحويل 1->أ, 2->ب, 3->ج
            mapping = {"1": "أ", "2": "ب", "3": "ج"}
            answer = mapping.get(answer, answer)
            state["answers"].append(answer)

            game = games_list[state["game_index"]]
            state["question_index"] += 1

            # إذا باقي أسئلة
            if state["question_index"] < len(game["questions"]):
                q = game["questions"][state["question_index"]]
                options_text = "\n".join([f"{k}: {v}" for k, v in q["options"].items()])
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"{q['question']}\n{options_text}")
                )
            else:
                # نهاية اللعبة، عرض النتيجة
                a_count = {"أ": 0, "ب": 0, "ج": 0}
                for ans in state["answers"]:
                    if ans in a_count:
                        a_count[ans] += 1
                # تحديد الأكثر
                most = max(a_count, key=a_count.get)
                result_text = game["results_text"].split("\n")
                selected_text = ""
                for line in result_text:
                    if line.startswith(f"أغلب ({most})"):
                        selected_text = line
                        break
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📝 النتيجة:\n{selected_text}"))
                del user_game_state[user_id]
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء اختيار أ أو ب أو ج (أو 1,2,3)"))
        return

    # --- أوامر مساعدة ---
    if text.lower() == "مساعدة":
        help_text = "- سؤال\n- شخصي\n- تحدي\n- اعتراف\n- اكثر\n- لعبه"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
