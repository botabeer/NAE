# ============================================
# app.py — بوت LINE (نسخة نهائية)
# ============================================

import os
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# مفاتيح LINE (غيرهم حسب حسابك)
# -------------------------------------------------
TOKEN = os.getenv("LINE_CHANNEL_TOKEN", "YOUR_CHANNEL_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# -------------------------------------------------
# رابط الصورة البنفسجية
# -------------------------------------------------
IMAGE_URL = "file:///mnt/data/25062640-AF0F-4D7C-B817-8558581CEB94.jpeg"

# =================================================
#      الكاروusel البنفسجي — مع عنوان وحقوق
# =================================================
def get_help_carousel():
    return FlexSendMessage(
        alt_text="مساعدة البوت",
        contents={
            "type": "carousel",
            "contents": [

                # -------------------------------------------------------
                # الصفحة 1 — أوامر اللعب
                # -------------------------------------------------------
                {
                    "type": "bubble",
                    "size": "mega",
                    "hero": {
                        "type": "image",
                        "url": IMAGE_URL,
                        "size": "full",
                        "aspectRatio": "16:9",
                        "aspectMode": "cover"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "backgroundColor": "#4B0082",
                        "paddingAll": "20px",
                        "contents": [

                            # عنوان البوت
                            {
                                "type": "text",
                                "text": "بوت عناد المالكي",
                                "weight": "bold",
                                "size": "xl",
                                "color": "#FFFFFF",
                                "align": "center",
                                "margin": "md"
                            },

                            {
                                "type": "separator",
                                "margin": "md",
                                "color": "#FFFFFF40"
                            },

                            {
                                "type": "text",
                                "text": "أوامر اللعب",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#FFFFFF",
                                "align": "center"
                            },

                            {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "margin": "md",
                                "contents": [
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▪️ سؤال", "text": "سؤال"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▫️ تحدي", "text": "تحدي"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▪️ منشن", "text": "منشن"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▫️ اعتراف", "text": "اعتراف"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▪️ موقف", "text": "موقف"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▫️ لغز", "text": "لغز"},
                                     "style": "primary", "color": "#6A0DAD"}
                                ]
                            },

                            {
                                "type": "text",
                                "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري",
                                "color": "#FFFFFF80",
                                "size": "xs",
                                "align": "center",
                                "margin": "lg"
                            }
                        ]
                    }
                },

                # -------------------------------------------------------
                # الصفحة 2 — ألعاب شخصية
                # -------------------------------------------------------
                {
                    "type": "bubble",
                    "size": "mega",
                    "hero": {
                        "type": "image",
                        "url": IMAGE_URL,
                        "size": "full",
                        "aspectRatio": "16:9",
                        "aspectMode": "cover"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "backgroundColor": "#4B0082",
                        "paddingAll": "20px",
                        "contents": [

                            {
                                "type": "text",
                                "text": "بوت عناد المالكي",
                                "weight": "bold",
                                "size": "xl",
                                "color": "#FFFFFF",
                                "align": "center",
                                "margin": "md"
                            },

                            {
                                "type": "separator",
                                "margin": "md",
                                "color": "#FFFFFF40"
                            },

                            {
                                "type": "text",
                                "text": "ألعاب شخصية",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#FFFFFF",
                                "align": "center"
                            },

                            {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "margin": "md",
                                "contents": [
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▪️ تحليل", "text": "تحليل"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▫️ نقاطي", "text": "نقاطي"},
                                     "style": "primary", "color": "#6A0DAD"},
                                    {"type": "button",
                                     "action": {"type": "message", "label": "▪️ الصدارة", "text": "الصدارة"},
                                     "style": "primary", "color": "#6A0DAD"}
                                ]
                            },

                            {
                                "type": "text",
                                "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري",
                                "color": "#FFFFFF80",
                                "size": "xs",
                                "align": "center",
                                "margin": "lg"
                            }
                        ]
                    }
                },

                # -------------------------------------------------------
                # الصفحة 3 — مساعدة
                # -------------------------------------------------------
                {
                    "type": "bubble",
                    "size": "mega",
                    "hero": {
                        "type": "image",
                        "url": IMAGE_URL,
                        "size": "full",
                        "aspectRatio": "16:9",
                        "aspectMode": "cover"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "backgroundColor": "#4B0082",
                        "paddingAll": "20px",
                        "contents": [

                            {
                                "type": "text",
                                "text": "بوت عناد المالكي",
                                "weight": "bold",
                                "size": "xl",
                                "color": "#FFFFFF",
                                "align": "center",
                                "margin": "md"
                            },

                            {
                                "type": "separator",
                                "margin": "md",
                                "color": "#FFFFFF40"
                            },

                            {
                                "type": "text",
                                "text":
                                    "▫️ تقدر تستخدم البوت في الخاص أو القروبات.\n"
                                    "▫️ كل الأوامر كلمة وحده.\n"
                                    "▫️ بعض الألعاب فيها: جاوب – لمح.",
                                "wrap": True,
                                "color": "#FFFFFF",
                                "size": "md"
                            },

                            {
                                "type": "text",
                                "text": "تم إنشاء هذا البوت بواسطة عبير الدوسري",
                                "color": "#FFFFFF80",
                                "size": "xs",
                                "align": "center",
                                "margin": "lg"
                            }
                        ]
                    }
                }
            ]
        }
    )

# =================================================
# Webhook
# =================================================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# =================================================
# ردود البوت
# =================================================
VALID_COMMANDS = {
    "مساعدة", "سؤال", "تحدي", "منشن",
    "اعتراف", "موقف", "لغز",
    "تحليل", "نقاطي", "الصدارة"
}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    # أمر مساعدة
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, get_help_carousel())
        return

    # البوت يرد فقط على الأوامر — غير كذا يتجاهل
    if text not in VALID_COMMANDS:
        return  # تجاهل بدون رد

    # باقي الأوامر (مفصلة لاحقاً إذا أردت)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"تم تنفيذ الأمر: {text}"))


# =================================================
# تشغيل محلي
# =================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
