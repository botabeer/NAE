import os
import logging
import random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ══════════════════════════════════════════════════
# إعدادات LINE
# ══════════════════════════════════════════════════
TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise ValueError("⚠️ يرجى تعيين LINE_CHANNEL_TOKEN و LINE_CHANNEL_SECRET في المتغيرات البيئية")

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ══════════════════════════════════════════════════
# رابط الصورة (استبدله برابط صورتك على Imgur)
# ══════════════════════════════════════════════════
IMAGE_URL = "https://i.imgur.com/purple-image.jpg"  # ⚠️ غيّر هذا!

# ══════════════════════════════════════════════════
# محتوى الألعاب
# ══════════════════════════════════════════════════
QUESTIONS = [
    "لو تقدر تسافر لأي مكان في العالم، وين تروح؟",
    "إيش أكثر شيء تندم عليه في حياتك؟",
    "من آخر شخص فكرت فيه قبل تنام؟",
    "إيش أغرب حلم حلمته؟",
    "لو عندك قوة خارقة، إيش تختار؟",
    "إيش أكثر شيء يخوفك في المستقبل؟",
    "من الشخص اللي تثق فيه أكثر شيء؟",
    "إيش أسعد لحظة عشتها؟",
]

CHALLENGES = [
    "ارسل صورة سيلفي بدون فلتر 🤳",
    "قلد صوت أحد الأعضاء (صوتي) 🎭",
    "اكتب رسالة لآخر شخص تكلمت معاه 💌",
    "ارقص 10 ثواني وصور نفسك 💃",
    "اتصل على شخص عشوائي وقله شيء مضحك 📞",
    "غير اسمك لمدة ساعة لـ (أنا غبي) 😂",
    "امسح آخر 3 رسائل من محادثاتك 🗑️",
]

MENTIONS = [
    "منشن شخص تعتبره قدوتك 🌟",
    "منشن أكثر شخص يضحكك 😂",
    "منشن شخص تتمنى تسافر معاه ✈️",
    "منشن آخر شخص زعلك 😔",
    "منشن شخص ما تقدر تزعل منه 💕",
    "منشن أذكى شخص تعرفه 🧠",
    "منشن شخص تحس إنه يفهمك 🤝",
]

CONFESSIONS = [
    "اعترف بشيء ما قلته لأحد من قبل 🤐",
    "إيش أكبر كذبة قلتها؟ 🤥",
    "من الشخص اللي تحبه بسر؟ 💘",
    "إيش أكثر شيء تستحي تعترف فيه؟ 😳",
    "من آخر شخص بكيت عشانه؟ 😢",
    "إيش أكثر شيء نفسك فيه حالياً؟ 🌠",
]

SITUATIONS = [
    "لو تقدر ترجع الزمن، إيش بتغير؟ ⏰",
    "لو عندك مليون ريال، إيش أول شيء تسويه؟ 💰",
    "لو تقدر تقابل أي شخص ميت، من تختار؟ 👻",
    "لو تعلق في جزيرة، من تبي يكون معاك؟ 🏝️",
    "لو تقدر تغير شيء في شكلك، إيش يكون؟ 🪞",
]

RIDDLES = [
    "شيء له رأس وليس له عيون؟ (الجواب: الدبوس 📌)",
    "ما هو الشيء الذي يمشي بلا أرجل ويبكي بلا عيون؟ (الجواب: السحاب ☁️)",
    "أنا أمشي بدون أرجل، وأدخل الأذن بدون استئذان، من أنا؟ (الجواب: الصوت 🔊)",
    "كلما أخذت منه كبر، ما هو؟ (الجواب: الحفرة 🕳️)",
    "له عين ولا يرى، من هو؟ (الجواب: الإبرة 🪡)",
]

PERSONALITY_TRAITS = [
    "🎨 شخصية إبداعية: دايم عندك أفكار جديدة ومبتكرة",
    "😂 شخصية مرحة: روح المجموعة والكل يحب يسولف معاك",
    "🧠 شخصية ذكية: تحب التفكير العميق وحل المشاكل",
    "💪 شخصية قيادية: تحب تقود وتنظم الأمور",
    "🤝 شخصية اجتماعية: تحب الناس والتواصل",
    "🎯 شخصية طموحة: دايم تسعى للأفضل",
    "💙 شخصية حنونة: قلبك طيب وتهتم بالآخرين",
    "🔥 شخصية متحمسة: دايم نشيط ومتحمس",
]

# ══════════════════════════════════════════════════
# الكاروسيل المحسّن
# ══════════════════════════════════════════════════
def create_bubble(title, buttons, is_first=False):
    """إنشاء صفحة واحدة من الكاروسيل"""
    contents = [
        {
            "type": "text",
            "text": "بوت عناد المالكي" if is_first else "🎮",
            "weight": "bold",
            "size": "xl" if is_first else "xxl",
            "color": "#FFFFFF",
            "align": "center"
        },
        {
            "type": "separator",
            "margin": "md",
            "color": "#FFFFFF40"
        },
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "size": "lg",
            "color": "#FFD700",
            "align": "center",
            "margin": "md"
        }
    ]
    
    button_box = {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "margin": "lg",
        "contents": buttons
    }
    contents.append(button_box)
    
    if is_first:
        contents.append({
            "type": "text",
            "text": "© عبير الدوسري",
            "color": "#FFFFFF60",
            "size": "xs",
            "align": "center",
            "margin": "xl"
        })
    
    return {
        "type": "bubble",
        "size": "mega",
        "hero": {
            "type": "image",
            "url": IMAGE_URL,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "backgroundColor": "#4B0082",
            "paddingAll": "20px",
            "contents": contents
        }
    }

def get_help_carousel():
    """قائمة المساعدة الرئيسية"""
    page1_buttons = [
        {"type": "button", "action": {"type": "message", "label": "🎲 سؤال", "text": "سؤال"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "💪 تحدي", "text": "تحدي"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "👥 منشن", "text": "منشن"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "💭 اعتراف", "text": "اعتراف"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
    ]
    
    page2_buttons = [
        {"type": "button", "action": {"type": "message", "label": "🤔 موقف", "text": "موقف"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "🧩 لغز", "text": "لغز"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "🎭 تحليل", "text": "تحليل"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
        {"type": "button", "action": {"type": "message", "label": "🏆 نقاطي", "text": "نقاطي"}, "style": "primary", "color": "#8B00FF", "height": "sm"},
    ]
    
    page3_buttons = [
        {"type": "button", "action": {"type": "message", "label": "👑 الصدارة", "text": "الصدارة"}, "style": "primary", "color": "#FFD700", "height": "sm"},
        {"type": "button", "action": {"type": "uri", "label": "💬 تواصل مع المطور", "uri": "https://line.me/ti/p/~your_line_id"}, "style": "link", "height": "sm"},
    ]
    
    return FlexSendMessage(
        alt_text="📋 قائمة البوت",
        contents={
            "type": "carousel",
            "contents": [
                create_bubble("🎮 ألعاب تفاعلية", page1_buttons, is_first=True),
                create_bubble("🎯 المزيد من الألعاب", page2_buttons),
                create_bubble("ℹ️ معلومات إضافية", page3_buttons)
            ]
        }
    )

# ══════════════════════════════════════════════════
# نظام النقاط (بسيط - يمكن تطويره لاحقاً)
# ══════════════════════════════════════════════════
user_points = {}

def add_points(user_id, points=1):
    """إضافة نقاط للمستخدم"""
    user_points[user_id] = user_points.get(user_id, 0) + points

def get_points(user_id):
    """الحصول على نقاط المستخدم"""
    return user_points.get(user_id, 0)

# ══════════════════════════════════════════════════
# Webhook
# ══════════════════════════════════════════════════
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("❌ توقيع غير صالح")
        abort(400)
    except Exception as e:
        logging.error(f"❌ خطأ: {e}")
    
    return "OK"

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

# ══════════════════════════════════════════════════
# معالج الرسائل
# ══════════════════════════════════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    # قاموس الأوامر
    commands = {
        "مساعدة": lambda: line_bot_api.reply_message(event.reply_token, get_help_carousel()),
        "سؤال": lambda: reply_text(random.choice(QUESTIONS)),
        "تحدي": lambda: reply_text(random.choice(CHALLENGES)),
        "منشن": lambda: reply_text(random.choice(MENTIONS)),
        "اعتراف": lambda: reply_text(random.choice(CONFESSIONS)),
        "موقف": lambda: reply_text(random.choice(SITUATIONS)),
        "لغز": lambda: reply_text(random.choice(RIDDLES)),
        "تحليل": lambda: reply_personality(),
        "نقاطي": lambda: reply_points(),
        "الصدارة": lambda: reply_leaderboard(),
    }
    
    def reply_text(message):
        """رد نصي مع إضافة نقاط"""
        add_points(user_id, 1)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    
    def reply_personality():
        """تحليل الشخصية"""
        add_points(user_id, 2)
        trait = random.choice(PERSONALITY_TRAITS)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"✨ تحليل شخصيتك:\n\n{trait}\n\n💫 +2 نقطة")
        )
    
    def reply_points():
        """عرض النقاط"""
        points = get_points(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"🏆 نقاطك: {points} نقطة\n\n💡 اجمع نقاط أكثر بالمشاركة في الألعاب!")
        )
    
    def reply_leaderboard():
        """قائمة الصدارة"""
        if not user_points:
            msg = "📊 لا توجد نقاط بعد!\n\nابدأ اللعب لتسجيل نقاطك 🎮"
        else:
            sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)[:5]
            msg = "👑 قائمة الصدارة\n" + "═" * 20 + "\n\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, (uid, pts) in enumerate(sorted_users):
                msg += f"{medals[i]} {pts} نقطة\n"
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    
    # تنفيذ الأمر أو التجاهل
    if text in commands:
        try:
            commands[text]()
        except Exception as e:
            logging.error(f"❌ خطأ في تنفيذ {text}: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ حدث خطأ، حاول مرة أخرى")
            )

# ══════════════════════════════════════════════════
# تشغيل التطبيق
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
