import json
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

# --- تحميل الملفات الأخرى ---
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

# --- تحميل الألعاب من ملف JSON ---
try:
    with open("personality_games.json", "r", encoding="utf-8") as f:
        games_data = json.load(f)
except Exception:
    games_data = {}

# ترتيب الألعاب حسب المفتاح
games_list = [games_data[key] for key in sorted(games_data.keys())]

# --- متابعة حالة كل مستخدم ---
user_game_state = {}  # user_id: {"game_index": 0, "question_index": 0, "answers": []}

# --- نصوص التحليل المفصل لكل لعبة ---
detailed_results = {
    "لعبة1": {
        "أ": """قلبك من ذهب وتضحي من دون تردد
أنت شخص مساند بطبيعتك، وتشعر الآخرين بالأمان.  
تمتلك القدرة على تقديم الدعم النفسي والمادي، وتضع راحة الآخرين قبل راحتك.  
قد تتعب أحيانًا بسبب التزامك تجاه الآخرين، لكن هذا جزء من شخصيتك النبيلة.  
تعلم كيف تحمي قلبك وطاقتك لمن يستحق فعلاً، وابتعد عن استغلال طيبتك.""",
        "ب": """قلبك نقي لكنه حذر
أنت تعطي بحدود وتحب بعقل، تعرف متى تقترب ومتى تبتعد.  
مشاعرك ناضجة وتتعامل مع الحياة بوعي، وتوازن بين الحب والاحتياط.  
خوفك أحيانًا يمنعك من الدخول في علاقات عميقة بسرعة، لكن هذا يجعلك تختار الأشخاص المناسبين.""",
        "ج": """قلبك مرهف كالزجاج لكنه قوي كالجبال
تشعر بكل شيء بعمق، وتؤثر بك الأحداث سريعًا.  
تتأثر بسهولة ولكن تتعافى بصمت، وتستفيد من تجاربك السابقة لتقوية شخصيتك.  
جرحك يترك أثرًا، لكنه يصقلك ويجعلك أكثر فهمًا لنفسك وللآخرين."""
    },
    "لعبة2": {
        "أ": """أنت شخص قوي التحمل
تواجه الصعوبات بثقة وصبر، ولا تستسلم بسهولة.  
تعتمد على نفسك لحل المشكلات، وتتعلم من كل تجربة لتعزيز قدراتك.  
قد يشعر البعض بصعوبة مواكبتك، لكن هذا يعكس عزيمتك وتصميمك.""",
        "ب": """القوة الاجتماعية هي سلاحك
تعتمد على دعم الآخرين، وتستفيد من العلاقات القوية في حياتك.  
تعرف متى تستشير ومتى تتحرك بمفردك.  
شخصيتك تحترم الآخرين وتكسب ثقتهم بسهولة.""",
        "ج": """القوة الداخلية والوعي الذاتي
تمتلك وعيًا عميقًا بنفسك وقدراتك، وتتعامل مع الحياة بتوازن.  
تدرك نقاط قوتك وضعفك، وتسعى لتطوير نفسك باستمرار.  
قد تبدو هادئًا للآخرين، لكن داخلك مليء بالإصرار والتركيز."""
    },
    "لعبة3": {
        "أ": """حب الأمان والثقة
أنت شخص يبحث عن الثبات والاعتماد على الشريك، وتولي أهمية كبيرة للثقة.  
تقدر الاستقرار العاطفي وتبحث عن علاقة قائمة على الاحترام والصدق.  
قد تكون حساسًا تجاه الخيانة أو الكذب، لذلك تختار شركاء حياتك بعناية.""",
        "ب": """حب المرح والضحك
تستمتع بالأوقات الممتعة والضحك مع الشريك، وتحب مشاركة السعادة.  
تبحث عن علاقة مليئة بالحيوية والطاقة الإيجابية.  
قد تتجنب الجدية أحيانًا، لكن توازن المرح مع الالتزام يظهر نضجك العاطفي.""",
        "ج": """حب التفاهم والدعم
أنت شخص يسعى للتفاهم العميق والدعم المتبادل.  
تقدر الحوار الصادق وتشعر بالمسؤولية تجاه مشاعر الآخرين.  
قد تتحمل الكثير من المشاعر، لكن هذا يجعلك شريكًا مخلصًا ومتفهمًا."""
    },
    "لعبة4": {
        "أ": """سلام الانعزال الذاتي
تميل للهدوء والتأمل، وتجد الراحة في وقتك الخاص.  
تتعامل مع الضغوط بالتفكير والتأمل الداخلي، وتعيد ترتيب أفكارك بهدوء.  
قد يراك الآخرون منعزلًا، لكنك تستخدم الوقت لتقوية نفسك.""",
        "ب": """سلام النشاط والحركة
تحب الانخراط في النشاطات والحركة للتخلص من التوتر.  
تعتمد على النشاط البدني أو الهوايات لتصفية ذهنك.  
هذه الطريقة تمنحك طاقة إيجابية وتوازنك النفسي.""",
        "ج": """سلام الرضا الداخلي
تركز على قبول ما لا يمكنك تغييره وتحقيق التوازن النفسي.  
تمتلك قدرة على التعامل مع الصعوبات بصبر ووعي.  
تتعلم من التجارب وتطور نفسك باستمرار للوصول لراحة داخلية حقيقية."""
    },
    "لعبة5": {
        "أ": """طموح شخصي مستقل
تسعى لتحقيق أهدافك بنفسك، وتعتمد على قوتك وإصرارك.  
تواجه التحديات دون الاعتماد الكامل على الآخرين، وتتعلم من كل تجربة.  
قد تكون صلبًا في اتخاذ القرارات، لكن هذا يضمن لك النجاح الحقيقي.""",
        "ب": """طموح اجتماعي
تسعى لتحقيق أهدافك بمشاركة الآخرين والدعم المتبادل.  
تؤمن بقوة الفريق والتعاون، وتقدر الأفكار المختلفة.  
شخصيتك متعاونة وتحب بناء علاقات قوية لتحقيق النجاح.""",
        "ج": """طموح مدروس وواعٍ
تخطط لكل خطوة بحكمة ووعي، وتوازن بين الطموح والواقعية.  
تعتمد على تقييم الفرص والمخاطر قبل اتخاذ القرار.  
تسعى لتحقيق الإنجازات بطريقة متزنة ومستدامة."""
    },
    "لعبة6": {
        "أ": """تفكير عملي وحل المشكلات
تعتمد على المنطق والتحليل، وتسعى لحل كل مشكلة بطريقة عملية.  
تستفيد من خبراتك وتجاربك لتجنب الأخطاء.  
قد يراك البعض عقلانيًا جدًا، لكن هذه الطريقة تجعلك فعالًا في حياتك.""",
        "ب": """تفكير اجتماعي ومشارك
تؤمن بقوة المشاركة ومساعدة الآخرين، وتستشير عند الحاجة.  
تسعى لتبادل الخبرات والمعرفة، وتقدر العلاقات الإنسانية.  
هذا التفكير يجعلك محبوبًا ومؤثرًا في محيطك.""",
        "ج": """تفكير هادئ ومتوازن
تميل للتفكير العميق واتخاذ القرارات بروية.  
توازن بين المشاعر والمنطق، وتبحث عن أفضل الحلول بهدوء.  
هذا يمنحك سلامًا داخليًا وقدرة على التعامل مع الحياة بثقة."""
    },
    "لعبة7": {
        "أ": """صديق مخلص ومسؤول
أنت دائمًا حاضر لمساعدة أصدقائك، وتتحمل المسؤولية عن علاقاتك.  
تعتمد على الصدق والوفاء، وتحب تقديم الدعم دون انتظار مقابل.  
قد يراك البعض صارمًا أحيانًا، لكن هذا يعكس إخلاصك وصدقك.""",
        "ب": """صديق مرح وممتع
تتمتع بروح مرحة، وتحب نشر السعادة بين أصدقائك.  
تعطي طاقة إيجابية وتساعد على التخفيف من التوتر.  
قد تبدو غير جدي أحيانًا، لكن أصدقاؤك يقدّرون مرونتك وروحك المرحة.""",
        "ج": """صديق هادئ ومتفاهم
تمتلك قدرة على الاستماع والتفهم، وتتعامل مع الأصدقاء بصبر ووعي.  
تفضل حل المشكلات بالحوار والهدوء، وتجنب الصراعات قدر الإمكان.  
هذا يجعل منك صديقًا يعتمد عليه ويثق بك الآخرون."""
    },
    "لعبة8": {
        "أ": """قرار سريع وواثق
تثق بحدسك وتتخذ القرارات بسرعة عند الحاجة.  
تعتمد على خبراتك ومعلوماتك دون تردد.  
قد تكون أحيانًا مندفعًا، لكن ثقتك بنفسك تساعدك على المضي قدمًا بثبات.""",
        "ب": """قرار تعاوني ومشترك
تستشير الآخرين قبل اتخاذ القرارات، وتقدر وجهات النظر المختلفة.  
تعمل على تحقيق توازن بين رأيك ورأي الآخرين.  
هذا يمنحك قرارات مدروسة وعادلة، ويكسبك احترام المحيطين.""",
        "ج": """قرار مدروس وواعٍ
تقوم بتحليل كل الخيارات بعناية قبل اتخاذ أي قرار.  
توازن بين المخاطر والفوائد، وتبحث عن الحل الأمثل للجميع.  
هذا يجعلك شخصًا حذرًا وموثوقًا في اتخاذ القرارات الهامة."""
    },
    "لعبة9": {
        "أ": """حلم شخصي مستقل
تركز على تحقيق أهدافك بنفسك، وتسعى لتطوير مهاراتك وقدراتك.  
تتمتع بالإصرار والمثابرة، وتواجه التحديات بثقة.  
هذا يضمن لك النجاح الذاتي ويجعلك قدوة لمن حولك.""",
        "ب": """حلم اجتماعي
تهتم بإسعاد الآخرين وتحقيق فرق في حياتهم.  
تقدر التعاون والمشاركة، وتسعى لترك أثر إيجابي في محيطك.  
هذا يعكس روحك الإنسانية ويجعل منك شخصًا محبوبًا وموثوقًا.""",
        "ج": """حلم متوازن وواعٍ
توازن بين طموحك الشخصي ومساعدة الآخرين.  
تسعى لتحقيق رضا داخلي واستقرار عاطفي، مع مراعاة محيطك الاجتماعي.  
هذا يمنحك رؤية واضحة ومستقبل متوازن."""
    },
    "لعبة10": {
        "أ": """سلام الانعزال الذاتي
تحب أن تكون مع نفسك لتجديد الطاقة والتركيز.  
تتعامل مع التوتر بضبط النفس والتأمل.  
تمتلك قدرة على التحليل الداخلي والتوازن النفسي.""",
        "ب": """سلام النشاط والحركة
تعتمد على النشاط البدني والهوايات للتخلص من التوتر.  
تجد في الحركة والطاقة الإيجابية وسيلة لتوازن حياتك.  
هذا يجعلك شخصًا نشيطًا ومليئًا بالحيوية.""",
        "ج": """سلام الرضا الداخلي
تركز على القبول الداخلي والتوازن النفسي.  
تعرف كيف تستفيد من تجاربك لتعيش بسلام ورضا.  
تتمتع بحكمة وقدرة على التعامل مع الصعوبات بهدوء."""
    }
}

# --- مؤشرات لكل مستخدم للأوامر الأخرى ---
user_indices = {"سؤال":{}, "تحدي":{}, "اعتراف":{}, "شخصي":{}, "أكثر":{}}
global_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0, "أكثر":0}

# --- قاموس المرادفات لكل أمر ---
commands_map = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر"]
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

    # --- مساعدة ---
    if text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال\n"
            "- شخصي\n"
            "- تحدي\n"
            "- اعتراف\n"
            "- أكثر\n"
            "- لعبه"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # --- أوامر الألعاب الأخرى ---
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

        if file_list:
            index = global_indices[command]
            msg = file_list[index]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            global_indices[command] = (index + 1) % len(file_list)
            user_indices[command][user_id] = global_indices[command]
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {command} حالياً."))
        return

    # --- بدء لعبة الشخصية ---
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

    # --- اختيار رقم اللعبة ---
    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(games_list):
            game_index = num - 1
            user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
            first_question = games_list[game_index]["questions"][0]
            options_text = "\n".join([f"{k}: {v}" for k, v in first_question["options"].items()])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{first_question['question']}\n{options_text}"))
        return

    # --- الرد على سؤال داخل اللعبة ---
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
                # نهاية اللعبة، عرض النتيجة المفصلة
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
