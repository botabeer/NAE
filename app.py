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
    """اختيار تحدي فروقات عشوائي"""
    return random.choice(DIFFERENCE_SETS)

# === مدير المحتوى ===
class ContentManager:
    def __init__(self):
        self.content_files: Dict[str, List[str]] = {}
        self.more_questions: List[str] = []
        self.riddles_list: List[dict] = []
        self.games_list: List[dict] = []
        self.poems_list: List[dict] = []
        self.quotes_list: List[dict] = []
        self.detailed_results: Dict = {}
        self.used_indices: Dict[str, List[int]] = {}

    def load_file_lines(self, filename: str) -> List[str]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                logger.info(f"تم تحميل {len(lines)} سطر من {filename}")
                return lines
        except Exception as e:
            logger.error(f"خطأ في قراءة الملف {filename}: {e}")
            return []

    def load_json_file(self, filename: str) -> Union[dict, list]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return [] if filename.endswith("s.json") else {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"خطأ في قراءة أو تحليل JSON {filename}: {e}")
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }

        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر","لغز","شعر","اقتباسات"]:
            self.used_indices[key] = []

        self.more_questions = self.load_file_lines("more_file.txt")
        self.riddles_list = self.load_json_file("riddles.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")

        data = self.load_json_file("personality_games.json")
        if isinstance(data, dict):
            self.games_list = [data[key] for key in sorted(data.keys())]
        else:
            self.games_list = []

        logger.info("تم تهيئة جميع الملفات بنجاح")

    def get_random_index(self, command: str, max_length: int) -> int:
        with content_lock:
            if len(self.used_indices[command]) >= max_length:
                self.used_indices[command] = []
            available_indices = [i for i in range(max_length) if i not in self.used_indices[command]]
            index = random.choice(available_indices) if available_indices else random.randint(0,max_length-1)
            self.used_indices[command].append(index)
            return index

    def get_content(self, command: str) -> Optional[str]:
        file_list = self.content_files.get(command, [])
        if not file_list: return None
        index = self.get_random_index(command, len(file_list))
        return file_list[index]

    def get_more_question(self) -> Optional[str]:
        if not self.more_questions: return None
        index = self.get_random_index("أكثر", len(self.more_questions))
        return self.more_questions[index]

    def get_riddle(self) -> Optional[dict]:
        if not self.riddles_list: return None
        index = self.get_random_index("لغز", len(self.riddles_list))
        return self.riddles_list[index]

    def get_poem(self) -> Optional[dict]:
        if not self.poems_list: return None
        index = self.get_random_index("شعر", len(self.poems_list))
        return self.poems_list[index]

    def get_quote(self) -> Optional[dict]:
        if not self.quotes_list: return None
        index = self.get_random_index("اقتباسات", len(self.quotes_list))
        return self.quotes_list[index]

# === تهيئة مدير المحتوى ===
content_manager = ContentManager()
content_manager.initialize()

# === القوائم الثابتة ===
def create_main_menu() -> QuickReply:
    """القائمة الرئيسية الثابتة"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="▫️ سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="▫️ تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="▫️ اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="▫️ أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="▫️ شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="▫️ اقتباسات", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="▫️ لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="▫️ فرق", text="فرق")),
        QuickReplyButton(action=MessageAction(label="▫️ لعبة", text="لعبه")),
    ])

# === Flex Messages البسيطة والأنيقة ===
def create_game_list_flex(games: list):
    game_buttons = []
    for i, game in enumerate(games[:10], 1):
        game_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(
                    label=f"{i}. {game.get('title', f'اللعبة {i}')}",
                    text=str(i)
                ),
                style='secondary',
                color='#000000',
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
                        text='الألعاب المتاحة',
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
                action=FlexMessageAction(label=f"{key}. {value}", text=key),
                style='secondary',
                color='#000000',
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
                        color='#000000',
                        align='center'
                    ),
                    TextComponent(
                        text='نتيجتك',
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
                                color='#000000',
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
                                action=FlexMessageAction(label='لعبة جديدة', text='لعبه'),
                                style='primary',
                                color='#000000',
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

def create_riddle_flex(riddle: dict):
    return FlexSendMessage(
        alt_text="لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text='لغز',
                        weight='bold',
                        size='xl',
                        color='#000000',
                        align='center'
                    ),
                    SeparatorComponent(margin='lg', color='#e0e0e0'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=riddle['question'],
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
                        contents=[
                            ButtonComponent(
                                action=FlexMessageAction(label='تلميح', text='لمح'),
                                style='secondary',
                                color='#000000',
                                height='sm'
                            ),
                            ButtonComponent(
                                action=FlexMessageAction(label='الإجابة', text='جاوب'),
                                style='primary',
                                color='#000000',
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
user_riddle_state: Dict[str, dict] = {}
user_sessions: Dict[str, dict] = {}

# === خريطة الأوامر ===
COMMANDS_MAP = {
    "سؤال":["سؤال","سوال","اسأله","اسئلة","اسأل"],
    "تحدي":["تحدي","تحديات","تحد"],
    "اعتراف":["اعتراف","اعترافات"],
    "أكثر":["أكثر","اكثر","زيادة"],
    "لغز":["لغز","الغاز","ألغاز"],
    "شعر":["شعر"],
    "اقتباسات":["اقتباسات","اقتباس","قول"]
}

def find_command(text:str) -> Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in COMMANDS_MAP.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# === دالة الحصول على اسم المستخدم ===
def get_user_display_name(user_id: str) -> str:
    """الحصول على اسم المستخدم من LINE"""
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.display_name
    except Exception as e:
        logger.error(f"خطأ في الحصول على اسم المستخدم: {e}")
        return "المستخدم"

# === دوال الألعاب ===
def calculate_result(answers: List[str], game_index: int) -> tuple:
    count = {"أ":0,"ب":0,"ج":0}
    for ans in answers:
        if ans in count: count[ans] +=1
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key,{}).get(
        most_common,f"إجابتك الأكثر: {most_common}\n\nنتيجتك تعكس شخصية فريدة!"
    )
    stats = f"أ: {count['أ']}  •  ب: {count['ب']}  •  ج: {count['ج']}"
    return result_text, stats

def handle_game_selection(event,user_id:str,num:int):
    if 1<=num<=len(content_manager.games_list):
        game_index = num-1
        user_game_state[user_id] = {"game_index":game_index,"question_index":0,"answers":[]}
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        progress = f"1/{len(game['questions'])}"
        
        flex_msg = create_game_question_flex(
            game.get('title', f'اللعبة {num}'),
            first_q,
            progress
        )
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
            
            flex_msg = create_game_question_flex(
                game.get('title', 'اللعبة'),
                q,
                progress
            )
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            result_text, stats = calculate_result(state["answers"], state["game_index"])
            username = get_user_display_name(user_id)
            flex_msg = create_game_result_flex(result_text, stats, username)
            line_bot_api.reply_message(event.reply_token, flex_msg)
            del user_game_state[user_id]

# === دوال المحتوى ===
def handle_content_command(event, command: str):
    user_id = event.source.user_id
    username = get_user_display_name(user_id)
    
    if command=="لغز":
        riddle = content_manager.get_riddle()
        if not riddle:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="لا توجد ألغاز متاحة حالياً.", quick_reply=create_main_menu())
            )
        else:
            user_riddle_state[user_id] = riddle
            flex_msg = create_riddle_flex(riddle)
            line_bot_api.reply_message(event.reply_token, flex_msg)
            
    elif command=="شعر":
        poem = content_manager.get_poem()
        if not poem:
            content = "لا يوجد شعر متاح حالياً."
        else:
            content = f"{poem.get('text', '')}\n\n— {poem.get('poet', 'مجهول')}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content, quick_reply=create_main_menu())
        )
            
    elif command=="اقتباسات":
        quote = content_manager.get_quote()
        if not quote:
            content = "لا توجد اقتباسات متاحة حالياً."
        else:
            content = f"{quote.get('text','')}\n\n— {quote.get('author','مجهول')}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content, quick_reply=create_main_menu())
        )
    else:
        content = content_manager.get_content(command)
        if content:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=content, quick_reply=create_main_menu())
            )

# === Webhook ===
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    if user_id in user_game_state:
        handle_game_answer(event,user_id,text)
        return
    
    if text.isdigit():
        handle_game_selection(event,user_id,int(text))
        return
    
    command = find_command(text)
    if command:
        handle_content_command(event, command)
        return
    
    if text.lower() in ["فرق","لعبه"]:
        challenge = get_difference_challenge() if text.lower()=="فرق" else None
        if challenge:
            messages = [
                ImageSendMessage(original_content_url=challenge["original"], preview_image_url=challenge["original"]),
                ImageSendMessage(original_content_url=challenge["changed"], preview_image_url=challenge["changed"]),
                TextSendMessage(text="كم عدد الاختلافات؟", quick_reply=create_main_menu())
            ]
            line_bot_api.reply_message(event.reply_token, messages)
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="لا توجد فروقات حالياً.", quick_reply=create_main_menu()))
        return
    
    # إذا لم يتعرف على أي أمر، تجاهل الرسالة
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="استخدم الأزرار الثابتة للتفاعل.", quick_reply=create_main_menu()))

# === بدء السيرفر ===
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء الخادم على المنفذ {port}")
    app.run(host='0.0.0.0', port=port)
