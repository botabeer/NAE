import json
import os
import logging
import random
from typing import List, Optional, Dict, Union
from threading import Lock
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, ImageSendMessage,
    QuickReply, QuickReplyButton, MessageAction, BubbleContainer,
    BoxComponent, TextComponent, ButtonComponent, MessageAction as FlexMessageAction,
    SeparatorComponent
)

# === إعداد Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === إعداد متغيرات البيئة ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Locks للتزامن ===
content_lock = Lock()

# === لعبة الفروقات ===
DIFFERENCE_SETS = [
    {
        "original": "https://i.imgur.com/1Yq7rKj.jpg",
        "changed": "https://i.imgur.com/XM0HkEW.jpg",
        "answer": 3
    },
    {
        "original": "https://i.imgur.com/4bAqH8h.jpg",
        "changed": "https://i.imgur.com/W3x1jpd.jpg",
        "answer": 5
    },
    {
        "original": "https://i.imgur.com/R60SwLZ.jpg",
        "changed": "https://i.imgur.com/OCZTjXA.jpg",
        "answer": 4
    }
]

def get_difference_challenge():
    return random.choice(DIFFERENCE_SETS)

# === مدير المحتوى ===
class ContentManager:
    def __init__(self):
        self.games_list: List[dict] = []
        self.detailed_results: Dict = {}

    def load_json_file(self, filename: str) -> Union[dict, list]:
        if not os.path.exists(filename):
            return [] if filename.endswith("s.json") else {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except:
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        self.games_list = self.load_json_file("personality_games.json")
        self.detailed_results = self.load_json_file("detailed_results.json")

content_manager = ContentManager()
content_manager.initialize()

# === القوائم الثابتة مع ▫️ ===
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="▫️ لعبة", text="لعبه")),
    ])

# === Flex Messages للألعاب ===
def create_game_list_flex(games: list):
    game_buttons = []
    for i, game in enumerate(games[:10], 1):
        game_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(
                    label=f"▫️ {i}. {game.get('title', f'اللعبة {i}')}",
                    text=str(i)
                ),
                style='secondary',
                color='#d3d3d3',  # رمادي فاتح
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text="قائمة الألعاب",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text='🕹️ الألعاب المتاحة',
                        weight='bold',
                        size='xl',
                        color='#000000',
                        align='center'
                    ),
                    SeparatorComponent(margin='lg', color='#e0e0e0'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='sm',
                        contents=game_buttons
                    )
                ],
                paddingAll='20px',
                backgroundColor='#ffffff'
            )
        )
    )

def create_game_question_flex(game_title: str, question: dict, progress: str):
    option_buttons = []
    for key, value in question['options'].items():
        option_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(label=f"▫️ {key}. {value}", text=key),
                style='secondary',
                color='#d3d3d3',  # رمادي فاتح
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text=f"{game_title}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='horizontal',
                        contents=[
                            TextComponent(
                                text=game_title,
                                weight='bold',
                                size='lg',
                                color='#000000',
                                flex=1
                            ),
                            TextComponent(
                                text=progress,
                                size='sm',
                                color='#999999',
                                flex=0,
                                align='end'
                            )
                        ]
                    ),
                    SeparatorComponent(margin='lg', color='#e0e0e0'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=question['question'],
                                size='md',
                                color='#000000',
                                wrap=True,
                                lineSpacing='8px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor='#f5f5f5',
                        cornerRadius='8px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='sm',
                        contents=option_buttons
                    )
                ],
                paddingAll='20px',
                backgroundColor='#ffffff'
            )
        )
    )

def create_game_result_flex(result_text: str, stats: str, username: str):
    return FlexSendMessage(
        alt_text="النتيجة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text=f'{username}',
                        weight='bold',
                        size='lg',
                        color='#666666',
                        align='center'
                    ),
                    TextComponent(
                        text='🏁 نتيجتك',
                        weight='bold',
                        size='xl',
                        color='#000000',
                        align='center',
                        margin='md'
                    ),
                    SeparatorComponent(margin='lg', color='#e0e0e0'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=result_text,
                                size='md',
                                color='#000000',
                                wrap=True,
                                lineSpacing='8px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor='#f5f5f5',
                        cornerRadius='8px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(
                                text=stats,
                                size='sm',
                                color='#888888',
                                wrap=True,
                                align='center'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=FlexMessageAction(label='▫️ 🎮 لعبة جديدة', text='لعبه'),
                                style='primary',
                                color='#d3d3d3',
                                height='sm'
                            )
                        ]
                    )
                ],
                paddingAll='20px',
                backgroundColor='#ffffff'
            )
        )
    )

# === حالات المستخدمين ===
user_game_state: Dict[str, dict] = {}

# === دوال اللعبة ===
def get_user_display_name(user_id: str) -> str:
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.display_name
    except:
        return "المستخدم"

def calculate_result(answers: List[str], game_index: int) -> tuple:
    count = {"أ":0,"ب":0,"ج":0}
    for ans in answers:
        if ans in count:
            count[ans]+=1
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key,{}).get(
        most_common, f"إجابتك الأكثر: {most_common}\n\nنتيجتك تعكس شخصية مميزة!"
    )
    stats = f"أ: {count['أ']} • ب: {count['ب']} • ج: {count['ج']}"
    return result_text, stats

def handle_game_selection(event,user_id:str,num:int):
    if 1<=num<=len(content_manager.games_list):
        game_index = num-1
        user_game_state[user_id] = {"game_index":game_index,"question_index":0,"answers":[]}
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        progress = f"1/{len(game['questions'])}"
        flex_msg = create_game_question_flex(game.get('title', f'اللعبة {num}'), first_q, progress)
        line_bot_api.reply_message(event.reply_token, flex_msg)

def handle_game_answer(event,user_id:str,text:str):
    state = user_game_state.get(user_id)
    if not state: return
    answer_map = {"1":"أ","2":"ب","3":"ج","a":"أ","b":"ب","c":"ج"}
    answer = answer_map.get(text.lower(), text)
    if answer in ["أ","ب","ج"]:
        state["answers"].append(answer)
        game = content_manager.games_list[state["game_index"]]
        state["question_index"] +=1
        if state["question_index"] < len(game["questions"]):
            q = game["questions"][state["question_index"]]
            progress = f"{state['question_index']+1}/{len(game['questions'])}"
            flex_msg = create_game_question_flex(game.get('title', 'اللعبة'), q, progress)
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            result_text, stats = calculate_result(state["answers"], state["game_index"])
            username = get_user_display_name(user_id)
            flex_msg = create_game_result_flex(result_text, stats, username)
            line_bot_api.reply_message(event.reply_token, flex_msg)
            del user_game_state[user_id]

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return "البوت يعمل بنجاح!", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature","")
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
    try:
        # فقط الأوامر الخاصة باللعبة
        if text in ["لعبه","لعبة","العاب","ألعاب","game","games"]:
            if content_manager.games_list:
                flex_msg = create_game_list_flex(content_manager.games_list)
                line_bot_api.reply_message(event.reply_token, flex_msg)
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="لا توجد ألعاب متاحة حالياً.", quick_reply=create_main_menu()))
            return

        if text.isdigit():
            handle_game_selection(event, user_id, int(text))
            return

        if user_id in user_game_state:
            handle_game_answer(event, user_id, text)
            return

        # أي رسالة أخرى → تجاهل تام
        return

    except Exception as e:
        logger.error(f"خطأ: {e}")

# === تشغيل التطبيق ===
if __name__=="__main__":
    port = int(os.getenv("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
