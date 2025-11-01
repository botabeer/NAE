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

# ملفات المحتوى
def load_file_lines(filename: str) -> typing.List[str]:
    if not os.path.exists(filename):
        print(f"الملف غير موجود: {filename}")
        return []
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        return lines

content_files = {
    "سؤال": load_file_lines("questions.txt"),
    "تحدي": load_file_lines("challenges.txt"),
    "اعتراف": load_file_lines("confessions.txt"),
    "شخصي": load_file_lines("personality.txt"),
}

more_questions = load_file_lines("more_file.txt")

# تحميل الألعاب
def load_games():
    try:
        with open("personality_games.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return [data[key] for key in sorted(data.keys())]
    except:
        return []

games_list = load_games()

user_game_state = {}
user_content_indices = {key: {} for key in content_files.keys()}
global_content_indices = {key: 0 for key in content_files.keys()}
more_questions_index = 0

# نتائج الألعاب العشر بدون رموز
detailed_results = {
    "لعبة1": {"أ": "قلبك من ذهب وتضحي بدون تردد. نقاط قوتك: التعاطف والحنان. انتبه: قد تتعب أحياناً بسبب التزامك.",
               "ب": "قلبك نقي لكنه حذر. نقاط قوتك: النضج العاطفي والوعي الذاتي. نصيحة: لا تدع تجاربك تمنعك من الانفتاح على الحب.",
               "ج": "قلبك مرهف كالزجاج لكنه قوي كالجبال. نقاط قوتك: الحساسية العالية والتعاطف العميق. نصيحة: احم قلبك جيداً."},
    "لعبة2": {"أ": "لديك طاقة شخصية قوية وقدرة على التأثير بالآخرين. نصيحة: استخدم قوتك بحكمة.",
               "ب": "شخصيتك متوازنة وهادئة، تستطيع التعامل مع التحديات بصبر وحكمة.",
               "ج": "تمتلك قدرة على الابتكار والتفكير خارج الصندوق. نصيحة: ركز على أهدافك لتحقيق أفضل النتائج."},
    "لعبة3": {"أ": "تميل للعلاقات العاطفية العميقة والمخلصة. نصيحة: تواصل بصدق مع شريك حياتك.",
               "ب": "تحب الاستقلالية في الحب وتقدر المساحة الشخصية. نصيحة: لا تنعزل كثيراً عن من تحب.",
               "ج": "شغوف ومغامر في العلاقات. نصيحة: كن صبوراً مع الطرف الآخر لتجنب سوء الفهم."},
    "لعبة4": {"أ": "تمتلك راحة داخلية كبيرة وتستمتع بالسلام النفسي. نصيحة: حافظ على توازنك.",
               "ب": "قد تشعر بالتوتر أحياناً، لكن لديك القدرة على التهدئة. نصيحة: خصص وقتاً لنفسك يومياً.",
               "ج": "تبحث دائماً عن التجارب الجديدة لتحقيق الرضا النفسي. نصيحة: تذكر أهمية الاستقرار أحياناً."},
    "لعبة5": {"أ": "طموحك لا حدود له وتسعى لتحقيق النجاح بسرعة. نصيحة: ضع خطة واقعية.",
               "ب": "تمتلك عزيمة قوية وقدرة على تحقيق أهدافك ببطء وثبات.",
               "ج": "تحب التحديات وتواجهها بحماس. نصيحة: اهتم بالتفاصيل لتجنب الأخطاء."},
    "لعبة6": {"أ": "تفكيرك إيجابي ويحفز من حولك. نصيحة: لا تسمح للتشاؤم بالتأثير عليك.",
               "ب": "تمتلك رؤية متفائلة متوازنة. نصيحة: استمر في تحفيز نفسك والآخرين.",
               "ج": "تميل أحياناً للقلق، لكنك قادر على التحول للتفكير الإيجابي بسرعة."},
    "لعبة7": {"أ": "تقدر الصداقة وتبني علاقات قوية. نصيحة: احرص على التواصل المستمر.",
               "ب": "شخص اجتماعي يحب المساعدة ويستمتع باللقاءات. نصيحة: ضع حدودك أحياناً.",
               "ج": "تمتلك شبكة واسعة من المعارف. نصيحة: ركز على الصداقات العميقة."},
    "لعبة8": {"أ": "قراراتك مدروسة وتبتعد عن التسرع. نصيحة: ثق بحدسك أحياناً.",
               "ب": "تميل للتفكير التحليلي قبل اتخاذ أي خطوة. نصيحة: لا تقيد نفسك بالخيارات التقليدية.",
               "ج": "تحب المخاطرة أحياناً وتتخذ قرارات سريعة. نصيحة: قيم العواقب قبل التنفيذ."},
    "لعبة9": {"أ": "تحلم كثيراً وتضع أهدافاً كبيرة. نصيحة: قسم أهدافك إلى خطوات صغيرة.",
               "ب": "تمتلك قدرة على تحويل أحلامك إلى خطط عملية. نصيحة: لا تتوقف عند أول عقبة.",
               "ج": "طموحك لا يعرف الحدود، تبحث عن فرص جديدة باستمرار."},
    "لعبة10":{"أ": "تمتلك راحة نفسية قوية وتستمتع باللحظة. نصيحة: حافظ على هدوئك في المواقف الصعبة.",
               "ب": "تتعامل مع الضغوط بهدوء وحكمة. نصيحة: خصص وقتاً للاسترخاء يومياً.",
               "ج": "قد تواجه بعض القلق، لكن لديك القدرة على الاسترخاء بسرعة بعد التحديات."}
}

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

# قائمة الأزرار مرتبة من اليمين إلى اليسار
def create_main_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="لعبة", text="لعبة")),
        QuickReplyButton(action=MessageAction(label="أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="شخصي", text="شخصي")),
        QuickReplyButton(action=MessageAction(label="اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="سؤال", text="سؤال")),
    ])

def get_content(command: str, user_id: str) -> str:
    file_list = content_files.get(command, [])
    if not file_list:
        return f"لا توجد بيانات متاحة في قسم '{command}' حالياً."
    index = global_content_indices[command]
    content = file_list[index]
    global_content_indices[command] = (index + 1) % len(file_list)
    return f"{get_user_name(user_id)}\n\n{content}"

def get_more_question(user_id: str) -> str:
    global more_questions_index
    if not more_questions:
        return "لا توجد أسئلة متاحة في قسم 'أكثر'."
    question = more_questions[more_questions_index]
    more_questions_index = (more_questions_index + 1) % len(more_questions)
    return f"{question}\n\n{get_user_name(user_id)}"

def get_games_list() -> str:
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
    count = {"أ":0,"ب":0,"ج":0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = detailed_results.get(game_key, {}).get(
        most_common, f"إجابتك الأكثر: {most_common} نتيجتك تعكس شخصية فريدة."
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
        welcome_msg = (
            "أهلاً بك في البوت!\n\n"
            "الأقسام المتاحة:\n"
            "سؤال - أسئلة ممتعة\n"
            "تحدي - تحديات\n"
            "اعتراف - اعترافات\n"
            "شخصي - أسئلة شخصية\n"
            "أكثر - أسئلة 'أكثر واحد'\n"
            "لعبة - ألعاب تحليل الشخصية\n\n"
            "اختر من القائمة أدناه:"
        )
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
        answer_map = {"1":"أ","2":"ب","3":"ج","a":"أ","b":"ب","c":"ج"}
        answer = answer_map.get(text_lower, text)
        if answer in ["أ","ب","ج"]:
            state["answers"].append(answer)
            game = games_list[state["game_index"]]
            state["question_index"] += 1
            if state["question_index"] < len(game["questions"]):
                q = game["questions"][state["question_index"]]
                options = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
                progress = f"[{state['question_index']+1}/{len(game['questions'])}]"
                msg = f"{progress} {q['question']}\n\n{options}\nأرسل: أ، ب، ج"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            else:
                user_name = get_user_name(user_id)
                result = calculate_result(state["answers"], state["game_index"])
                final_msg = f"انتهت اللعبة!\n{user_name}\n\n{result}\nأرسل 'لعبة' لتجربة لعبة أخرى!"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=final_msg, quick_reply=create_main_menu()))
                del user_game_state[user_id]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
