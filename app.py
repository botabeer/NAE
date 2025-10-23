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

# --- تحميل ملف الألعاب JSON ---
try:
    with open("personality_games.json", "r", encoding="utf-8") as f:
        games_data = json.load(f)
except Exception as e:
    games_data = {}
    print("خطأ في تحميل ملف الألعاب:", e)

# --- مؤشرات لكل مستخدم ---
user_indices = {"سؤال":{}, "تحدي":{}, "اعتراف":{}, "شخصي":{}, "لعبه":{}, "أكثر":{}}
global_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0, "لعبه":0, "أكثر":0}

# --- حالة الألعاب لكل مستخدم ---
user_game_state = {}  # {user_id: {"current_game": "اللعبة 1", "question_index": 0, "answers": []}}

# --- قاموس المرادفات لكل أمر ---
commands_map = {
    "سؤال": ["سؤال", "اسأله", "اسئلة"],
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

def start_game(user_id: str, game_name: str):
    if game_name not in games_data:
        return "هذه اللعبة غير موجودة حالياً."
    user_game_state[user_id] = {
        "current_game": game_name,
        "question_index": 0,
        "answers": []
    }
    first_question = games_data[game_name]["questions"][0]
    return format_question(first_question)

def format_question(q: dict):
    text = q["question"] + "\n"
    for key, option in q["options"].items():
        text += f"{key}: {option}\n"
    return text

def process_game_answer(user_id: str, answer: str):
    state = user_game_state.get(user_id)
    if not state:
        return "ابدأ أولاً بإرسال اسم اللعبة لتبدأ."
    game_name = state["current_game"]
    questions = games_data[game_name]["questions"]
    current_index = state["question_index"]
    # تسجيل الإجابة
    state["answers"].append(answer)
    # الانتقال للسؤال التالي
    next_index = current_index + 1
    if next_index >= len(questions):
        # اللعبة انتهت، أرسل النتيجة
        result_text = games_data[game_name].get("results_text", "")
        # هنا يمكن تخصيص النتائج حسب الإجابات إذا أردنا لاحقًا
        user_game_state.pop(user_id)
        return result_text
    else:
        state["question_index"] = next_index
        return format_question(questions[next_index])

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    lower_text = text.lower()
    user_id = event.source.user_id

    # --- مساعدة ---
    if lower_text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال (اسأله / اسئلة)\n"
            "- تحدي (تحديات / تحد)\n"
            "- اعتراف (اعترافات)\n"
            "- شخصي (شخصية / شخصيات)\n"
            "- أكثر (اكثر)\n"
            "- لعبه (اللعبة)\n"
            "يمكنك بدء لعبة بإرسال اسمها تمامًا كما هو مكتوب في البوت."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # --- التعامل مع لعبة نشطة ---
    if user_id in user_game_state:
        response = process_game_answer(user_id, text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response))
        return

    # --- تحديد الأمر ---
    command = None
    for key, variants in commands_map.items():
        if lower_text in [v.lower() for v in variants]:
            command = key
            break

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
            # عرض قائمة الألعاب المتوفرة
            games_list = "\n".join([f"- {g}" for g in games_data.keys()])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"اختر اللعبة لتبدأ:\n{games_list}"
            ))
            return

        if not file_list:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {command} حالياً."))
            return

        index = global_indices[command]
        msg = file_list[index]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        global_indices[command] = (index + 1) % len(file_list)
        user_indices[command][user_id] = global_indices[command]
        return
    else:
        # إذا المستخدم كتب اسم اللعبة مباشرة
        if text in games_data:
            response = start_game(user_id, text)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response))
            return

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="أمر غير معروف، اكتب 'مساعدة' لمعرفة الأوامر."))
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
