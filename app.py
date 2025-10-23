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

# --- تحميل الملفات ---
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personality.txt")
more_file = load_file_lines("more_file.txt")

# تحميل ألعاب من JSON
try:
    with open("personality_games.json", "r", encoding="utf-8") as f:
        games_data = json.load(f)
except Exception:
    games_data = {}

# --- مؤشرات لكل مستخدم ---
user_indices = {"سؤال":{}, "تحدي":{}, "اعتراف":{}, "شخصي":{}, "لعبه":{}, "أكثر":{}}
user_game_progress = {}  # لتتبع السؤال الحالي لكل مستخدم في كل لعبة
global_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0, "لعبه":0, "أكثر":0}

# --- قاموس المرادفات لكل أمر ---
commands_map = {
    "سؤال": ["سؤال", "اسأله", "اسئلة", "سوال"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر"],
    "لعبه": ["لعبه", "اللعبة"]
}

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

def format_game_question(game_title, question_obj):
    options_text = "\n".join([f"{key}: {val}" for key, val in question_obj["options"].items()])
    return f"{game_title}\n\n{question_obj['question']}\n{options_text}"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip().lower()
    user_id = event.source.user_id

    # --- مساعدة ---
    if text == "مساعدة":
        help_text = (
            "- سؤال\n"
            "- شخصي\n"
            "- تحدي\n"
            "- اعتراف\n"
            "- اكثر\n"
            "- لعبه"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # --- تحديد الأمر بناء على المرادفات ---
    command = None
    for key, variants in commands_map.items():
        if text in [v.lower() for v in variants]:
            command = key
            break

    # --- تنفيذ الأمر ---
    if command:
        if command == "سؤال":
            file_list = questions_file
        elif command == "تحدي":
            file_list = challenges_file
        elif command == "اعتراف":
            file_list = confessions_file
        elif command == "شخصي":
            file_list = personal_file
        elif command == "أكثر":
            file_list = more_file
        else:  # لعبه
            # نرسل قائمة الألعاب إذا المستخدم يبدأ أول مرة
            if user_id not in user_game_progress:
                games_list_text = "\n".join([f"{i+1}. {g['title']}" for i, g in enumerate(games_data.values())])
                user_game_progress[user_id] = {"current_game": None, "question_index": 0, "answers": {}}
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اختر اللعبة لتبدأ:\n{games_list_text}"))
                return
            else:
                progress = user_game_progress[user_id]
                # إذا لم يختار لعبة بعد
                if progress["current_game"] is None:
                    # نحاول تحديد اللعبة بناءً على رقم أو اسم
                    for key, g in enumerate(games_data.values(), start=1):
                        if str(key) == text or text in g["title"].lower():
                            game_key = list(games_data.keys())[key-1]
                            progress["current_game"]["current_game"] = game_key
                            break
                    if progress["current_game"] is None:
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اختيار غير صحيح، اكتب رقم اللعبة أو اسمها."))
                        return

                # اللعبة الحالية
                game_key = progress["current_game"]["current_game"]
                game = games_data[game_key]
                question_index = progress["question_index"]
                question_obj = game["questions"][question_index]

                # --- قبول كل الإجابات أ أ 1 1 ---
                answer = text.upper()
                if answer in ["أ", "1"]:  # أي خيار يعتبر صحيح
                    progress["answers"][question_index] = "أ"
                elif answer in ["ب", "2"]:
                    progress["answers"][question_index] = "ب"
                elif answer in ["ج", "3"]:
                    progress["answers"][question_index] = "ج"

                # زيادة السؤال
                progress["question_index"] += 1

                if progress["question_index"] >= len(game["questions"]):
                    # عرض النتيجة
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=game["results_text"]))
                    # إعادة تعيين لتتمكن من اختيار لعبة جديدة
                    user_game_progress.pop(user_id)
                    return
                else:
                    next_question = game["questions"][progress["question_index"]]
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(
                        text=format_game_question(game["title"], next_question)
                    ))
                    return

        # --- للأوامر العادية ---
        if not file_list:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {command} حالياً."))
            return

        index = global_indices[command]
        msg = file_list[index]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        global_indices[command] = (index + 1) % len(file_list)
        user_indices[command][user_id] = global_indices[command]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
