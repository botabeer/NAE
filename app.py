import os
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ══════════════════════════════════════════════════
# إعدادات LINE
# ══════════════════════════════════════════════════
TOKEN = os.getenv("LINE_CHANNEL_TOKEN", "")
SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

line_bot_api = LineBotApi(TOKEN) if TOKEN else None
handler = WebhookHandler(SECRET) if SECRET else None

# ══════════════════════════════════════════════════
# محتوى الألعاب
# ══════════════════════════════════════════════════
QUESTIONS = [
    "لو تقدر تسافر لأي مكان في العالم، وين تروح؟",
    "إيش أكثر شيء تندم عليه في حياتك؟",
    "من آخر شخص فكرت فيه قبل تنام؟",
    "إيش أغرب حلم حلمته؟",
    "لو عندك قوة خارقة، إيش تختار؟",
]

CHALLENGES = [
    "ارسل صورة سيلفي بدون فلتر 🤳",
    "قلد صوت أحد الأعضاء 🎭",
    "اكتب رسالة لآخر شخص تكلمت معاه 💌",
    "ارقص 10 ثواني وصور نفسك 💃",
]

MENTIONS = [
    "منشن شخص تعتبره قدوتك 🌟",
    "منشن أكثر شخص يضحكك 😂",
    "منشن شخص تتمنى تسافر معاه ✈️",
]

CONFESSIONS = [
    "اعترف بشيء ما قلته لأحد من قبل 🤐",
    "إيش أكبر كذبة قلتها؟ 🤥",
    "من الشخص اللي تحبه بسر؟ 💘",
]

SITUATIONS = [
    "لو تقدر ترجع الزمن، إيش بتغير؟ ⏰",
    "لو عندك مليون ريال، إيش أول شيء تسويه؟ 💰",
]

RIDDLES = [
    "شيء له رأس وليس له عيون؟ (الجواب: الدبوس 📌)",
    "ما هو الشيء الذي يمشي بلا أرجل؟ (الجواب: السحاب ☁️)",
]

PERSONALITY = [
    "🎨 شخصية إبداعية",
    "😂 شخصية مرحة",
    "🧠 شخصية ذكية",
    "💪 شخصية قيادية",
]

# ══════════════════════════════════════════════════
# نظام التتبع
# ══════════════════════════════════════════════════
state = {}

def get_next(user_id, key, lst):
    idx = state.get(f"{user_id}_{key}", 0)
    state[f"{user_id}_{key}"] = (idx + 1) % len(lst)
    return lst[idx]

# ══════════════════════════════════════════════════
# الكاروسيل
# ══════════════════════════════════════════════════
def get_help_carousel():
    return FlexSendMessage(
        alt_text="قائمة البوت",
        contents={
            "type": "carousel",
            "contents": [
                {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#4B0082",
                        "paddingAll": "20px",
                        "contents": [
                            {"type": "text", "text": "بوت عناد المالكي", "weight": "bold", "size": "xl", "color": "#FFFFFF", "align": "center"},
                            {"type": "separator", "margin": "md", "color": "#FFFFFF40"},
                            {"type": "text", "text": "أوامر اللعب", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center", "margin": "md"},
                            {"type": "box", "layout": "vertical", "spacing": "sm", "margin": "md", "contents": [
                                {"type": "button", "action": {"type": "message", "label": "▪️ سؤال", "text": "سؤال"}, "style": "primary", "color": "#6A0DAD"},
                                {"type": "button", "action": {"type": "message", "label": "▫️ تحدي", "text": "تحدي"}, "style": "primary", "color": "#6A0DAD"},
                                {"type": "button", "action": {"type": "message", "label": "▪️ منشن", "text": "منشن"}, "style": "primary", "color": "#6A0DAD"},
                                {"type": "button", "action": {"type": "message", "label": "▫️ اعتراف", "text": "اعتراف"}, "style": "primary", "color": "#6A0DAD"},
                            ]},
                            {"type": "text", "text": "© عبير الدوسري", "color": "#FFFFFF80", "size": "xs", "align": "center", "margin": "lg"}
                        ]
                    }
                },
                {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#4B0082",
                        "paddingAll": "20px",
                        "contents": [
                            {"type": "text", "text": "بوت عناد المالكي", "weight": "bold", "size": "xl", "color": "#FFFFFF", "align": "center"},
                            {"type": "separator", "margin": "md", "color": "#FFFFFF40"},
                            {"type": "text", "text": "ألعاب إضافية", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center", "margin": "md"},
                            {"type": "box", "layout": "vertical", "spacing": "sm", "margin": "md", "contents": [
                                {"type": "button", "action": {"type": "message", "label": "▪️ موقف", "text": "موقف"}, "style": "primary", "color": "#6A0DAD"},
                                {"type": "button", "action": {"type": "message", "label": "▫️ لغز", "text": "لغز"}, "style": "primary", "color": "#6A0DAD"},
                                {"type": "button", "action": {"type": "message", "label": "▪️ تحليل", "text": "تحليل"}, "style": "primary", "color": "#6A0DAD"},
                            ]},
                        ]
                    }
                }
            ]
        }
    )

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
        abort(400)
    except Exception as e:
        logging.error(f"خطأ: {e}")
    return "OK"

@app.route("/")
def home():
    return "البوت يعمل ✅"

# ══════════════════════════════════════════════════
# معالج الرسائل
# ══════════════════════════════════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    try:
        if text == "مساعدة":
            line_bot_api.reply_message(event.reply_token, get_help_carousel())
        elif text == "سؤال":
            msg = get_next(user_id, "q", QUESTIONS)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "تحدي":
            msg = get_next(user_id, "ch", CHALLENGES)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "منشن":
            msg = get_next(user_id, "m", MENTIONS)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "اعتراف":
            msg = get_next(user_id, "cf", CONFESSIONS)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "موقف":
            msg = get_next(user_id, "st", SITUATIONS)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "لغز":
            msg = get_next(user_id, "r", RIDDLES)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        elif text == "تحليل":
            msg = get_next(user_id, "p", PERSONALITY)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✨ {msg}"))
    except Exception as e:
        logging.error(f"خطأ: {e}")

# ══════════════════════════════════════════════════
# تشغيل
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
