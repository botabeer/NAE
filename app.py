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

# إعداد متغيرات البيئة
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# تخزين أسماء المستخدمين
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

def load_file_lines(filename: str) -> typing.List[str]:
    if not os.path.exists(filename):
        print(f"الملف غير موجود: {filename}")
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            print(f"تم تحميل {len(lines)} سطر من {filename}")
            return lines
    except Exception as e:
        print(f"خطأ في تحميل {filename}: {e}")
        return []

# تحميل الملفات النصية
content_files = {
    "سؤال": load_file_lines("questions.txt"),
    "تحدي": load_file_lines("challenges.txt"),
    "اعتراف": load_file_lines("confessions.txt"),
    "شخصي": load_file_lines("personality.txt"),
}

more_questions = load_file_lines("more_file.txt")

def load_games():
    try:
        with open("personality_games.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return [data[key] for key in sorted(data.keys())]
    except FileNotFoundError:
        print("ملف personality_games.json غير موجود")
        return []
    except json.JSONDecodeError as e:
        print(f"خطأ في تنسيق JSON: {e}")
        return []

games_list = load_games()

user_game_state = {}
user_content_indices = {key: {} for key in content_files.keys()}
global_content_indices = {key: 0 for key in content_files.keys()}
more_questions_index = 0

# نتائج مفصلة وطويلة لكل الألعاب
detailed_results = {
    "لعبة1": {
        "أ": "أنت شخص حنون ومتعاطف للغاية، تهتم بالآخرين وتبذل قصارى جهدك لإسعادهم.\nنقاط القوة: القدرة على التعاطف، الحب الصادق، والوفاء بالوعود.\nنقاط الضعف: قد تتعب جسديًا ونفسيًا بسبب التضحية المستمرة.\nنصائح: خصص وقتًا لنفسك، وتعلم قول 'لا' أحيانًا دون شعور بالذنب.",
        "ب": "شخصيتك متزنة وحكيمة، تفكر جيدًا قبل اتخاذ القرارات.\nنقاط القوة: الوعي الذاتي، التحليل الجيد، والقدرة على التكيف.\nنقاط الضعف: أحيانًا تميل للقلق الزائد قبل اتخاذ أي خطوة.\nنصائح: ثق بحدسك وامنح نفسك الفرصة لتجربة الأمور دون خوف.",
        "ج": "أنت شخص حساس وراقي، تدرك مشاعر الآخرين وتتعامل معها بعناية.\nنقاط القوة: الحساسية، الإبداع، القدرة على فهم الآخرين.\nنقاط الضعف: تتأثر بسهولة بالمواقف السلبية.\nنصائح: مارس التأمل وشارك مشاعرك مع أشخاص تثق بهم."
    },
    "لعبة2": {
        "أ": "تمتلك طاقة شخصية عالية وتستطيع التأثير على من حولك بسهولة.\nنقاط القوة: الحضور القوي، القدرة على القيادة، والإقناع.\nنقاط الضعف: قد تتسرع أحيانًا في الحكم على الأمور.\nنصائح: استمع للآخرين ولا تتجاهل التفاصيل الصغيرة.",
        "ب": "شخصيتك هادئة ومتزنة، تستطيع التعامل مع الضغوط بشكل ممتاز.\nنقاط القوة: الصبر، التحليل الجيد، الاستقرار النفسي.\nنقاط الضعف: أحيانًا تميل للانطواء وعدم التعبير عن نفسك.\nنصائح: شارك أفكارك ومشاعرك مع من تثق بهم.",
        "ج": "تحب التفكير الإبداعي والخروج عن المألوف، تبحث دائمًا عن طرق جديدة لحل المشكلات.\nنقاط القوة: الابتكار، المرونة، التفكير خارج الصندوق.\nنقاط الضعف: أحيانًا تعاني من التشتت وصعوبة التركيز.\nنصائح: ركز على هدف واحد في كل مرة وقم بتنظيم وقتك."
    },
    "لعبة3": {
        "أ": "أنت شخص اجتماعي، تحب تكوين الصداقات والتواصل مع الجميع.\nنقاط القوة: اللباقة، مهارات التواصل، القدرة على كسب الآخرين.\nنقاط الضعف: أحيانًا تضع مصالح الآخرين قبل مصالحك.\nنصائح: اهتم بنفسك أولاً قبل مساعدة الآخرين.",
        "ب": "شخصيتك مستقلة وتحب الاعتماد على نفسك في كل شيء.\nنقاط القوة: الاعتماد على الذات، الانضباط، التركيز.\nنقاط الضعف: أحيانًا تشعر بالوحدة أو الانعزال.\nنصائح: تواصل مع الآخرين واطلب الدعم عند الحاجة.",
        "ج": "أنت شخص خلاق وتحب التعبير عن أفكارك بطرق مبتكرة.\nنقاط القوة: الإبداع، التميز، التفكير خارج المألوف.\nنقاط الضعف: قد تميل للتشتت إذا لم تكن منظماً.\nنصائح: ضع خطط واضحة لتنظيم أفكارك."
    },
    "لعبة4": {
        "أ": "شخصيتك محبة للمغامرة وتجربة كل جديد.\nنقاط القوة: الشجاعة، حب الاستكشاف، الفضول.\nنقاط الضعف: قد تتسرع أحيانًا وتتخذ قرارات غير مدروسة.\nنصائح: خطط جيدًا قبل خوض أي تجربة جديدة.",
        "ب": "تمتلك روحًا قيادية، تستطيع تنظيم الفريق واتخاذ القرارات.\nنقاط القوة: القيادة، الثقة بالنفس، القدرة على اتخاذ القرار.\nنقاط الضعف: أحيانًا تكون صارمًا جدًا.\nنصائح: كن مرنًا واستمع لآراء الآخرين.",
        "ج": "أنت شخص صبور وهادئ، تستطيع مواجهة التحديات بهدوء.\nنقاط القوة: الصبر، التحكم في الانفعالات، التحليل الجيد.\nنقاط الضعف: أحيانًا تميل للانعزال عن الآخرين.\nنصائح: شارك مشاعرك ولا تحتفظ بكل شيء لنفسك."
    },
    "لعبة5": {
        "أ": "أنت طموح وتسعى دائمًا لتحقيق أهدافك.\nنقاط القوة: الطموح، التصميم، الإصرار.\nنقاط الضعف: قد تهمل الراحة وتعرض نفسك للإرهاق.\nنصائح: خصص وقتًا للراحة والاسترخاء.",
        "ب": "شخصيتك متعاونة وتحب مساعدة الآخرين.\nنقاط القوة: التعاون، التعاطف، روح الفريق.\nنقاط الضعف: أحيانًا تضحي بنفسك لأجل الآخرين.\nنصائح: تعلم وضع حدود للحفاظ على طاقتك.",
        "ج": "أنت شخص عقلاني، تعتمد على المنطق في اتخاذ القرارات.\nنقاط القوة: المنطق، التحليل، التركيز.\nنقاط الضعف: أحيانًا تنسى الجانب العاطفي في الحياة.\nنصائح: امنح نفسك الحرية للتعبير عن المشاعر."
    },
    "لعبة6": {
        "أ": "أنت متفائل بطبعك، ترى الجانب الإيجابي في كل الأمور.\nنقاط القوة: التفاؤل، القدرة على تحفيز الآخرين.\nنقاط الضعف: أحيانًا تغفل المخاطر المحتملة.\nنصائح: توازن بين التفاؤل والحذر.",
        "ب": "شخصيتك تحليلية، تحب التفكير قبل اتخاذ أي خطوة.\nنقاط القوة: التحليل الدقيق، الحذر، التخطيط الجيد.\nنقاط الضعف: قد تتأخر في اتخاذ القرارات.\nنصائح: ثق بحدسك عند الحاجة للتصرف بسرعة.",
        "ج": "أنت شخص متفرد وتحب الابتكار في كل شيء تقوم به.\nنقاط القوة: الابتكار، الخيال، التميز.\nنقاط الضعف: أحيانًا تواجه صعوبة في تنفيذ أفكارك.\nنصائح: ضع خطة عملية لأفكارك الإبداعية."
    },
    "لعبة7": {
        "أ": "أنت متفائل ومحب للحياة، تبحث دائمًا عن الجديد والممتع.\nنقاط القوة: الطاقة الإيجابية، القدرة على تشجيع الآخرين.\nنقاط الضعف: أحيانًا تتجاهل التفاصيل المهمة.\nنصائح: ركز على التفاصيل المهمة مع الحفاظ على روح التفاؤل.",
        "ب": "شخصيتك هادئة وتحب النظام في كل شيء.\nنقاط القوة: التنظيم، الالتزام، الدقة.\nنقاط الضعف: أحيانًا تكون صارمًا مع نفسك والآخرين.\nنصائح: تعلم المرونة والتسامح.",
        "ج": "أنت شخص اجتماعي وتحب التعاون والمشاركة.\nنقاط القوة: روح الفريق، التواصل، المشاركة.\nنقاط الضعف: أحيانًا تضحي براحتك لأجل الآخرين.\nنصائح: احرص على موازنة وقتك بين نفسك والآخرين."
    },
    "لعبة8": {
        "أ": "أنت شخص متفائل ويحب التشجيع والإيجابية.\nنقاط القوة: التحفيز، الطاقة الإيجابية، روح المبادرة.\nنقاط الضعف: أحيانًا تتسرع وتتجاهل التفاصيل.\nنصائح: ضع خطة قبل التنفيذ.",
        "ب": "شخصيتك عملية، تحب التنظيم والتخطيط.\nنقاط القوة: الانضباط، التنظيم، التركيز.\nنقاط الضعف: أحيانًا تكون صارمًا في الحكم على الآخرين.\nنصائح: امنح نفسك مرونة أكبر.",
        "ج": "أنت مبدع وتحب التجديد والابتكار.\nنقاط القوة: الابتكار، التفكير الإبداعي، التميز.\nنقاط الضعف: أحيانًا تشتت أفكارك.\nنصائح: نظم أفكارك قبل العمل."
    },
    "لعبة9": {
        "أ": "شخصيتك قيادية، تحب السيطرة واتخاذ القرارات.\nنقاط القوة: القيادة، الثقة بالنفس، التحفيز.\nنقاط الضعف: أحيانًا تكون صارمًا أو متسلطًا.\nنصائح: استمع للآخرين قبل اتخاذ القرارات.",
        "ب": "شخصيتك ودودة ومحبة، تجذب الآخرين بسهولة.\nنقاط القوة: اللباقة، التواصل، التعاطف.\nنقاط الضعف: أحيانًا تهمل نفسك لأجل الآخرين.\nنصائح: اهتم بنفسك قبل مساعدة الآخرين.",
        "ج": "أنت شخص هادئ ومتفكر، تحب التفكير العميق.\nنقاط القوة: التحليل، الصبر، القدرة على فهم المواقف المعقدة.\nنقاط الضعف: أحيانًا تتأخر في اتخاذ القرارات.\nنصائح: خذ وقتك قبل أي خطوة مهمة."
    },
    "لعبة10": {
        "أ": "أنت شخص متوازن وواعي، تستطيع موازنة حياتك بشكل جيد.\nنقاط القوة: التوازن، الحكمة، إدارة الوقت.\nنقاط الضعف: أحيانًا تميل للتردد.\nنصائح: ثق بنفسك وخذ قراراتك بثقة.",
        "ب": "شخصيتك مغامرة، تحب التحديات والمغامرة.\nنقاط القوة: الجرأة، روح المغامرة، الحماس.\nنقاط الضعف: أحيانًا تتسرع.\nنصائح: خطط قبل المخاطرة.",
        "ج": "أنت شخص صبور ومتفهم، تستطيع التعامل مع الآخرين بلطف.\nنقاط القوة: الصبر، التعاطف، القدرة على حل النزاعات.\nنقاط الضعف: أحيانًا تشعر بالإرهاق بسبب الآخرين.\nنصائح: خصص وقتًا لنفسك للاسترخاء."
    }
}

# باقي الكود كما في المثال السابق، بدون تغييرات:
commands_map = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة", "اسأل"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر", "زيادة"]
}

def find_command(text: str) -> typing.Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in commands_map.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

def create_main_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="شخصي", text="شخصي")),
        QuickReplyButton(action=MessageAction(label="أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="لعبة", text="لعبه")),
    ])

def get_content(command: str, user_id: str) -> str:
    file_list = content_files.get(command, [])
    if not file_list:
        return f"لا توجد بيانات متاحة في قسم '{command}' حالياً."
    index = global_content_indices[command]
    content = file_list[index]
    global_content_indices[command] = (index + 1) % len(file_list)
    user_content_indices[command][user_id] = global_content_indices[command]
    return content

def get_more_question(user_id: str) -> str:
    global more_questions_index
    if not more_questions:
        return "لا توجد أسئلة متاحة في قسم 'أكثر'."
    user_name = get_user_name(user_id)
    question = more_questions[more_questions_index]
    more_questions_index = (more_questions_index + 1) % len(more_questions)
    return f"{question}\n\n{user_name}"

def get_games_list() -> str:
    if not games_list:
        return "لا توجد ألعاب متاحة حالياً."
    titles = [
        "الألعاب المتاحة:",
        "1- أي نوع من القلوب تمتلك",
        "2- القوة الشخصية",
        "3- الحب والعلاقات",
        "4- السلام الداخلي",
        "5- الطموح والنجاح",
        "6- التفكير الإيجابي",
        "7- الصداقة والعلاقات الاجتماعية",
        "8- القرارات الحياتية",
        "9- الأحلام والطموحات",
        "10- الراحة النفسية",
        "أرسل رقم اللعبة للبدء (1-10)"
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
        f"إجابتك الأكثر: {most_common} نتيجتك تعكس شخصية فريدة."
    )
    stats = f"\nإحصائياتك:\nأ: {count['أ']} | ب: {count['ب']} | ج: {count['ج']}"
    return result_text + stats

@app.route("/", methods=["GET"])
def home():
    return "البوت يعمل بنجاح!", 200

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
    text_lower = text.lower()
    
    if text_lower in ["مساعدة", "help", "بداية", "start"]:
        welcome_msg = "اختر من القائمة أدناه:"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_msg, quick_reply=create_main_menu())
        )
        return
    
    command = find_command(text)
    if command:
        if command == "أكثر":
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
            user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
            user_name = get_user_name(user_id)
            first_q = games_list[game_index]["questions"][0]
            options = "\n".join([f"{k}. {v}" for k, v in first_q["options"].items()])
            msg = f"{games_list[game_index].get('title', f'اللعبة {num}')}\nاللاعب: {user_name}\n\n{first_q['question']}\n\n{options}\nأرسل: أ، ب، ج"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"اختر رقماً من 1 إلى {len(games_list)}"))
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
                msg = f"{progress} {q['question']}\n\n{options}\nأرسل: أ، ب، ج"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            else:
                user_name = get_user_name(user_id)
                result = calculate_result(state["answers"], state["game_index"])
                final_msg = f"انتهت اللعبة!\n{user_name}\n\n{result}\nأرسل 'لعبه' لتجربة لعبة أخرى!"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=final_msg, quick_reply=create_main_menu()))
                del user_game_state[user_id]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
