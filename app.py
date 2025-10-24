import json
import random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, typing

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الملفات النصية ---
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

# --- تحميل الأمثال والالغاز من JSON ---
try:
    with open("proverbs.json", "r", encoding="utf-8") as f:
        proverbs = json.load(f)
except Exception:
    proverbs = []

try:
    with open("riddles.json", "r", encoding="utf-8") as f:
        riddles = json.load(f)
except Exception:
    riddles = []

# --- حفظ مؤشر التكرار لكل مستخدم لكل نوع لغز ---
user_riddle_index = {}
riddle_order = list(range(len(riddles)))

# --- تحميل ألعاب الشخصية ---
try:
    with open("personality_games.json", "r", encoding="utf-8") as f:
        games_data = json.load(f)
except Exception:
    games_data = {}

games_list = [games_data[key] for key in sorted(games_data.keys())]

# --- متابعة حالة كل مستخدم ---
user_game_state = {}  # user_id: {"game_index": 0, "question_index": 0, "answers": []}

# --- تحميل النصوص التفصيلية من ملف خارجي ---
try:
    with open("detailed_results.json", "r", encoding="utf-8") as f:
        detailed_results = json.load(f)
except Exception:
    detailed_results = {}

# --- مؤشرات لكل مستخدم للأوامر الأخرى ---
user_indices = {"سؤال":{}, "تحدي":{}, "اعتراف":{}, "شخصي":{}, "أكثر":{}}
global_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0, "أكثر":0}

# --- قاموس المرادفات لكل أمر ---
commands_map = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر"],
    "امثله": ["امثله"],
    "لغز": ["لغز", "الغاز", "ألغاز"]
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()

    if text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال\n"
            "- شخصي\n"
            "- تحدي\n"
            "- اعتراف\n"
            "- أكثر\n"
            "- لعبه\n"
            "- امثله\n"
            "- لغز"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    command = None
    for key, variants in commands_map.items():
        if text in [v.lower() for v in variants]:
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
        elif command == "امثله":
            if proverbs:
                selected = random.choice(proverbs)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=selected.get("text", "")))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="لا توجد أمثله حالياً."))
            return
        elif command == "لغز":
            if riddles:
                # ترتيب المستخدِم الخاص
                if user_id not in user_riddle_index:
                    user_riddle_index[user_id] = 0
                    random.shuffle(riddle_order)
                idx = riddle_order[user_riddle_index[user_id] % len(riddles)]
                selected = riddles[idx]
                reply = f"السؤال: {selected.get('question','')}\nتلميح: {selected.get('hint','')}\nالإجابة: {selected.get('answer','')}"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                user_riddle_index[user_id] += 1
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="لا توجد ألغاز حالياً."))
            return

        if file_list:
            index = global_indices[command]
            msg = file_list[index]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            global_indices[command] = (index + 1) % len(file_list)
            user_indices[command][user_id] = global_indices[command]
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {command} حالياً."))
        return

    if text == "لعبه":
        games_titles = "\n".join([
            "1. أي نوع من القلوب تمتلك",
            "2. الأحلام والطموحات الشخصية",
            "3. السعادة الداخلية",
            "4. القوة الشخصية",
            "5. الحب والعلاقات",
            "6. السلام الداخلي",
            "7. الطموح والنجاح",
            "8. التفكير الإيجابي",
            "9. الصداقة والعلاقات الاجتماعية",
            "10. القرارات الحياتية"
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اختر اللعبة لتبدأ:\n{games_titles}"))
        return

    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(games_list):
            game_index = num - 1
            user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
            first_question = games_list[game_index]["questions"][0]
            options_text = "\n".join([f"{k}: {v}" for k, v in first_question["options"].items()])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{first_question['question']}\n{options_text}"))
        return

    if user_id in user_game_state:
        state = user_game_state[user_id]
        answer = text.strip()
        if answer in ["أ", "ب", "ج", "1", "2", "3"]:
            mapping = {"1": "أ", "2": "ب", "3": "ج"}
            answer = mapping.get(answer, answer)
            state["answers"].append(answer)

            game = games_list[state["game_index"]]
            state["question_index"] += 1

            if state["question_index"] < len(game["questions"]):
                q = game["questions"][state["question_index"]]
                options_text = "\n".join([f"{k}: {v}" for k, v in q["options"].items()])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{q['question']}\n{options_text}"))
            else:
                a_count = {"أ": 0, "ب": 0, "ج": 0}
                for ans in state["answers"]:
                    if ans in a_count:
                        a_count[ans] += 1
                most = max(a_count, key=a_count.get)
                game_key = list(games_data.keys())[state["game_index"]]
                detailed_text = detailed_results.get(game_key, {}).get(most, "")
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📝 النتيجة:\n{detailed_text}"))
                del user_game_state[user_id]

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
