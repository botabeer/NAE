from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, typing, re

app = Flask(__name__)

# LINE credentials from environment
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Utility to load optional external lists
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personal.txt")

# Defaults if files missing
if not questions_file:
    questions_file = [
        "ما أكثر صفة تحبها في شريك حياتك؟",
        "ما أول شعور جاءك لما شفته لأول مرة؟",
        "لو تقدر تغير شيء في علاقتك، وش هو؟"
    ]
if not challenges_file:
    challenges_file = [
        "اكتب رسالة قصيرة تبدأ بـ: أحبك لأن...",
        "ارسل له صورة تمثل أجمل ذكرى عندك معه."
    ]
if not confessions_file:
    confessions_file = [
        "اعترف بأول شخص جذبك في حياتك.",
        "اعترف بأكثر عادة سيئة عندك."
    ]
if not personal_file:
    personal_file = [
        "تحب تبدأ يومك بالنشاط ولا بالهدوء؟",
        "هل تعتبر نفسك اجتماعي أم انطوائي؟"
    ]

# -------------------------
# Games: 10 games, each 10 Qs (formatted as requested)
# -------------------------
games: typing.Dict[str, typing.List[str]] = {
    "لعبه1": [
        "سؤال 1:\nأنت تمشي في غابة مظلمة وهادئة، فجأة تسمع صوت خطوات خلفك. ماذا تفعل؟\n1. تلتفت فورًا\n2. تسرع بخطواتك\n3. تتجاهل وتواصل طريقك\n4. تختبئ خلف شجرة",
        "سؤال 2:\nتصل إلى نهر يجري بسرعة. كيف تعبره؟\n1. تبني جسرًا صغيرًا\n2. تبحث عن مكان ضحل لعبوره\n3. تسبح من خلاله\n4. تنتظر حتى يهدأ التيار",
        "سؤال 3:\nرأيت كوخًا صغيرًا بين الأشجار. ماذا تفعل؟\n1. تقترب وتطرق الباب\n2. تدخل دون تردد\n3. تراقبه من بعيد\n4. تتجاوزه وتكمل طريقك",
        "سؤال 4:\nداخل الكوخ وجدت طاولة عليها مفتاح وورقة. ماذا تأخذ؟\n1. المفتاح\n2. الورقة\n3. كليهما\n4. لا تأخذ شيئًا",
        "سؤال 5:\nخرجت من الكوخ ووجدت طريقين. أي تختار؟\n1. طريق مضيء بالشمس\n2. طريق مظلم لكنه قصير\n3. طريق فيه أزهار\n4. طريق وعر لكنه آمن",
        "سؤال 6:\nسمعت صوت حيوان بري. ماذا تفعل؟\n1. تبتعد فورًا\n2. تختبئ\n3. تحاول معرفة نوع الحيوان\n4. تصرخ طلبًا للمساعدة",
        "سؤال 7:\nرأيت ضوءًا غريبًا في الأفق. ماذا تفعل؟\n1. تقترب منه بحذر\n2. تتجاهله\n3. تنتظر لترى ما سيحدث\n4. تركض نحوه بحماس",
        "سؤال 8:\nوجدت سلة فيها طعام. كيف تتصرف؟\n1. تأكل فورًا\n2. تشم الطعام لتتأكد\n3. لا تقترب منه\n4. تأخذها معك",
        "سؤال 9:\nحل الليل وأنت ما زلت في الغابة. أين تنام؟\n1. على الأرض\n2. فوق شجرة\n3. داخل كهف قريب\n4. تظل مستيقظًا حتى الصباح",
        "سؤال 10:\nصباحًا رأيت طريق العودة. هل ترجع؟\n1. نعم فورًا\n2. بعد أن تستكشف أكثر\n3. لا، أريد المغامرة\n4. أنتظر أن أجد أحدًا"
    ],
    "لعبه2": [
        "سؤال 1:\nاستيقظت على جزيرة غامضة لوحدك. ما أول ما تفعله؟\n1. تستكشف المكان\n2. تبحث عن ماء\n3. تصرخ طلبًا للمساعدة\n4. تجلس للتفكير",
        "سؤال 2:\nرأيت أثر أقدام على الرمل. ماذا تفعل؟\n1. تتبعها\n2. تتجاهلها\n3. تراقبها من بعيد\n4. تغطيها بالرمل",
        "سؤال 3:\nوجدت ثمرة غير معروفة. هل تأكلها؟\n1. نعم فورًا\n2. لا أقترب منها\n3. أختبرها أولًا\n4. أحتفظ بها",
        "سؤال 4:\nاقترب الليل ولا مأوى لديك. ماذا تفعل؟\n1. تبني مأوى بسيط\n2. تصعد على شجرة\n3. تشعل نارًا للحماية\n4. تظل مستيقظًا",
        "سؤال 5:\nسمعت أصوات غريبة من الغابة. ماذا تفعل؟\n1. تقترب منها\n2. تبتعد فورًا\n3. تراقب من بعيد\n4. تصرخ",
        "سؤال 6:\nوجدت قاربا صغيرًا. هل تستخدمه؟\n1. نعم فورًا\n2. أختبره أولًا\n3. أنتظر الصباح\n4. أبحث عن أدوات أخرى",
        "سؤال 7:\nظهر شخص غريب على الجزيرة. ماذا تفعل؟\n1. تتحدث معه\n2. تختبئ\n3. تراقبه من بعيد\n4. تهاجمه أولًا",
        "سؤال 8:\nبدأ المطر يهطل بشدة. كيف تتصرف؟\n1. تبحث عن كهف\n2. تغطي نفسك بأوراق\n3. تستمتع بالمطر\n4. تحاول إشعال نار",
        "سؤال 9:\nوجدت رسالة داخل زجاجة. ماذا تفعل؟\n1. تفتحها فورًا\n2. تحتفظ بها\n3. تتجاهلها\n4. ترسل واحدة مثلها",
        "سؤال 10:\nرأيت طائرة تمر فوقك. ماذا تفعل؟\n1. تلوّح لها\n2. تشعل نارًا لإشارة\n3. تصرخ\n4. تجلس تنتظر"
    ],
    "لعبه3": [
        "سؤال 1:\nأنت في مدينة جديدة. أول شيء تفعله؟\n1. تستكشف\n2. تبحث عن مطعم\n3. تبحث عن فندق\n4. تسأل الناس",
        "سؤال 2:\nرأيت إعلانًا غريبًا في الشارع. هل تتابعه؟\n1. نعم بحماس\n2. لا أهتم\n3. ألتقط له صورة\n4. أتجاهله",
        "سؤال 3:\nشخص عرض عليك عملًا غريبًا. هل تقبله؟\n1. نعم\n2. لا\n3. أسأله التفاصيل\n4. أؤجل القرار",
        "سؤال 4:\nأضاع طفل طريقه أمامك. ماذا تفعل؟\n1. تساعده فورًا\n2. تبحث عن والديه\n3. تتصل بالشرطة\n4. تتجاهله",
        "سؤال 5:\nضعت في أحد الأحياء. كيف تتصرف؟\n1. تسأل المارة\n2. تستخدم الخريطة\n3. تتجول حتى تجد الطريق\n4. تنتظر أحدًا يساعدك",
        "سؤال 6:\nبدأت السماء تمطر. كيف تتصرف؟\n1. تفتح المظلة\n2. تجري لمكان مغلق\n3. تستمتع بالمطر\n4. تكمل طريقك",
        "سؤال 7:\nوجدت محفظة في الطريق. ماذا تفعل؟\n1. تسلمها للشرطة\n2. تبحث عن صاحبها\n3. تتركها مكانها\n4. تأخذ المال فقط",
        "سؤال 8:\nرأيت شخصًا يراقبك. كيف تتصرف؟\n1. تراقبه أنت أيضًا\n2. تبتعد فورًا\n3. تواجهه وتسأله\n4. تتجاهله",
        "سؤال 9:\nصديقك تأخر عن الموعد. ما رد فعلك؟\n1. تغضب\n2. تنتظره\n3. تغادر\n4. تتصل به",
        "سؤال 10:\nانقطعت الكهرباء ليلاً. ماذا تفعل؟\n1. تشعل شمعة\n2. تستخدم هاتفك\n3. تخرج تتمشى\n4. تنام"
    ],
    # لعبه4..لعبه10 مختصرة كما في الطلب السابق (أضفتها كذلك كاملة)
    "لعبه4": [
        "سؤال 1:\nأمامك باب قصر قديم. تدخل؟\n1. أدخل مباشرة\n2. أراقب من الخارج\n3. أدعو شخصًا معي\n4. أعود لاحقًا",
        "سؤال 2:\nوجدت درجًا يؤدي للأسفل. تنزل؟\n1. نعم\n2. لا\n3. تتأكد من الضوء\n4. تبحث عن طريق آخر",
        "سؤال 3:\nوجدت مرآة تبدو غريبة. ماذا تفعل؟\n1. تنظر فيها\n2. تكسرها\n3. تلمسها\n4. تبتعد",
        "سؤال 4:\nرأيت غرفة مليئة بالكتب. ماذا تختار؟\n1. تفتح كتابًا قديمًا\n2. تأخذ واحدًا معك\n3. تتجاهلها\n4. تدعو أحدًا للمساعدة",
        "سؤال 5:\nصوت خطوات قربك، ماذا تفعل؟\n1. تراقب\n2. تختبئ\n3. تصرخ\n4. تتبع الصوت",
        "سؤال 6:\nوجدت صندوقًا مغلقًا. تفتحه؟\n1. نعم بحذر\n2. لا\n3. تبحث عن مفتاح\n4. تتركه",
        "سؤال 7:\nهناك رسمة على الحائط تبدو كرمز، ماذا تفعل؟\n1. تدرسها\n2. تلمسها\n3. تتجاهلها\n4. تأخذ صورة",
        "سؤال 8:\nرأيت نافذة تطل على بستان، ماذا تفعل؟\n1. تقف وتتأمل\n2. تقفز للخروج\n3. تغلقها\n4. تنادي شخصًا",
        "سؤال 9:\nوجدت خاتمًا براقًا، تلبسه؟\n1. نعم\n2. لا\n3. تضعه بحذر\n4. تتركه",
        "سؤال 10:\nالقصر يهتز قليلاً، ماذا تفعل؟\n1. تخرج فورًا\n2. تبحث عن مخرج آمن\n3. تنتظر لتهدأ الأمور\n4. تتصل بشخص"
    ],
    "لعبه5": [
        "سؤال 1:\nاستيقظت على كوكب جديد. أول ما تفعله؟\n1. تستكشف المشهد\n2. تبحث عن مأوى\n3. تجمع عينات\n4. تنتظر إشارات",
        "سؤال 2:\nوجدت نباتًا غريبًا، ماذا تفعل؟\n1. تلمسه\n2. تلتقط صورة\n3. تتجنبه\n4. تأخذ منه عينة",
        "سؤال 3:\nرأيت مخلوقًا صغيرًا. كيف تتصرف؟\n1. تقترب بحذر\n2. تبتعد\n3. تراقبه من بعيد\n4. تتواصل معه",
        "سؤال 4:\nتواجه فصل ليل غريب، ماذا تفعل؟\n1. تبني مأوى\n2. تشعل نارًا\n3. تواصل السير\n4. تستكشف المكان",
        "سؤال 5:\nوجدت جهازًا غريبًا، تضغط عليه؟\n1. نعم\n2. لا\n3. تدرسه أولًا\n4. تحطمه",
        "سؤال 6:\nتراودك رؤية ضوء بعيد، ماذا تفعل؟\n1. تذهب نحوه\n2. تراقب\n3. تقيس المسافة\n4. تعود",
        "سؤال 7:\nسمعت نغمة غريبة، ماذا تفعل؟\n1. تبحث عن مصدرها\n2. تتجاهلها\n3. تسجلها\n4. تنادي لمشاركة الصوت",
        "سؤال 8:\nوجدت بوابة، تدخل أم لا؟\n1. أدخل\n2. لا\n3. أنتظر\n4. أبحث عن معلومات",
        "سؤال 9:\nواجهتك مشكلة تقنية، كيف تحلها؟\n1. تجريبًا\n2. تخطيطًا\n3. تواصل مع الآخرين\n4. تتجاهلها",
        "سؤال 10:\nتوفرت وسيلة للعودة، تفعلها؟\n1. أعود\n2. أبقى للاستكشاف\n3. أشارك الاكتشاف\n4. أنتظر المساعدة"
    ],
    "لعبه6": [
        "سؤال 1:\nأنت على شاطئ واسع. ماذا تفعل أولاً؟\n1. تسبح\n2. تمشي على الرمال\n3. تبحث عن صدفة\n4. تجلس تتأمل",
        "سؤال 2:\nوجدت قاربًا صغيرًا، تستخدمه؟\n1. نعم\n2. لا\n3. تفتشه أولًا\n4. تنتظر مساعدة",
        "سؤال 3:\nوجدت خريطة بحرية قديمة. ماذا تفعل؟\n1. تتبعها\n2. تتركها\n3. تحفظها\n4. تظهرها للآخرين",
        "سؤال 4:\nرأيت ضوءًا في البحر ليلاً. ماذا تفعل؟\n1. تقترب\n2. تحذر الآخرين\n3. تبتعد\n4. تراقب",
        "سؤال 5:\nسمعت صوت غريب تحت الماء، كيف تتصرف؟\n1. تسبح نحوه\n2. تبتعد\n3. تسجل الصوت\n4. تبحث عن مصدره",
        "سؤال 6:\nعاصفة قادمة، ماذا تفعل؟\n1. تثبت القارب\n2. تصل للشاطئ\n3. تبتعد للبحر العميق\n4. تبني ملاذ",
        "سؤال 7:\nوجدت لؤلؤة نادرة، ماذا تفعل؟\n1. تأخذها\n2. تتركها\n3. تبيعها\n4. تهديها لأحد",
        "سؤال 8:\nشخص في الماء يحتاج مساعدة، ماذا تفعل؟\n1. تنقذه فورًا\n2. تنادي لإنقاذه\n3. تستخدم قاربًا\n4. تبحث عن معدات",
        "سؤال 9:\nوجدت مقبرة سفن قديمة، ما تفعل؟\n1. تستكشفها\n2. تتركها\n3. تجمع آثارًا\n4. تقرر العودة",
        "سؤال 10:\nرأيت جزيرة صغيرة على الخريطة، تذهب؟\n1. نعم\n2. لا\n3. تجهز نفسك\n4. تنتظر"
    ],
    "لعبه7": [
        "سؤال 1:\nدخلت كهفًا مظلمًا، ماذا تفعل أولاً؟\n1. تشعل مصباحًا\n2. تمشي بحذر\n3. تعود للخارج\n4. تنادي للتأكد من الأمان",
        "سؤال 2:\nوجدت نقوشًا على الجدار، ماذا تفعل؟\n1. تدرسها\n2. تلمسها\n3. تصورها\n4. تتجاهلها",
        "سؤال 3:\nسمعت صدى غريب، ماذا تفعل؟\n1. تتبع الصوت\n2. تبتعد\n3. تصرخ\n4. تنصت بهدوء",
        "سؤال 4:\nوجدت مياهًا جوفية، تشربها؟\n1. نعم\n2. لا\n3. تغليها أولًا\n4. تختبرها",
        "سؤال 5:\nرأيت فتحة أعلى، تصعد؟\n1. نعم\n2. لا\n3. تبحث عن سلم\n4. تنتظر مساعدة",
        "سؤال 6:\nوجدت درجًا ضيقًا، تنهض للصعود؟\n1. نعم\n2. لا\n3. تتأكد من ثباته\n4. تبحث عن بديل",
        "سؤال 7:\nرأيت غرفة مليئة بالبلورات، تأخذ قطعة؟\n1. نعم\n2. لا\n3. تلتقط صورة\n4. تسجل موقعها",
        "سؤال 8:\nتواجه صدعًا في الأرض، كيف تتصرف؟\n1. تتجنبه\n2. تحاول العبور\n3. تقيس عمقه\n4. تنادي للحصول على أدوات",
        "سؤال 9:\nسمعت حركة خلفك، ماذا تفعل؟\n1. تنعطف بسرعة\n2. تصرخ\n3. تختبئ\n4. تمشي بحذر نحوها",
        "سؤال 10:\nوجدت مخبأ قديم، تدخل؟\n1. نعم بحذر\n2. لا\n3. تفتح من بعيد\n4. تنتظر"
    ],
    "لعبه8": [
        "سؤال 1:\nأنت في مدرسة قديمة، ماذا تفعل أولاً؟\n1. تدخل صفًا\n2. تسأل عن المكتبة\n3. تبحث عن المدرسين\n4. تتجول",
        "سؤال 2:\nوجدت دفتر ملاحظات غريب، ماذا تفعل؟\n1. تقرأه\n2. تغلقه\n3. تأخذ ملاحظة فقط\n4. تتركه",
        "سؤال 3:\nأستاذ يعرض مسابقة غريبة، تشارك؟\n1. نعم\n2. لا\n3. تسأل عن المكافأة\n4. تؤجل القرار",
        "سؤال 4:\nرأيت مجموعة تتناقش، تنضم؟\n1. نعم\n2. لا\n3. تراقب أولًا\n4. تسأل عن الموضوع",
        "سؤال 5:\nوجدت غرفة سرية، تدخل؟\n1. نعم\n2. لا\n3. تطرق الباب\n4. تبحث عن مفتاح",
        "سؤال 6:\nامتحان مفاجئ، كيف تتصرف؟\n1. تركز وتجيب\n2. تحاول الغش\n3. تخرج\n4. تسأل عن الوقت",
        "سؤال 7:\nوجدت كتاب قديم في الخزانة، ماذا تفعل؟\n1. تدرسه\n2. تتركه\n3. تأخذ منه ملاحظة\n4. تعرضه للآخرين",
        "سؤال 8:\nرأيت لوحة فنية غريبة، ماذا تفعل؟\n1. تدرسها\n2. تصورها\n3. تتجاهلها\n4. تسأل عنها",
        "سؤال 9:\nصديقك يحتاج مساعدة في الواجب، تساعده؟\n1. نعم فورًا\n2. تشرح له خطوات\n3. ترفض\n4. توجهه لشرح آخر",
        "سؤال 10:\nانتهت المدرسة فجأة، ماذا تفعل؟\n1. تضحك وتخرج\n2. تجلس للتفكير\n3. تبحث عن سبب\n4. تسأل المعلمين"
    ],
    "لعبه9": [
        "سؤال 1:\nاستيقظت في مستقبل مختلف، ماذا تفعل أولاً؟\n1. تستكشف التكنولوجيا\n2. تبحث عن معلومات\n3. تحاول التواصل مع الآخرين\n4. تراقب بصمت",
        "سؤال 2:\nوجدت جهازًا يمكنه تغيير الذاكرة، تستخدمه؟\n1. نعم\n2. لا\n3. تجرب جزءًا صغيرًا\n4. تدرسه أولًا",
        "سؤال 3:\nرأيت آلة تستطيع السفر عبر الزمن، تذهب؟\n1. نعم\n2. لا\n3. تذهب لمحاولة قصيرة\n4. تتركها",
        "سؤال 4:\nالعالم يحتاج قرارًا مهمًا، تتدخل؟\n1. نعم بقوة\n2. لا تترك الخبراء\n3. تقدم اقتراحًا صغيرًا\n4. تراقب الانتقادات",
        "سؤال 5:\nوجدت عملًا بمستقبل مشرق، تقبله؟\n1. نعم\n2. لا\n3. تسأل عن التفاصيل\n4. تؤجل",
        "سؤال 6:\nتقابل روبوتًا ودودًا، كيف تتعامل؟\n1. تتعاون معه\n2. تراقبه\n3. تختبره\n4. تبتعد",
        "سؤال 7:\nتواجه مشكلة تقنية كبرى، كيف تحلها؟\n1. تُجرّب حلولًا مبتكرة\n2. تعتمد على فريق\n3. تستشير خبراء\n4. تؤجل للحظة أخرى",
        "سؤال 8:\nرأيت مدينة عائمة، تدخل؟\n1. نعم\n2. لا\n3. تدرس نظامها\n4. تراقب من الخارج",
        "سؤال 9:\nاقتراح تغييرات جذرية على المجتمع، تؤيده؟\n1. نعم\n2. لا\n3. أدرس التبعات\n4. أرفض لأسباب أخلاقية",
        "سؤال 10:\nوجدت فرصة للعودة للحاضر، تفعل؟\n1. أعود\n2. أبقى\n3. أرسل تقريرًا\n4. أنتظر فرصة أفضل"
    ],
    "لعبه10": [
        "سؤال 1:\nدخلت إلى حلم غريب، ماذا تفعل؟\n1. تستكشف المشاهد\n2. تحاول الاستيقاظ\n3. تتبع العناصر الغريبة\n4. تستمتع بالحلم",
        "سؤال 2:\nتحدث مع شخصية من أحلامك، ماذا تقول؟\n1. أسأل عن سبب وجودها\n2. أستمر بالحديث\n3. أتركها تمضي\n4. أطلب نصيحة",
        "سؤال 3:\nوجدت باب داخل الحلم، تفتحه؟\n1. نعم\n2. لا\n3. تراقبه\n4. تتركه",
        "سؤال 4:\nالحلم يتحول إلى كابوس، كيف تواجهه؟\n1. أقاوم بشجاعة\n2. أهرب\n3. أبحث عن مخرج\n4. أصحو من النوم",
        "سؤال 5:\nرأيت رمزًا متكررًا، ماذا تفعل؟\n1. تبحث عن تفسير\n2. تتجاهله\n3. ترسمه\n4. تسجل الحلم",
        "سؤال 6:\nشعور مفاجئ بالسقوط، كيف تتصرف؟\n1. أستيقظ\n2. أستمتع بالإحساس\n3. أحاول التحكم\n4. أبحث عن سبب",
        "سؤال 7:\nالتقيت بنفسك في الحلم، ماذا تفعل؟\n1. أتحدث معها\n2. أراقبها\n3. أهرب\n4. أتعلم منها",
        "سؤال 8:\nوجدت رسالة مشفرة، تفتحها؟\n1. نعم\n2. لا\n3. أحللها أولًا\n4. أتركها",
        "سؤال 9:\nالحلم يوفر خيار للبقاء فيه، تفعل؟\n1. أبقى\n2. أعود\n3. أؤجل القرار\n4. أشارك الآخرين",
        "سؤال 10:\nاستيقظت وعندك تذكّر غريب، تفعل؟\n1. تدون الأفكار\n2. تتجاهلها\n3. تشاركها مع أحد\n4. تبحث عن معنى"
    ]
}

# -----------------------------
# Group sessions structure
# -----------------------------
# group_sessions[group_id] = {
#   "game": "لعبهX",
#   "players": { user_id: {"step": int, "answers": [ (q_index, chosen_num, chosen_text) ] } },
#   "state": "joining"
# }
group_sessions: typing.Dict[str, typing.Dict] = {}

# -----------------------------
# Keyword maps for smart scoring
# -----------------------------
# map type keys to list of Arabic keywords likely to indicate that trait
KEYWORDS = {
    "قيادية": [
        r"\bتدخل\b", r"\bتقترب\b", r"\bتسرع\b", r"\bتركض\b", r"\bأهاجم\b", r"\bأقبل\b",
        r"\bأذهب\b", r"\bأقوم\b", r"\bأبدأ\b", r"\bأقود\b", r"\bأواجه\b", r"\bأتحرك\b"
    ],
    "تعبيرية": [
        r"\bأتحدث\b", r"\bأتواصل\b", r"\bأشارك\b", r"\bألوّح\b", r"\bأضحك\b", r"\bأغني\b",
        r"\bأعبر\b", r"\bأتعاطف\b", r"\bأتقابل\b", r"\bأتفاعل\b", r"\bأقترب\b"
    ],
    "تحليلية": [
        r"\bأبحث\b", r"\bأخطط\b", r"\bأفحص\b", r"\bأدرس\b", r"\bأقيس\b", r"\bأتحقق\b",
        r"\bأستخدم\b", r"\bأحسب\b", r"\bأحلل\b", r"\bأجرب\b", r"\bأختبر\b"
    ],
    "داعمة": [
        r"\bأساعد\b", r"\bأساند\b", r"\bأنتظر\b", r"\bأعتني\b", r"\bأدعم\b", r"\bأحمي\b",
        r"\bأحفظ\b", r"\bأحتفظ\b", r"\bأقف مع\b", r"\bأهتم\b", r"\bأشارك\b"
    ]
}

# The four long descriptions as provided by user (exact/near-exact)
DESCRIPTIONS = {
    "قيادية": (
        "الشخصية القيادية\n\n"
        "ربما يكون نمط الشخصية القيادية معروفاً عند الغالبية، والذي يتسم بالاستقلالية والقيادة المستمرة، "
        "إلى جانب تحمّل المسؤولية، والقدرة على تحقيق الأهداف، وتنفيذ المهام بفاعليّة، كما يمتلك صاحبها رغبة قوية "
        "بفرض السيطرة والتحكم بالآخرين والأمور المحيطة، وغالباً ما يكون عمليّاً ومُحبّاً للمنافسة، "
        "ولا يهتمّ بالتفاصيل، بل ينصبُّ تركيزه أكثر على النتائج."
    ),
    "تعبيرية": (
        "الشخصية التعبيرية\n\n"
        "المعروفة أيضاً بالشخصية الاجتماعية، وهي تتميز بقدرة صاحبها على التفاعل مع الآخرين، "
        "والاستمتاع بالتواصل الاجتماعي والمشاركة في الأنشطة المجتمعية، كما يتسم بالود والعفوية والانفتاح على الاختلاف، "
        "وإظهار التعاطف مع الآخرين، والمرونة في التعامل."
    ),
    "تحليلية": (
        "الشخصية التحليلية\n\n"
        "عادةً ما يتميز صاحب الشخصية التحليلية بالعقلانية، وتركيزه على التفاصيل، واعتماده على المنطق في تحليل المعلومات "
        "وامتلاكه مهارات اتخاذ القرارات، كما يميل إلى التفكير الدقيق، والتحقق من مختلف النّواحي قبل اتخاذ أي خطوة."
    ),
    "داعمة": (
        "الشخصية الداعمة\n\n"
        "يظن البعض أنّ الشخصيات الداعمة والشخصيات الاجتماعية تتقارب كثيراً؛ فعادة ما يظلّ أصحابها على تواصل دائم مع الآخرين "
        "ويقدمون لهم الدعم والمساعدة، إلا أنّ الشخصيات الداعمة في الواقع غالباً ما تكون أكثر خجلاً، وتُفضّل الاستقرار والهدوء."
    )
}

# -----------------------------
# Helper: extract option text given game key, question index and chosen number
# -----------------------------
def extract_option_text(game_key: str, q_index: int, chosen: int) -> str:
    """
    Each question string is formatted like:
    "سؤال N:\nQuestion text\n1. opt1\n2. opt2\n3. opt3\n4. opt4"
    This function extracts the chosen option text (Arabic) for scoring.
    """
    try:
        q = games[game_key][q_index]
    except Exception:
        return ""
    # split lines, find lines that start with "1." "2." etc or "1. " etc
    lines = q.splitlines()
    # consider variations "1." or "1. " or "1)"
    pattern = re.compile(rf"^\s*{chosen}\s*[\.\)\-:]\s*(.+)$")
    for line in lines:
        m = pattern.match(line)
        if m:
            return m.group(1).strip()
    # fallback: try to find numbered options anywhere
    # find all options using regex
    opts = re.findall(r"\n\s*\d+\s*[\.\)\-:]\s*([^\n]+)", q)
    if opts and 1 <= chosen <= len(opts):
        return opts[chosen-1].strip()
    return ""

# -----------------------------
# Scoring: returns chosen personality key among four
# -----------------------------
def score_answers_to_personality(answers: typing.List[typing.Tuple[int,int,str]]) -> str:
    """
    answers: list of tuples (q_index, chosen_number, chosen_text)
    We check keywords in chosen_text for each personality. If none match, we fallback to chosen_number mapping.
    """
    scores = {"قيادية":0, "تعبيرية":0, "تحليلية":0, "داعمة":0}

    for q_index, chosen_num, chosen_text in answers:
        txt = (chosen_text or "").lower()
        matched = False
        # check keywords for each personality
        for trait, kws in KEYWORDS.items():
            for kw in kws:
                # regex search
                try:
                    if re.search(kw, txt):
                        scores[trait] += 1
                        matched = True
                        break
                except re.error:
                    continue
            if matched:
                break
        if not matched:
            # fallback heuristic by chosen number distribution:
            # map: 1 -> قيادية, 2 -> تحليلية, 3 -> تعبيرية, 4 -> داعمة
            if chosen_num == 1:
                scores["قيادية"] += 1
            elif chosen_num == 2:
                scores["تحليلية"] += 1
            elif chosen_num == 3:
                scores["تعبيرية"] += 1
            elif chosen_num == 4:
                scores["داعمة"] += 1

    # choose max
    sorted_by_score = sorted(scores.items(), key=lambda x: (-x[1], ["قيادية","تعبيرية","تحليلية","داعمة"].index(x[0])))
    top_trait, top_score = sorted_by_score[0]
    # if top score is zero (no info), default to 'تعبيرية' (neutral friendly)
    if top_score == 0:
        return "تعبيرية"
    return top_trait

# -----------------------------
# Build final analysis text (no points, only descriptive text per user request)
# -----------------------------
def build_final_analysis_text(name: str, trait_key: str) -> str:
    desc = DESCRIPTIONS.get(trait_key, "")
    return f"{name}\n\n{desc}"

# -----------------------------
# LINE Webhook endpoint
# -----------------------------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# -----------------------------
# Message handler
# -----------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    source = event.source
    user_id = source.user_id
    group_id = getattr(source, "group_id", None)  # None if private chat
    text_raw = event.message.text.strip()
    text = text_raw.strip()

    # ---- basic commands (works anywhere) ----
    if text == "مساعدة":
        help_text = (
            "أوامر البوت:\n"
            "- سؤال → سؤال.\n"
            "- تحدي → تحدي.\n"
            "- اعتراف → اعتراف.\n"
            "- اسئلة شخصية → سؤال شخصي عشوائي.\n"
            "- لعبهN (مثال: لعبه1) → يبدأ جلسة لعبة جماعية في القروب.\n"
            "  بعد بدء اللعبة: كل عضو يكتب 'ابدأ' للانضمام ثم يجيب بالأرقام 1-4.\n"
            "- البوت يتجاهل أي رسائل خارج الأوامر أو الجلسات."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if text == "سؤال":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(questions_file)))
        return

    if text == "تحدي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(challenges_file)))
        return

    if text == "اعتراف":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(confessions_file)))
        return

    if text == "اسئلة شخصية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(personal_file)))
        return

    # ---- start group game ----
    if group_id and text.startswith("لعبه"):
        if text not in games:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب لعبه1 حتى لعبه10 لبدء لعبة."))
            return
        # create group session
        group_sessions[group_id] = {"game": text, "players": {}, "state": "joining"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=(f"تم بدء الجلسة: {text}\n"
                  "كل عضو يرسل 'ابدأ' للانضمام. بعد الانضمام أجب بالأرقام 1-4 على كل سؤال.\n"
                  "البوت سيعطي تحليل مفصّل باسم كل لاعب مباشرة بعد إكماله للأسئلة.")
        ))
        return

    # ---- join session ----
    if group_id and text == "ابدأ":
        gs = group_sessions.get(group_id)
        if not gs or gs.get("state") != "joining":
            return
        players = gs["players"]
        if user_id in players:
            # resend current question
            player = players[user_id]
            step = player["step"]
            q = games[gs["game"]][step]
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q}"))
            return
        # register new player
        players[user_id] = {"step": 0, "answers": []}  # answers: list of tuples (q_index, chosen_num, chosen_text)
        try:
            name = line_bot_api.get_profile(user_id).display_name
        except:
            name = "عضو"
        q0 = games[gs["game"]][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q0}"))
        return

    # ---- player answering during session ----
    if group_id and group_id in group_sessions and user_id in group_sessions[group_id]["players"]:
        gs = group_sessions[group_id]
        player = gs["players"][user_id]
        # extract number from reply (digit or contains digit)
        ans_num = None
        txt = text.strip()
        if txt.isdigit() and 1 <= int(txt) <= 4:
            ans_num = int(txt)
        else:
            # find solitary number or "1." or "1 " etc
            m = re.search(r"\b([1-4])\b", txt)
            if m:
                ans_num = int(m.group(1))
        if ans_num is None:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب رقم الخيار فقط من 1 إلى 4."))
            return

        # get chosen option text for scoring
        q_index = player["step"]
        game_key = gs["game"]
        chosen_text = extract_option_text(game_key, q_index, ans_num)
        # record answer
        player["answers"].append( (q_index, ans_num, chosen_text) )
        player["step"] += 1

        # next question or finalize for this player
        if player["step"] < len(games[game_key]):
            next_q = games[game_key][player["step"]]
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{next_q}"))
            return
        else:
            # player finished -> compute personality and send detailed description with their name
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            trait = score_answers_to_personality(player["answers"])
            final_text = build_final_analysis_text(name, trait)
            # send to group (push so all see it)
            line_bot_api.push_message(group_id, TextSendMessage(text=final_text))
            # remove player from session so they can play again if wanted
            del gs["players"][user_id]
            return

    # otherwise ignore non-commands (per requirement)
    return

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
