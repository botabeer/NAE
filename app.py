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
    """الحصول على اسم المستخدم من LINE"""
    if user_id in user_names:
        return user_names[user_id]
    try:
        profile = line_bot_api.get_profile(user_id)
        user_names[user_id] = profile.display_name
        return profile.display_name
    except Exception:
        return "صديقي"

# === دالة تحميل الملفات ===
def load_file_lines(filename: str) -> typing.List[str]:
    """تحميل محتوى ملف نصي"""
    if not os.path.exists(filename):
        print(f"⚠️ الملف غير موجود: {filename}")
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            print(f"✅ تم تحميل {len(lines)} سطر من {filename}")
            return lines
    except Exception as e:
        print(f"❌ خطأ في تحميل {filename}: {e}")
        return []

# === دالة تحميل ملفات JSON ===
def load_json_file(filename: str) -> typing.Union[dict, list]:
    """تحميل ملف JSON"""
    if not os.path.exists(filename):
        print(f"⚠️ الملف غير موجود: {filename}")
        return [] if filename.endswith("s.json") else {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ تم تحميل {filename}")
            return data
    except Exception as e:
        print(f"❌ خطأ في تحميل {filename}: {e}")
        return [] if filename.endswith("s.json") else {}

# === تحميل الملفات النصية ===
content_files = {
    "سؤال": load_file_lines("questions.txt"),
    "تحدي": load_file_lines("challenges.txt"),
    "اعتراف": load_file_lines("confessions.txt"),
    "شخصي": load_file_lines("personality.txt"),
}

# === تحميل أسئلة "أكثر" ===
more_questions = load_file_lines("more_file.txt")

# === تحميل الأمثال والألغاز ===
proverbs_list = load_json_file("proverbs.json")
riddles_list = load_json_file("riddles.json")

# === تحميل الألعاب ===
def load_games():
    """تحميل بيانات الألعاب من ملف JSON"""
    data = load_json_file("personality_games.json")
    if isinstance(data, dict):
        return [data[key] for key in sorted(data.keys())]
    return []

games_list = load_games()

# === تحميل نتائج الألعاب ===
detailed_results = load_json_file("detailed_results.json")

# === حالات المستخدمين ===
user_game_state = {}
user_proverb_state = {}
user_riddle_state = {}
user_content_indices = {key: {} for key in content_files.keys()}
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

def find_command(text: str) -> typing.Optional[str]:
    """البحث عن الأمر المطابق"""
    text_lower = text.lower().strip()
    for key, variants in commands_map.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# === القائمة الرئيسية ===
def create_main_menu():
    """إنشاء القائمة السريعة"""
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
    """الحصول على محتوى عادي"""
    file_list = content_files.get(command, [])
    if not file_list:
        return f"⚠️ لا توجد بيانات متاحة في قسم '{command}' حالياً."
    
    index = global_content_indices[command]
    content = file_list[index]
    global_content_indices[command] = (index + 1) % len(file_list)
    user_content_indices[command][user_id] = global_content_indices[command]
    return content

def get_more_question(user_id: str) -> str:
    """الحصول على سؤال 'أكثر'"""
    global more_questions_index
    if not more_questions:
        return "⚠️ لا توجد أسئلة متاحة في قسم 'أكثر'."
    
    user_name = get_user_name(user_id)
    question = more_questions[more_questions_index]
    more_questions_index = (more_questions_index + 1) % len(more_questions)
    return f"💭 {question}\n\n{user_name}"

def get_proverb(user_id: str) -> str:
    """الحصول على مثل"""
    global proverbs_index
    if not proverbs_list:
        return "⚠️ لا توجد أمثال متاحة حالياً."
    
    proverb = proverbs_list[proverbs_index]
    user_proverb_state[user_id] = proverb
    proverbs_index = (proverbs_index + 1) % len(proverbs_list)
    
    user_name = get_user_name(user_id)
    return f"📜 المثل:\n{proverb['question']}\n\n{user_name}\n\n💡 اكتب 'جاوب' لمعرفة المعنى"

def get_riddle(user_id: str) -> str:
    """الحصول على لغز"""
    global riddles_index
    if not riddles_list:
        return "⚠️ لا توجد ألغاز متاحة حالياً."
    
    riddle = riddles_list[riddles_index]
    user_riddle_state[user_id] = riddle
    riddles_index = (riddles_index + 1) % len(riddles_list)
    
    user_name = get_user_name(user_id)
    return f"🧩 اللغز:\n{riddle['question']}\n\n{user_name}\n\n💡 اكتب 'لمح' للتلميح أو 'جاوب' للإجابة"

def get_games_list() -> str:
    """قائمة الألعاب المتاحة"""
    if not games_list:
        return "⚠️ لا توجد ألعاب متاحة حالياً."
    
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
    """حساب نتيجة اللعبة"""
    count = {"أ": 0, "ب": 0, "ج": 0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index + 1}"
    result_text = detailed_results.get(game_key, {}).get(
        most_common,
        f"✅ إجابتك الأكثر: {most_common}\n\n🎯 نتيجتك تعكس شخصية فريدة!"
    )
    
    stats = f"\n\n📊 إحصائياتك:\n"
    stats += f"أ: {count['أ']} | ب: {count['ب']} | ج: {count['ج']}"
    return result_text + stats

# === Routes ===
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
        print("❌ توقيع غير صالح")
        abort(400)
    return "OK"

# === معالج الرسائل ===
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()
    
    # === أمر المساعدة ===
    if text_lower in ["مساعدة", "help", "بداية", "start"]:
        user_name = get_user_name(user_id)
        welcome_msg = (
            f"👋 أهلاً {user_name}!\n\n"
            "📋 الأقسام المتاحة:\n"
            "❓ سؤال - أسئلة ممتعة\n"
            "🎯 تحدي - تحديات مثيرة\n"
            "💬 اعتراف - اعترافات صادقة\n"
            "👤 شخصي - أسئلة شخصية\n"
            "✨ أكثر - أسئلة 'أكثر واحد'\n"
            "🎮 لعبة - ألعاب تحليل الشخصية\n"
            "📜 أمثال - أمثال شعبية\n"
            "🧩 لغز - ألغاز مسلية\n\n"
            "🔽 اختر من القائمة:"
        )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_msg, quick_reply=create_main_menu())
        )
        return
    
    # === معالجة الأوامر الأساسية ===
    command = find_command(text)
    if command:
        if command == "أمثال":
            content = get_proverb(user_id)
        elif command == "لغز":
            content = get_riddle(user_id)
        elif command == "أكثر":
            content = get_more_question(user_id)
        else:
            content = get_content(command, user_id)
            user_name = get_user_name(user_id)
            content = f"{user_name}\n\n{content}"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content, quick_reply=create_main_menu())
        )
        return

    # === باقي المعالجة تبقى كما هي ===
    if text_lower in ["جاوب", "الجواب", "الاجابة", "اجابة"]:
        if user_id in user_proverb_state:
            proverb = user_proverb_state.pop(user_id)
            user_name = get_user_name(user_id)
            msg = f"✅ معنى المثل:\n{proverb['answer']}\n\n{user_name}"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg, quick_reply=create_main_menu())
            )
            return
        if user_id in user_riddle_state:
            riddle = user_riddle_state.pop(user_id)
            user_name = get_user_name(user_id)
            msg = f"✅ الإجابة:\n{riddle['answer']}\n\n{user_name}"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg, quick_reply=create_main_menu())
            )
            return
        return

    if text_lower in ["لمح", "تلميح", "hint"]:
        if user_id in user_riddle_state:
            riddle = user_riddle_state[user_id]
            hint = riddle.get('hint', 'لا يوجد تلميح')
            user_name = get_user_name(user_id)
            msg = f"💡 التلميح:\n{hint}\n\n{user_name}"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        return

    if text_lower in ["لعبه", "لعبة", "العاب", "ألعاب", "game"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=get_games_list())
        )
        return

    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(games_list):
            game_index = num - 1
            user_game_state[user_id] = {
                "game_index": game_index,
                "question_index": 0,
                "answers": []
            }
            
            user_name = get_user_name(user_id)
            first_q = games_list[game_index]["questions"][0]
            options = "\n".join([f"{k}. {v}" for k, v in first_q["options"].items()])
            msg = f"🎮 {games_list[game_index].get('title', f'اللعبة {num}')}\n"
            msg += f"اللاعب: {user_name}\n\n"
            msg += f"❓ {first_q['question']}\n\n{options}\n\n📝 أرسل: أ، ب، ج"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return
        return

    if user_id in user_game_state:
        state = user_game_state[user_id]
        answer_map = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج"}
        answer = answer_map.get(text_lower, text)
        
        if answer in ["أ", "ب", "ج"]:
            state["answers"].append(answer)
            game = games_list[state["game_index"]]
            state["question_index"] += 1
            
            if state["question_index"] < len(game["questions"]):
                q = game["questions"][state["question_index"]]
                options = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
                progress = f"[{state['question_index'] + 1}/{len(game['questions'])}]"
                msg = f"{progress} ❓ {q['question']}\n\n{options}\n\n📝 أرسل: أ، ب، ج"
                
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=msg)
                )
            else:
                user_name = get_user_name(user_id)
                result = calculate_result(state["answers"], state["game_index"])
                final_msg = f"🎉 انتهت اللعبة!\n"
                final_msg += f"{user_name}\n\n"
                final_msg += f"{result}\n\n"
                final_msg += f"💬 أرسل 'لعبه' لتجربة لعبة أخرى!"
                
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=final_msg, quick_reply=create_main_menu())
                )
                del user_game_state[user_id]
            return
        return

    return

# === تشغيل التطبيق ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
