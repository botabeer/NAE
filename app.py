# app.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction,
    PostbackEvent, PostbackAction
)
import random, os, urllib.parse

app = Flask(__name__)

# ------------------ ضبط مفاتيح LINE من متغيرات البيئة ------------------
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("❌ حط متغيرات البيئة LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ------------------ ذاكرات مؤقتة لتتبع المستخدمين ------------------
user_asked_questions = {}    # user_id -> set()  (صراحة)
user_asked_confessions = {}  # user_id -> set()  (اعتراف)
user_asked_challenges = {}   # user_id -> set()  (تحدي)

# تحليل الشخصية: حالة كل مستخدم أثناء الاختبار
# user_analysis_progress[user_id] = {"questions": [indices], "current": int, "scores": {trait:count}}
user_analysis_progress = {}

# ------------------ قوائم الأسئلة (عامية سعودية) ------------------
# ==== 100 سؤال صراحة/جرأة
truth_questions = [
"وش أكثر شي تخاف تخسره؟",
"وش آخر كذبة قلتها؟",
"اعترف بشي لما أحد مو موجود",
"هل عمرك غرمت في شخص بدون سبب واضح؟",
"وش أكثر شي يزعجك في العلاقة؟",
"هل تراقب جواله لو يجلس بعيد؟",
"هل ممكن تكذب عشان تهون موقف؟",
"وش أكثر موقف محرج صار لك مع شريكك؟",
"هل سبق تعبان من العلاقة؟",
"وش أكثر شيء تبغاه من شريكك؟",
"هل تبي تهجر الشخص اللي تحبه لو زعلت؟",
"هل فكرت تطلق مجرد تفكير؟",
"هل تحب تفاجئه برسالة حب فجأة؟",
"كم مرة خليته ينتظر وانت متعمد؟",
"وش أسوا تصرف سويتوه مع بعض؟",
"هل سويت مقلب مزح قوي على شريكك؟",
"هل تفضّل تصارحه أو تكتم مشاعرك؟",
"هل تعلّق بسرعة على ناس جداد؟",
"هل سبق قللت من أهمية مشاعره؟",
"هل تعتقد إن الحب يحتاج تضحيات كبيرة؟",
"هل تحب إنكم تتكلمون كل يوم؟",
"هل تتضايق لو تكرر نفس الكلام؟",
"هل تقدر تعيش بدون اهتمام يومين؟",
"هل تحب المفاجآت الكبيرة ولا البسيطة؟",
"هل تحب تهدي هدية ولا كلام رومانسي؟",
"هل سبق حاولت تغير نفسك عشان أحد؟",
"هل تحب تعبر بالمواقف ولا بالكلام؟",
"هل تبين مشاعرك بسرعة؟",
"هل تحب تبادر في المصالحة ولا تنتظر؟",
"هل تميل للكبت ولا للتفريغ؟",
"هل تفضّل الأنشطة الهادية ولا المغامرات؟",
"هل تهتم برأي أهلك في شريكك؟",
"هل تحب تعرف كل تفاصيل يومه؟",
"هل تقدر تنسى زعل بسهولة؟",
"هل تحب الإهتمام اليومي ولا المناسبات؟",
"هل تتضايق من الجدل الطويل؟",
"هل تفضّل الكلام الصريح حتى لو جارح؟",
"هل تعمل لها مفاجآت بدون مناسبة؟",
"هل تحب إنكم تشاهدون نفس الأفلام؟",
"هل تفضّل الهدايا المفيدة ولا الغريبة؟",
"هل تحب تجهز له شي بنفسك؟",
"هل تحب تغير روتينكم من وقت لوقت؟",
"هل تحب الإيماءات الصغيرة أكثر من الكلام؟",
"هل تنام وتبقى زعلان؟",
"هل تحب تداوم على عبارات الحب؟",
"هل هي مهمة أكثر من بعض الشي؟",
"هل ممكن تعطي فرصة بعد غلط كبير؟",
"هل تحب تشارك مخططاتك معه؟",
"هل تهاب الاعتذار لكرامتك؟",
"هل تستشير قبل اتخاذ قرارات كبيرة؟",
"هل تدي حدود للعلاقات الثانية؟",
"هل تظن إن الغيرة دليل اهتمام؟",
"هل تقدر تتخلى عن شيء مهم عشانها؟",
"هل تحب تستلم هدايا؟",
"هل تفضّل المكالمات الطويلة ولا الرسائل؟",
"هل عندك عادة غريبة يحبها؟",
"هل تشاهد محادثاته لو تقدر؟",
"هل تحب التواصل المسائي أكثر من الصباح؟",
"هل تحب الاحتفال بأشياء بسيطة؟",
"هل تحب تخطط لمستقبلك معاه؟",
"هل تندم على أول علاقة لك؟",
"هل تؤمن بالحب من أول نظرة؟",
"هل تظن تقلب المزاج يؤثر بالعلاقة؟",
"هل تحب تلقى اهتمامه بسرعة؟",
"هل تكره المبالغة بالحب؟",
"هل تحب تكتب رسالة طويلة له؟",
"هل تحب المفاجآت بالليل ولا الصباح؟",
"هل تشعر أنه يقرأ أفكارك؟",
"هل تتوقع منه مواقف رومانسية دايم؟",
"هل ترد بسرعة على رسالته؟",
"هل تحب تبتسم قدام الناس عشان يفرح؟",
"هل تقدّر الأشياء الصغيرة؟",
"هل تظن إن الحب يتغسل بالغضب؟",
"هل تحب تشاركه وقتك لو تعب؟",
"هل تفضل نزهة بسيطة ولا سفر؟",
"هل تحب تجرّب أشياء جديدة معه؟",
"هل تبي يكون عندك مساحة شخصية؟",
"هل تحب تقابله كل يوم؟",
"هل تهتم بتربيته أو شخصيته؟",
"هل تحب انك تكون دايمًا جنب اللي تحبه؟",
"هل تبدي حبك بكلام مختصر ولا تفاصيل؟",
"هل تحب تبين اهتمامك قدام أهله؟",
"هل تفضل يحل المشكلة ولا يعاتبك؟",
"هل تتأثر بأقل كلمة تقال؟",
"هل تظن إن الوقت يغير المشاعر؟",
"هل تبي تكون بدايه علاقتكم قصة تحب تذكرها؟",
"هل تحب تخلي العلاقة طبيعية ولا عرض؟",
"هل تفضّل نقاش منطقي ولا شعوري؟",
"هل ممكن تثق بسرعة؟",
"هل تحب إنكم تتكلمون بصراحة عن المال؟",
"هل تظن إن الصراحة عنوان لكل شيء؟"
]

# ==== 100 اعتراف
confession_questions = [
"اعترف بأول حب في حياتك",
"اعترف بشي سويتنه وانت صغیر وخجلان منه",
"اعترف بحاجة مخفيه للحين",
"اعترف بأكثر مرة بكیت من الفرح",
"اعترف بحاجة جرّبتها وما قلتها لأحد",
"اعترف بالتصرف اللي ندمت عليه",
"اعترف بأقرب شخص أثّر فيك",
"اعترف بحاجة غريبة تحبها",
"اعترف بأول كلمة حب قلتها",
"اعترف بحاجة تفتخر فيها بس قليل يعرف",
"اعترف بأغرب حلم صار لك عن حب",
"اعترف بأول مرة حسیت فيها بالخجل قدام حد",
"اعترف بحاجة تمنیت لو ترجع",
"اعترف بحاجة غیرتها عبثیة",
"اعترف بحاجة تبی تعتذر لها",
"اعترف بحاجة ما کنت مستعد أحكيلها",
"اعترف بحاجة تحسها ضعف عندك",
"اعترف بحاجة سوت لك تأثر شدید",
"اعترف بحاجة غیرت قرارك فی الحیاة",
"اعترف بحاجة تشتاق لها لحد الحين",
"اعترف بحاجة مادیة توفت ببالك دايم",
"اعترف بحاجة كنت تخبی عن عائلتك",
"اعترف بحاجة سويتھا باندفاع",
"اعترف بحاجة ما تقدر توصفها بكلمات",
"اعترف بحاجة تخاف لو الناس عرفوها",
"اعترف بحاجة كنت تبی تقولها وقتها",
"اعترف بحاجة غیرت فیك نَظَرتك للحب",
"اعترف بحاجة تضحك لما تتذكرها",
"اعترف بحاجة جرّبتها وخفت منها",
"اعترف بحاجة تشوفها علامة في حياتك",
"اعترف بحاجة تخاف تعترف بها",
"اعترف بحاجة ما قد حكیتها لحد",
"اعترف بحاجة خفِیة من طفولتك",
"اعترف بحاجة غیرت معنیك الحیاة",
"اعترف بحاجة قویة ما توقعتها",
"اعترف بحاجة قلّتك تعتقدها ممكنة",
"اعترف بحاجة تعتبرها نقطة تحوّل",
"اعترف بحاجة تمنیت لو تعلم الناس فيها",
"اعترف بحاجة خلّت عندك أثر دائم",
"اعترف بحاجة تعتقد انها تساعد الناس",
"اعترف بحاجة كنت تتمنى اعادة الزمن",
"اعترف بحاجة سببت لك اندهاش",
"اعترف بحاجة مشتاق ترجع لها",
"اعترف بحاجة حسيتها ضعف وانتهیت لصالحك",
"اعترف بحاجة تظنها غلطة لكن تعلمت منها",
"اعترف بحاجة تمنیت لو قلتها وقبلها",
"اعترف بحاجة تمنیت لو اديت لها حقها",
"اعترف بحاجة سرّیة لحد الآن",
"اعترف بحاجة بتضحك الناس لو عرفوها",
"اعترف بحاجة كانت بداية قصة جديدة",
"اعترف بحاجة جرّبت تخففها بالضحك",
"اعترف بحاجة تمنیت لو كان حد جنبك وقتها",
"اعترف بحاجة كانت بداية تغيير شخصیتك",
"اعترف بحاجة فارقتك لعدت سنين",
"اعترف بحاجة خاقتك و نصحتك",
"اعترف بحاجة كنت تتمنى تقولها لوالدك",
"اعترف بحاجة خجلان تقولها لصديقك",
"اعترف بحاجة تمنیت لو الناس تفهمها",
"اعترف بحاجة لحد الآن تؤثر عليك",
"اعترف بحاجة حسیت وقتها انك وحيد",
"اعترف بحاجة سرّت عنك وخايف تكشف",
"اعترف بحاجة سالمة بس خلتك تتغير",
"اعترف بحاجة فكرت ترجعها بس لم تستطع",
"اعترف بحاجة انا متأكد انها كانت صائبة",
"اعترف بحاجة صارت لك صدفة عجبتك",
"اعترف بحاجة تمنیت اقولها من زمان",
"اعترف بحاجة غيرت طريقك بالمستقبل",
"اعترف بحاجة طولت تفكيرك قبل ما تسويها",
"اعترف بحاجة بتضحك لما تفتكر ردّة فعله",
"اعترف بحاجة يوم تبدى تحس انها طريقك",
"اعترف بحاجة ودي اعترفها اليوم",
"اعترف بحاجة ما توقعتها مني",
"اعترف بحاجة حسّيت انها ضعف بس طلعت قوة",
"اعترف بحاجة شفتها علامة رضا",
"اعترف بحاجة تمنیت لو تعرف اللي صار",
"اعترف بحاجة خلّتني اشك بنفسي",
"اعترف بحاجة غيرت انتباهك لحياة",
"اعترف بحاجة سرية بس ابي اعتذر عنها",
"اعترف بحاجة تبي تقولها للناس المهمين",
"اعترف بحاجة صار لها نتيجة حلوة",
"اعترف بحاجة تمنیت لو اعرفها في وقتها",
"اعترف بحاجة مجنونة سويتھا من حب",
"اعترف بحاجة تردد اني احكيها بس ابي اقولها"
]

# ==== 100 تحديات
challenges = [
"ارسل له رسالة تقول فيها 'مليون سبب أحبك' (صوت أو نص)",
"اقبل شريكك لمدة 10 ثواني قدام الناس",
"اصنع له مشروب مفضل واصوره وابعثه",
"اكتب له رسالة تبدأ بكلمة 'اشتقت' وارسلها",
"اعطه مفاجأة بسيطة اليوم بدون سبب",
"غني له مقطع من أغنية تحبها",
"سجل له رسالة صوتية تقول فيها صدق شعورك",
"اطبخ له شي بسيط وشارك صورته",
"صف شريكك بثلاث كلمات قدام ناس",
"اكتب له قائمة 5 أشياء تحبها فيه",
"شارك ذكرى قديمة حلوة بينكم",
"سامحه بشكل ظريف إذا كان زعلان",
"احجز له وقت صغير اليوم بس له",
"ابعث له صورة قديمة تجمعكم",
"سجل فيديو تقول فيه كلمة حب بصراحة",
"رتب له جلسة فيلم ومعيشة بسيطة",
"ارسل له ملاحظة صغيرة على خده",
"خذ له قهوه على ما يجي من الشغل",
"صمّم له رسالة بخطك وابعثلها",
"قل له أول شيء خطر في بالك الآن",
# نُكمل حتى 100
]

# نكمل التحديات حتى 100 تلقائياً لو أقل
while len(challenges) < 100:
    i = len(challenges) + 1
    challenges.append(f"تحدي رومنسي رقم {i}: سوّ له حاجة تخليه يضحك")

# ==== تحليل الشخصية: نستخدم 20 سؤال بأزرار (كل سؤال 4 اختيارات مرمزة بـ trait)
analysis_questions = [
    {
        "q": "لو زعلك موقف، وش تسوي؟",
        "opts": [
            ("أهدى وافكر قبل ما أرد", "calm"),
            ("أنفعل وأتكلم على طول", "strong"),
            ("أجلس واطلع عن الموضوع شوي", "sensitive"),
            ("أحاول أحل الموضوع عملي", "social")
        ]
    },
    {
        "q": "لما أحد يمدحك، وش شعورك؟",
        "opts": [
            ("أستحي لكن أفرح", "sensitive"),
            ("أستغل الموقف وابني عليه", "strong"),
            ("أضحك وأغير الموضوع", "social"),
            ("أخذها بهدوء وما أبالغ", "calm")
        ]
    },
    {
        "q": "في عزيمة، وش تسوي أكثر؟",
        "opts": [
            ("اجلس براحة واتفرج", "calm"),
            ("اتحرك مع الناس وأتكلم", "social"),
            ("أراقب وبس اتكلم مع ناس محددة", "sensitive"),
            ("تنظم وتدبر الأمور", "strong")
        ]
    },
    {
        "q": "لو ضايقك ضغط الشغل، كيف تخفف؟",
        "opts": [
            ("اقعد لحالي واسترجع افكاري", "calm"),
            ("اخذ راحة مع الناس اللي احبهم", "social"),
            ("اكتب مشاعري واعبر عنها", "sensitive"),
            ("اعمل خطة وانجز بسرعة", "strong")
        ]
    },
    {
        "q": "اذا عطيتك فرصة تقود مشروع، وش تسوي؟",
        "opts": [
            ("اقود بكل ثقة", "strong"),
            ("اجمع فريق واعمل طاقة", "social"),
            ("احب استمع وافكر بخطوات", "calm"),
            ("ابتكر وافكر خارج الصندوق", "sensitive")
        ]
    },
    {
        "q": "لو قابلت شخص جديد، كيف تتعامل؟",
        "opts": [
            ("اتفتح واتعرف بسرعة", "social"),
            ("انتظر واتابع تصرفاته", "calm"),
            ("احاول افهم مشاعره", "sensitive"),
            ("اخذ المبادرة وابدأ الحديث", "strong")
        ]
    },
    {
        "q": "كيف تتعامل مع النقد؟",
        "opts": [
            ("أستمع واتعلم", "calm"),
            ("أرد بحزم لو كان غير منصف", "strong"),
            ("أتأثر تقريباً وانزعج", "sensitive"),
            ("أضحك وأخفف الموقف", "social")
        ]
    },
    {
        "q": "وش اسلوبك بالاقناع؟",
        "opts": [
            ("هدوء ومنطق", "calm"),
            ("حماس وقوة كلام", "strong"),
            ("قرب عاطفي وفهم", "sensitive"),
            ("ضم الناس لوجهة نظرك", "social")
        ]
    },
    {
        "q": "لو صار خلاف بسيط، كيف تنهيه؟",
        "opts": [
            ("بتفاهم وهدوء", "calm"),
            ("بتواجه على طول", "strong"),
            ("تحاول تفهم مشاعر الطرف الثاني", "sensitive"),
            ("تضحك وتخفف الجو", "social")
        ]
    },
    {
        "q": "وش تحس يميزك في التعامل؟",
        "opts": [
            ("هدوء اعصاب", "calm"),
            ("حزم وقرار", "strong"),
            ("حساسية وفهم", "sensitive"),
            ("طاقة واجتماعية", "social")
        ]
    },
    {
        "q": "لو عطيتك وقت فراغ، وش تسوي؟",
        "opts": [
            ("اقرأ أو استرخى", "calm"),
            ("اجتمع مع الأهل والأصحاب", "social"),
            ("اعبر عن مشاعري او اكتب", "sensitive"),
            ("ابدأ مشروع او هواية جديدة", "strong")
        ]
    },
    {
        "q": "لو حصل موقف مفاجئ مزعج، ردة فعلك؟",
        "opts": [
            ("اهدي وافكر", "calm"),
            ("اتكلم بصراحة واطلع الحزم", "strong"),
            ("ابحث عن المشاعر اللي وراه", "sensitive"),
            ("امزح واهون الموقف", "social")
        ]
    },
    {
        "q": "اذا غلطت، أي رد تسوي؟",
        "opts": [
            ("اعتذر واصحح غلطتي", "calm"),
            ("اعمل خطة لتصليح", "strong"),
            ("أبدي اسف بعمق ومشاعر", "sensitive"),
            ("اخلي جو مرح لتخفيف التوتر", "social")
        ]
    },
    {
        "q": "تختار تكون مشهور بين الناس ولا هادي ومميز؟",
        "opts": [
            ("احب الشهرة والقرب من الناس", "social"),
            ("احب الاختفاء والهدوء", "calm"),
            ("احب الظهور بصدق واحاسيس", "sensitive"),
            ("احب اثبات نفسي بقراراتي", "strong")
        ]
    },
    {
        "q": "لو شفت ظلم، كيف تتصرف؟",
        "opts": [
            ("احاول أهدّي واعالج", "calm"),
            ("اتدخل وبحزم", "strong"),
            ("اتأثر واعطي دعم عاطفي", "sensitive"),
            ("اجمع الناس واسوي موقف", "social")
        ]
    },
    {
        "q": "لو عرضوا عليك تحدي كبير، كيف؟",
        "opts": [
            ("ادرس المخاطر وامشي", "calm"),
            ("اقبل وبقوة", "strong"),
            ("احس بالمخاطر وابكي شوي", "sensitive"),
            ("ابدأ واجيب الناس معي", "social")
        ]
    },
    {
        "q": "وش نوع الأصدقاء اللي ترتاح معهم؟",
        "opts": [
            ("اللي هادئين وعندهم عقل", "calm"),
            ("اللي مرحين وممتعین", "social"),
            ("اللي يحسون فيني ويفهمونني", "sensitive"),
            ("اللي يعتمدون علي واني اعتمد عليهم", "strong")
        ]
    },
    {
        "q": "كيف تحب تُعبّر عن فرحتك؟",
        "opts": [
            ("بابتسامة هادية", "calm"),
            ("باحتفال مع الناس", "social"),
            ("بدموع فرح ومشاعر", "sensitive"),
            ("بانجاز ونتيجة واضحة", "strong")
        ]
    },
    {
        "q": "لو خلصت الاسئلة، اي شكل تبي النتيجة؟",
        "opts": [
            ("وصف مفصل عن مشاعري", "sensitive"),
            ("نصايح عملية لتطوير نفسي", "strong"),
            ("نقطة قوة وهدوء", "calm"),
            ("نصايح تواصل واجتماعيات", "social")
        ]
    }
]

# ------------------ دوال واجهة الأزرار الرئيسية ------------------
def main_menu_buttons():
    buttons_template = ButtonsTemplate(
        title="أبغاك تستمتع",
        text="اختار اللي تبي تسويه الحين:",
        actions=[
            MessageAction(label="🎯 تحليل الشخصية", text="تحليل"),
            MessageAction(label="💬 صراحة وجرأة", text="صراحة"),
            MessageAction(label="🗣️ اعترافات", text="اعتراف"),
            MessageAction(label="🔥 تحديات", text="تحدي"),
            MessageAction(label="❓ مساعدة", text="مساعدة")
        ]
    )
    return TemplateSendMessage(alt_text="القائمة", template=buttons_template)

# ------------------ وظائف التحليل: بدء وبناء سؤال وحساب نتيجة ------------------
def start_analysis(user_id):
    # نختار 20 سؤال عشوائي من pool (بدون تكرار)
    pool = list(range(len(analysis_questions)))
    chosen = random.sample(pool, k=min(20, len(pool)))
    user_analysis_progress[user_id] = {
        "questions": chosen,
        "current": 0,
        "scores": {"strong":0, "sensitive":0, "social":0, "calm":0}
    }
    qidx = user_analysis_progress[user_id]["questions"][0]
    return build_analysis_question_message(qidx, 1, len(chosen))

def build_analysis_question_message(qidx, number, total):
    item = analysis_questions[qidx]
    title = f"سؤال {number}/{total}: {item['q']}"
    actions = []
    for choice_index, (label, trait) in enumerate(item["opts"]):
        data = urllib.parse.urlencode({"action":"analysis_answer","q":str(qidx),"c":str(choice_index),"t":trait})
        actions.append(PostbackAction(label=label, data=data))
    buttons = ButtonsTemplate(title="تحليل الشخصية", text=title, actions=actions)
    return TemplateSendMessage(alt_text="سؤال تحليل", template=buttons)

def handle_analysis_postback(user_id, qidx, choice_idx, trait):
    data = user_analysis_progress.get(user_id)
    if not data:
        return "ما فيه اختبار شغال عندك، اكتب 'تحليل' لتبدأ."
    # سجل نقاط
    if trait in data["scores"]:
        data["scores"][trait] += 1
    # تقدّم للسؤال القادم
    data["current"] += 1
    if data["current"] >= len(data["questions"]):
        # انتهى الاختبار: احسب النتيجة
        scores = data["scores"]
        del user_analysis_progress[user_id]
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary, primary_score = sorted_scores[0]
        secondary, secondary_score = sorted_scores[1]
        desc = generate_analysis_text(primary, secondary, scores)
        return desc
    else:
        next_qidx = data["questions"][data["current"]]
        return build_analysis_question_message(next_qidx, data["current"]+1, len(data["questions"]))

def generate_analysis_text(primary, secondary, scores):
    mapping = {
        "strong": ("قوي وواثق", 
                   "أنت شخص واضح وصريح، تميل تاخذ زمام الأمور وماتحب التردد. عادةً تبادر وتحب تحل المشاكل بسرعة. هالأسلوب يخليك قائد في كثير مواقف."),
        "sensitive": ("حساس وعاطفي",
                      "أنت إنسان عميق بالمشاعر، تحس وتتفهم الناس من غير ما تقول، وتقدّر التفاصيل الصغيرة اللي تعني كثير. ممكن تتأثر بسرعة بس بنفس الوقت قلبك كبير."),
        "social": ("اجتماعي ومتحمس",
                   "تميل تكون وسط الناس، طاقتك معدية وتحب تخوض تجارب مع الآخرين. سهل تكوّن صداقات وتحب تخلق جو حلو حواليك."),
        "calm": ("هادي ومتفكر",
                 "أسلوبك متأنٍ وراقي، تحب تفكر قبل ما تتصرف وما تنجرّ وراك الحماس. هالهدوء يخليك صاحب قرار منطقي في الكثير من المواقف.")
    }
    p_title, p_text = mapping[primary]
    s_title, s_text = mapping[secondary]
    extra = ""
    if scores[primary] - scores[secondary] >= 5:
        extra = "واضح ان هالطابع يسيطر عليك بشكل كبير، تقدر تستثمر هالشي في قيادة مشاريعك وعلاقاتك."
    elif scores[primary] - scores[secondary] <= 1:
        extra = "شكل شخصيتك مزيج متوازن، تقدر تتكيّف مع المواقف بسهولة وتعطي الناس اللي حولك."
    else:
        extra = "عندك توازن بين الجوانب، لكن جانب واحد يبرز شوي عن الباقي."
    result = f"🎯 تحليلك:\nأبرز طابع: {p_title}\n\n{p_text}\n\nالثاني اللي يبين: {s_title}\n{s_text}\n\n{extra}\n\nنصيحة بسيطة: حاول تستغل نقاط قوتك واحتضن نقاط الضعف كفرص تطوير."
    return result

# ------------------ Webhook handlers ------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ------------------ معالجة رسائل المستخدم ------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()

    # القائمة الرئيسية
    if text in ["ابدأ", "ابدا", "بدء", "start", "لعبة", "القائمة"]:
        line_bot_api.reply_message(event.reply_token, main_menu_buttons())
        return

    # مساعدة
    if "مساعدة" in text or "help" in text:
        help_text = (
            "📘 أوامر البوت:\n"
            "- اكتب 'ابدأ' علشان تطلع لك الازرار.\n"
            "- اضغط 'تحليل' عشان تبدأ اختبار 20 سؤال بالأزرار.\n"
            "- اضغط 'صراحة' أو 'اعتراف' أو 'تحدي' عشان تجيك أسئلة وتحديات عشوائية.\n"
            "- كل سؤال يتغير وما يتكرر لنفسك حتى تخلص المجموعة.\n"
            "- اكتب 'إعادة' لو تبي تمسح جلساتك وتبدأ من جديد.\n\nاستمتع 💚"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # إعادة الجلسة
    if "إعادة" in text or "اعادة" in text or "restart" in text:
        user_asked_questions.pop(user_id, None)
        user_asked_confessions.pop(user_id, None)
        user_asked_challenges.pop(user_id, None)
        user_analysis_progress.pop(user_id, None)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم إعادة الإعداد، اكتب 'ابدأ' علشان ترجع القائمة"))
        return

    # صراحة
    if "صراحة" in text or "جرأة" in text or "جرأة" in text:
        asked = user_asked_questions.get(user_id, set())
        available = [q for q in truth_questions if q not in asked]
        if not available:
            user_asked_questions[user_id] = set()
            available = truth_questions.copy()
        q = random.choice(available)
        user_asked_questions.setdefault(user_id, set()).add(q)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❖ سؤال صراحة:\n{q}"))
        return

    # اعتراف
    if "اعتراف" in text or "اعترف" in text:
        asked = user_asked_confessions.get(user_id, set())
        available = [q for q in confession_questions if q not in asked]
        if not available:
            user_asked_confessions[user_id] = set()
            available = confession_questions.copy()
        q = random.choice(available)
        user_asked_confessions.setdefault(user_id, set()).add(q)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🗣️ اعتراف:\n{q}"))
        return

    # تحدي
    if "تحدي" in text:
        asked = user_asked_challenges.get(user_id, set())
        available = [q for q in challenges if q not in asked]
        if not available:
            user_asked_challenges[user_id] = set()
            available = challenges.copy()
        c = random.choice(available)
        user_asked_challenges.setdefault(user_id, set()).add(c)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🔥 تحدي:\n{c}"))
        return

    # بدء التحليل عن طريق نص (لو المستخدم كتب "تحليل")
    if "تحليل" in text:
        msg = start_analysis(user_id)
        line_bot_api.reply_message(event.reply_token, msg)
        return

    # افتراضي: لا نرد على أي نص آخر
    return

# ------------------ التعامل مع Postback (أزرار التحليل) ------------------
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data  # الشكل urlencoded من start_analysis
    params = dict(urllib.parse.parse_qsl(data))
    action = params.get("action")
    if action == "analysis_answer":
        qidx = int(params.get("q", 0))
        choice_idx = int(params.get("c", 0))
        trait = params.get("t", "")
        reply = handle_analysis_postback(user_id, qidx, choice_idx, trait)
        if isinstance(reply, TemplateSendMessage):
            line_bot_api.reply_message(event.reply_token, reply)
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    else:
        # ردود عامة لو في actions ثانية (ما نستخدم حاليًا)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="تم الضغط"))

# ------------------ تشغيل التطبيق ------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
