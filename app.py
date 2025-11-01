import json
import os
import typing
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)

# === إعداد متغيرات البيئة ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === تخزين أسماء المستخدمين ===
user_names = {}

def get_user_name(user_id: str) -> str:
    if user_id in user_names:
        return user_names[user_id]
    try:
        profile = line_bot_api.get_profile(user_id)
        user_names[user_id] = profile.display_name
        return profile.display_name
    except Exception:
        return "صديقي"

# === تحميل الملفات ===
def load_file_lines(filename: str) -> typing.List[str]:
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def load_json_file(filename: str):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# === تحميل الملفات ===
content_files = {
    "سؤال": load_file_lines("questions.txt"),
    "تحدي": load_file_lines("challenges.txt"),
    "اعتراف": load_file_lines("confessions.txt"),
    "شخصي": load_file_lines("personality.txt"),
}

more_questions = load_file_lines("more_file.txt")
proverbs_list = load_json_file("proverbs.json")
riddles_list = load_json_file("riddles.json")
detailed_results = load_json_file("detailed_results.json")

def load_games():
    data = load_json_file("personality_games.json")
    if isinstance(data, dict):
        return [data[key] for key in sorted(data.keys())]
    return []
games_list = load_games()

# === حالات المستخدمين ===
user_game_state = {}
user_proverb_state = {}
user_riddle_state = {}

global_content_indices = {key: 0 for key in content_files.keys()}
more_questions_index = 0
proverbs_index = 0
riddles_index = 0

# === خريطة الأوامر ===
commands_map = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة", "اسأل"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر", "زيادة"],
    "أمثال": ["أمثال", "امثال", "مثل"],
    "لغز": ["لغز", "الغاز", "ألغاز"]
}

def find_command(text: str):
    text_lower = text.lower().strip()
    for key, variants in commands_map.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

def create_main_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="❓ سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="🎯 تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="💬 اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="👤 شخصي", text="شخصي")),
        QuickReplyButton(action=MessageAction(label="✨ أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="🎮 لعبة", text="لعبه")),
        QuickReplyButton(action=MessageAction(label="📜 أمثال", text="أمثال")),
        QuickReplyButton(action=MessageAction(label="🧩 لغز", text="لغز")),
    ])

# === دوال المحتوى ===
def get_content(command: str, user_id: str) -> str:
    file_list = content_files.get(command, [])
    if not file_list:
        return f"⚠️ لا توجد بيانات في قسم '{command}'."
    index = global_content_indices[command]
    content = file_list[index]
    global_content_indices[command] = (index + 1) % len(file_list)
    return content

def get_more_question(user_id: str) -> str:
    global more_questions_index
    if not more_questions:
        return "⚠️ لا توجد أسئلة في 'أكثر'."
    user_name = get_user_name(user_id)
    question = more_questions[more_questions_index]
    more_questions_index = (more_questions_index + 1) % len(more_questions)
    return f"💭 {question}\n\n {user_name}"

def get_proverb(user_id: str) -> str:
    global proverbs_index
    if not proverbs_list:
        return "⚠️ لا توجد أمثال."
    proverb = proverbs_list[proverbs_index]
    user_proverb_state[user_id] = proverb
    proverbs_index = (proverbs_index + 1) % len(proverbs_list)
    user_name = get_user_name(user_id)
    return f"📜 المثل:\n{proverb['question']}\n\n {user_name}\n\n💬 اكتب 'جاوب' لمعرفة الإجابة"

def get_riddle(user_id: str) -> str:
    global riddles_index
    if not riddles_list:
        return "⚠️ لا توجد ألغاز."
    riddle = riddles_list[riddles_index]
    user_riddle_state[user_id] = riddle
    riddles_index = (riddles_index + 1) % len(riddles_list)
    user_name = get_user_name(user_id)
    return f"🧩 اللغز:\n{riddle['question']}\n\n {user_name}\n\n💡 اكتب 'لمح' للتلميح أو 'جاوب' للإجابة"

def get_games_list() -> str:
    if not games_list:
        return "⚠️ لا توجد ألعاب متاحة."
    titles = [
        "🎮 الألعاب المتاحة:",
        "",
        "1️⃣ أي نوع من القلوب تمتلك",
        "2️⃣ القوة الشخصية",
        "3️⃣ الحب والعلاقات",
        "4️⃣ السلام الداخلي",
        "5️⃣ الطموح والنجاح",
        "6️⃣ التفكير الإيجابي",
        "7️⃣ الصداقة والعلاقات",
        "8️⃣ القرارات الحياتية",
        "9️⃣ الأحلام والطموحات",
        "🔟 الراحة النفسية",
        "",
        "📌 أرسل رقم اللعبة (1-10)"
    ]
    return "\n".join(titles)

def calculate_result(answers: typing.List[str], game_index: int) -> str:
    count = {"أ": 0, "ب": 0, "ج": 0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index + 1}"
    result_text = detailed_results.get(game_key, {}).get(
        most_common,
        f"✅ أكثر إجاباتك كانت ({most_common}) وتعكس شخصية فريدة!"
    )
    stats = f"\n\n📊 الإحصائيات:\nأ: {count['أ']} | ب: {count['ب']} | ج: {count['ج']}"
    return result_text + stats

# === Webhook ===
@app.route("/", methods=["GET"])
def home():
    return "✅ البوت يعمل بنجاح!", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# === معالج الرسائل ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()

    if text_lower in ["مساعدة", "بداية", "start"]:
        user_name = get_user_name(user_id)
        welcome_msg = (
            f"👋 أهلاً {user_name}!\n\n"
            "اختر نوع المحتوى من القائمة أدناه 👇"
        )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_msg, quick_reply=create_main_menu())
        )
        return

    command = find_command(text)
    if command:
        if command == "أمثال":
            msg = get_proverb(user_id)
        elif command == "لغز":
            msg = get_riddle(user_id)
        elif command == "أكثر":
            msg = get_more_question(user_id)
        else:
            user_name = get_user_name(user_id)
            msg = f"{user_name}\n\n{get_content(command, user_id)}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg, quick_reply=create_main_menu())
        )
        return

    if text_lower in ["جاوب", "الجواب"]:
        if user_id in user_proverb_state:
            proverb = user_proverb_state.pop(user_id)
            msg = f"✅ الإجابة:\n{proverb['answer']}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        if user_id in user_riddle_state:
            riddle = user_riddle_state.pop(user_id)
            msg = f"✅ الإجابة:\n{riddle['answer']}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        return

    if text_lower in ["لمح", "تلميح"]:
        if user_id in user_riddle_state:
            hint = user_riddle_state[user_id].get("hint", "لا يوجد تلميح.")
            msg = f"💡 التلميح:\n{hint}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return
        return

    if text_lower in ["لعبه", "لعبة"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_games_list()))
        return

    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(games_list):
            user_game_state[user_id] = {"game_index": num-1, "question_index": 0, "answers": []}
            game = games_list[num-1]
            first_q = game["questions"][0]
            options = "\n".join([f"{k}. {v}" for k,v in first_q["options"].items()])
            msg = f"🎮 {game['title']}\n❓ {first_q['question']}\n\n{options}\n📝 أرسل: أ، ب، ج"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    if user_id in user_game_state:
        state = user_game_state[user_id]
        answer_map = {"1":"أ","2":"ب","3":"ج","a":"أ","b":"ب","c":"ج"}
        ans = answer_map.get(text_lower, text)
        if ans in ["أ","ب","ج"]:
            state["answers"].append(ans)
            state["question_index"] += 1
            game = games_list[state["game_index"]]
            if state["question_index"] < len(game["questions"]):
                q = game["questions"][state["question_index"]]
                opts = "\n".join([f"{k}. {v}" for k,v in q["options"].items()])
                msg = f"[{state['question_index']+1}/{len(game['questions'])}] ❓ {q['question']}\n\n{opts}\n📝 أرسل: أ، ب، ج"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            else:
                result = calculate_result(state["answers"], state["game_index"])
                msg = f"🏁 انتهت اللعبة!\n{result}\n\n🎯 أرسل 'لعبه' لتجربة أخرى"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
                del user_game_state[user_id]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
