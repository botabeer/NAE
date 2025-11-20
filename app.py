import json
import os
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Union
from threading import Lock
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction, BubbleContainer,
    BoxComponent, TextComponent, ButtonComponent, MessageAction as FlexMessageAction,
    SeparatorComponent, FillerComponent
)

# ==================== إعداد Logging ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==================== إعداد متغيرات البيئة ====================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==================== Locks للتزامن ====================
content_lock = Lock()
db_lock = Lock()
players_lock = Lock()
names_cache_lock = Lock()

# ==================== الألوان الملكية ====================
COLORS = {
    # الألوان الأساسية
    'primary': '#6B21A8',
    'secondary': '#9333EA',
    'accent': '#A855F7',
    'light': '#D8B4FE',
    
    # الخلفيات
    'background': '#FFFFFF',
    'glass_bg': '#FAF8FC',
    'card_bg': '#FEFCFF',
    'card_hover': '#F9F5FF',
    
    # النصوص
    'text_main': '#1F2937',
    'text_secondary': '#581C87',
    'text_light': '#6B7280',
    'text_muted': '#9CA3AF',
    
    # الحدود
    'border': '#EDE9FE',
    'separator': '#F3E8FF',
    
    # الحالات
    'success': '#10B981',
    'warning': '#F59E0B',
    'error': '#EF4444',
    
    # الشارات
    'badge_bg': '#F3E8FF',
    'badge_text': '#6B21A8',
}

# ==================== قاعدة البيانات ====================
DB_PATH = "bot_database.db"

def init_db():
    """إنشاء قاعدة البيانات وجداولها"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                total_points INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                last_played TEXT,
                registered_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                game_type TEXT,
                points INTEGER,
                won INTEGER,
                played_at TEXT
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_points ON users(total_points DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON game_history(user_id)')
        
        conn.commit()
        conn.close()
        logger.info("تم إنشاء قاعدة البيانات بنجاح")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_user_exists(user_id: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (user_id, registered_at) VALUES (?, ?)',
                (user_id, datetime.now().isoformat())
            )
            conn.commit()
        conn.close()

def update_user_points(user_id: str, display_name: str, points: int, won: bool, game_type: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute('''
                UPDATE users 
                SET display_name = ?,
                    total_points = total_points + ?,
                    games_played = games_played + 1,
                    wins = wins + ?,
                    last_played = ?
                WHERE user_id = ?
            ''', (display_name, points, 1 if won else 0, datetime.now().isoformat(), user_id))
        else:
            cursor.execute('''
                INSERT INTO users (user_id, display_name, total_points, games_played, wins, last_played, registered_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            ''', (user_id, display_name, points, 1 if won else 0, datetime.now().isoformat(), datetime.now().isoformat()))
        
        cursor.execute('''
            INSERT INTO game_history (user_id, game_type, points, won, played_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, game_type, points, 1 if won else 0, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()

def get_user_stats(user_id: str) -> Optional[Dict]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None

def get_leaderboard(limit: int = 10) -> List[Dict]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, display_name, total_points, games_played, wins
            FROM users
            ORDER BY total_points DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

# ==================== نظام المستخدمين ====================
registered_players = set()
user_names_cache = {}
user_message_count = {}

def get_user_profile_safe(user_id: str) -> str:
    with names_cache_lock:
        if user_id in user_names_cache:
            return user_names_cache[user_id]
    
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
        
        with names_cache_lock:
            user_names_cache[user_id] = display_name
        
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET display_name = ? WHERE user_id = ?', (display_name, user_id))
            conn.commit()
            conn.close()
        
        return display_name
    
    except LineBotApiError as e:
        if e.status_code == 404:
            logger.warning(f"المستخدم {user_id[-4:]} لم يبدأ المحادثة بعد")
        else:
            logger.error(f"خطأ في LINE API: {e}")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
    
    fallback_name = f"لاعب {user_id[-4:]}"
    
    with names_cache_lock:
        user_names_cache[user_id] = fallback_name
    
    return fallback_name

def check_rate_limit(user_id: str, max_messages: int = 30, time_window: int = 60) -> bool:
    now = datetime.now()
    
    if user_id not in user_message_count:
        user_message_count[user_id] = {
            'count': 1,
            'reset_time': now + timedelta(seconds=time_window)
        }
        return True
    
    user_data = user_message_count[user_id]
    
    if now >= user_data['reset_time']:
        user_data['count'] = 1
        user_data['reset_time'] = now + timedelta(seconds=time_window)
        return True
    
    if user_data['count'] >= max_messages:
        return False
    
    user_data['count'] += 1
    return True

# ==================== مدير المحتوى ====================
class ContentManager:
    def __init__(self):
        self.content_files: Dict[str, List[str]] = {}
        self.mention_questions: List[str] = []
        self.riddles_list: List[dict] = []
        self.emoji_puzzles: List[dict] = []
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
            logger.error(f"خطأ في قراءة JSON {filename}: {e}")
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }

        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["منشن", "إيموجي", "لغز", "شعر", "اقتباسات"]:
            self.used_indices[key] = []

        self.mention_questions = self.load_file_lines("more_questions.txt")
        self.riddles_list = self.load_json_file("riddles.json")
        self.emoji_puzzles = self.load_json_file("emojis.json")
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
            index = random.choice(available_indices) if available_indices else random.randint(0, max_length-1)
            self.used_indices[command].append(index)
            return index

    def get_content(self, command: str) -> Optional[str]:
        file_list = self.content_files.get(command, [])
        if not file_list: return None
        index = self.get_random_index(command, len(file_list))
        return file_list[index]

    def get_mention_question(self) -> Optional[str]:
        if not self.mention_questions: return None
        index = self.get_random_index("منشن", len(self.mention_questions))
        return self.mention_questions[index]

    def get_riddle(self) -> Optional[dict]:
        if not self.riddles_list: return None
        index = self.get_random_index("لغز", len(self.riddles_list))
        return self.riddles_list[index]

    def get_emoji_puzzle(self) -> Optional[dict]:
        if not self.emoji_puzzles: return None
        index = self.get_random_index("إيموجي", len(self.emoji_puzzles))
        return self.emoji_puzzles[index]

    def get_poem(self) -> Optional[dict]:
        if not self.poems_list: return None
        index = self.get_random_index("شعر", len(self.poems_list))
        return self.poems_list[index]

    def get_quote(self) -> Optional[dict]:
        if not self.quotes_list: return None
        index = self.get_random_index("اقتباسات", len(self.quotes_list))
        return self.quotes_list[index]

# تهيئة المدير
content_manager = ContentManager()
content_manager.initialize()
init_db()

# ==================== Flex Messages ====================

def create_welcome_flex():
    """بطاقة الترحيب"""
    return FlexSendMessage(
        alt_text="مرحباً بك",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text='مرحباً بك',
                                weight='bold',
                                size='xxl',
                                color=COLORS['text_secondary'],
                                align='center'
                            ),
                            TextComponent(
                                text='بوت التفاعل الذكي',
                                size='sm',
                                color=COLORS['text_light'],
                                align='center',
                                margin='sm'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    SeparatorComponent(margin='xl', color=COLORS['separator']),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            create_menu_item('سؤال', 'أسئلة متنوعة'),
                            create_menu_item('تحدي', 'تحديات ممتعة'),
                            create_menu_item('اعتراف', 'اعترافات صادقة'),
                            create_menu_item('منشن', 'أسئلة المنشن'),
                            create_menu_item('لعبة', 'ألعاب الشخصية'),
                            create_menu_item('ترتيب', 'المتصدرين'),
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_menu_item(title: str, desc: str):
    """عنصر قائمة"""
    return BoxComponent(
        layout='vertical',
        spacing='xs',
        contents=[
            TextComponent(
                text=title,
                weight='bold',
                size='md',
                color=COLORS['primary']
            ),
            TextComponent(
                text=desc,
                size='xs',
                color=COLORS['text_light']
            )
        ],
        paddingAll='12px',
        backgroundColor=COLORS['card_bg'],
        cornerRadius='12px'
    )

def create_content_flex(title: str, content: str, category: str):
    """بطاقة المحتوى"""
    return FlexSendMessage(
        alt_text=title,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=title,
                                weight='bold',
                                size='xl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=content,
                                size='lg',
                                color=COLORS['text_main'],
                                wrap=True,
                                lineSpacing='8px'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['card_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='horizontal',
                        margin='lg',
                        contents=[
                            TextComponent(
                                text=category,
                                size='sm',
                                color=COLORS['badge_text']
                            )
                        ],
                        paddingAll='8px',
                        backgroundColor=COLORS['badge_bg'],
                        cornerRadius='20px',
                        paddingStart='16px',
                        paddingEnd='16px',
                        alignItems='center',
                        justifyContent='center'
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_puzzle_flex(puzzle: dict, puzzle_type: str):
    """بطاقة اللغز"""
    return FlexSendMessage(
        alt_text=f"لغز {puzzle_type}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=f'لغز {puzzle_type}',
                                weight='bold',
                                size='xl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        backgroundColor=COLORS['glass_bg'],
                        paddingAll='16px',
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=puzzle['question'],
                                size='xl',
                                color=COLORS['text_main'],
                                wrap=True,
                                align='center',
                                lineSpacing='8px',
                                weight='bold'
                            )
                        ],
                        paddingAll='24px',
                        backgroundColor=COLORS['card_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            ButtonComponent(
                                action=FlexMessageAction(label='تلميح', text='لمح'),
                                style='secondary',
                                color=COLORS['secondary'],
                                height='md'
                            ),
                            ButtonComponent(
                                action=FlexMessageAction(label='الإجابة', text='جاوب'),
                                style='primary',
                                color=COLORS['primary'],
                                height='md'
                            )
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_poem_flex(poem: dict):
    """بطاقة الشعر"""
    return FlexSendMessage(
        alt_text="شعر",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text='قصيدة',
                                weight='bold',
                                size='xl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=poem.get('text', ''),
                                size='lg',
                                color=COLORS['text_main'],
                                wrap=True,
                                align='center',
                                lineSpacing='12px'
                            )
                        ],
                        paddingAll='24px',
                        backgroundColor=COLORS['card_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            SeparatorComponent(color=COLORS['separator']),
                            TextComponent(
                                text=poem.get('poet', 'مجهول'),
                                size='md',
                                color=COLORS['text_secondary'],
                                align='end',
                                margin='md',
                                weight='bold'
                            )
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_quote_flex(quote: dict):
    """بطاقة الاقتباس"""
    return FlexSendMessage(
        alt_text="اقتباس",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=quote.get('text', ''),
                                size='xl',
                                color=COLORS['text_main'],
                                wrap=True,
                                align='center',
                                lineSpacing='8px'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=quote.get('author', 'مجهول'),
                                size='lg',
                                color=COLORS['primary'],
                                align='center',
                                weight='bold'
                            )
                        ],
                        paddingAll='12px',
                        backgroundColor=COLORS['badge_bg'],
                        cornerRadius='20px'
                    )
                ],
                paddingAll='28px',
                backgroundColor=COLORS['card_bg']
            )
        )
    )

def create_leaderboard_flex(players: List[Dict]):
    """قائمة المتصدرين"""
    player_items = []
    
    for i, player in enumerate(players[:10], 1):
        rank_display = f"#{i}"
        name = player.get('display_name', f"لاعب {player['user_id'][-4:]}")
        points = player.get('total_points', 0)
        games = player.get('games_played', 0)
        
        if i == 1:
            bg_color = '#FEF3C7'
        elif i == 2:
            bg_color = '#F3F4F6'
        elif i == 3:
            bg_color = '#FED7AA'
        else:
            bg_color = COLORS['card_bg']
        
        player_items.append(
            BoxComponent(
                layout='horizontal',
                spacing='md',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=rank_display,
                                size='lg',
                                align='center',
                                weight='bold',
                                color=COLORS['primary']
                            )
                        ],
                        flex=0,
                        width='50px',
                        alignItems='center',
                        justifyContent='center'
                    ),
                    BoxComponent(
                        layout='vertical',
                        flex=1,
                        contents=[
                            TextComponent(
                                text=name,
                                size='md',
                                color=COLORS['text_main'],
                                weight='bold'
                            ),
                            TextComponent(
                                text=f"{games} لعبة",
                                size='xs',
                                color=COLORS['text_light'],
                                margin='xs'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=f"{points}",
                                size='xl',
                                color=COLORS['primary'],
                                weight='bold',
                                align='end'
                            ),
                            TextComponent(
                                text='نقطة',
                                size='xs',
                                color=COLORS['text_light'],
                                align='end'
                            )
                        ],
                        flex=0,
                        alignItems='end'
                    )
                ],
                paddingAll='16px',
                backgroundColor=bg_color,
                cornerRadius='12px',
                margin='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text="قائمة المتصدرين",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text='قائمة المتصدرين',
                                weight='bold',
                                size='xxl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='none',
                        contents=player_items if player_items else [
                            TextComponent(
                                text='لا يوجد لاعبون بعد',
                                size='md',
                                color=COLORS['text_light'],
                                align='center'
                            )
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_user_stats_flex(stats: Dict, display_name: str):
    """إحصائيات المستخدم"""
    return FlexSendMessage(
        alt_text="إحصائياتك",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text='إحصائياتك',
                                weight='bold',
                                size='xl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            create_stat_row('الاسم', display_name),
                            create_stat_row('النقاط', str(stats.get('total_points', 0))),
                            create_stat_row('الألعاب', str(stats.get('games_played', 0))),
                            create_stat_row('الانتصارات', str(stats.get('wins', 0))),
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_stat_row(label: str, value: str):
    """صف إحصائية"""
    return BoxComponent(
        layout='horizontal',
        contents=[
            TextComponent(
                text=label,
                size='md',
                color=COLORS['text_light'],
                flex=1
            ),
            TextComponent(
                text=value,
                size='lg',
                color=COLORS['primary'],
                weight='bold',
                flex=1,
                align='end'
            )
        ],
        paddingAll='16px',
        backgroundColor=COLORS['card_bg'],
        cornerRadius='12px'
    )

def create_answer_flex(answer: str, answer_type: str):
    """بطاقة الإجابة/التلميح"""
    color = COLORS['success'] if answer_type == 'الإجابة الصحيحة' else COLORS['secondary']
    
    return FlexSendMessage(
        alt_text=answer_type,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=answer_type,
                                weight='bold',
                                size='xl',
                                color=color,
                                align='center'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=answer,
                                size='xl',
                                color=COLORS['text_main'],
                                wrap=True,
                                align='center',
                                lineSpacing='8px',
                                weight='bold'
                            )
                        ],
                        paddingAll='24px',
                        backgroundColor=COLORS['card_bg'],
                        cornerRadius='16px'
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_game_list_flex(games: list):
    """قائمة الألعاب"""
    game_buttons = []
    for i, game in enumerate(games[:10], 1):
        game_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(
                    label=f"{i}. {game.get('title', f'اللعبة {i}')}",
                    text=str(i)
                ),
                style='secondary',
                color=COLORS['primary'],
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text="الألعاب المتاحة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text='الألعاب المتاحة',
                                weight='bold',
                                size='xl',
                                color=COLORS['text_secondary'],
                                align='center'
                            )
                        ],
                        paddingAll='20px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='16px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='sm',
                        contents=game_buttons
                    )
                ],
                paddingAll='24px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_game_question_flex(game_title: str, question: dict, progress: str):
    """سؤال اللعبة"""
    option_buttons = []
    for key, value in question['options'].items():
        option_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(label=f"{key}. {value}", text=key),
                style='secondary',
                color=COLORS['primary'],
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text=game_title,
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
                                color=COLORS['primary'],
                                flex=1
                            ),
                            TextComponent(
                                text=progress,
                                size='xs',
                                color=COLORS['text_light'],
                                flex=0,
                                align='end'
                            )
                        ]
                    ),
                    SeparatorComponent(margin='md', color=COLORS['border']),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(
                                text=question['question'],
                                size='md',
                                color=COLORS['text_main'],
                                wrap=True,
                                lineSpacing='6px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='8px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        spacing='sm',
                        contents=option_buttons
                    )
                ],
                paddingAll='20px',
                backgroundColor=COLORS['background']
            )
        )
    )

def create_game_result_flex(result_text: str, stats: str, points: int):
    """نتيجة اللعبة"""
    return FlexSendMessage(
        alt_text="نتيجة اللعبة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text='نتيجتك',
                        weight='bold',
                        size='xl',
                        color=COLORS['primary'],
                        align='center'
                    ),
                    SeparatorComponent(margin='md', color=COLORS['border']),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(
                                text=result_text,
                                size='md',
                                color=COLORS['text_main'],
                                wrap=True,
                                lineSpacing='6px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor=COLORS['glass_bg'],
                        cornerRadius='8px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='md',
                        contents=[
                            TextComponent(
                                text=stats,
                                size='sm',
                                color=COLORS['text_light'],
                                wrap=True,
                                align='center'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='md',
                        contents=[
                            TextComponent(
                                text=f'حصلت على {points} نقطة',
                                size='md',
                                color=COLORS['success'],
                                weight='bold',
                                align='center'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=FlexMessageAction(label='لعبة جديدة', text='لعبة'),
                                style='primary',
                                color=COLORS['primary'],
                                height='sm'
                            )
                        ]
                    )
                ],
                paddingAll='20px',
                backgroundColor=COLORS['background']
            )
        )
    )

# ==================== القوائم ====================
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="منشن", text="منشن")),
        QuickReplyButton(action=MessageAction(label="المزيد", text="المزيد")),
    ])

def create_secondary_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="اقتباسات", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="إيموجي", text="إيموجي")),
        QuickReplyButton(action=MessageAction(label="الرئيسية", text="القائمة")),
    ])

# ==================== حالات المستخدمين ====================
user_game_state: Dict[str, dict] = {}
user_riddle_state: Dict[str, dict] = {}
user_emoji_state: Dict[str, dict] = {}

# ==================== خريطة الأوامر ====================
COMMANDS_MAP = {
    "سؤال": ["سؤال", "سوال", "اسأله", "اسئلة"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "منشن": ["منشن", "اكثر", "أكثر", "زيادة"],
    "لغز": ["لغز", "الغاز", "ألغاز"],
    "إيموجي": ["إيموجي", "ايموجي", "emoji"],
    "شعر": ["شعر"],
    "اقتباسات": ["اقتباسات", "اقتباس", "قول"]
}

def find_command(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in COMMANDS_MAP.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# ==================== دوال الألعاب ====================
def calculate_result(answers: List[str], game_index: int) -> tuple:
    count = {"أ": 0, "ب": 0, "ج": 0}
    for ans in answers:
        if ans in count:
            count[ans] += 1
    
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key, {}).get(
        most_common, f"إجابتك الأكثر: {most_common}\n\nنتيجتك تعكس شخصية فريدة"
    )
    stats = f"أ: {count['أ']}  •  ب: {count['ب']}  •  ج: {count['ج']}"
    
    total_questions = len(answers)
    points = total_questions * 5
    
    return result_text, stats, points

def handle_game_selection(event, user_id: str, num: int):
    if 1 <= num <= len(content_manager.games_list):
        game_index = num - 1
        user_game_state[user_id] = {
            "game_index": game_index,
            "question_index": 0,
            "answers": []
        }
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        progress = f"1/{len(game['questions'])}"
        
        flex_msg = create_game_question_flex(
            game.get('title', f'اللعبة {num}'),
            first_q,
            progress
        )
        safe_reply(event.reply_token, flex_msg)

def handle_game_answer(event, user_id: str, text: str):
    state = user_game_state.get(user_id)
    if not state:
        return
    
    answer_map = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج"}
    answer = answer_map.get(text.lower(), text)
    
    if answer in ["أ", "ب", "ج"]:
        state["answers"].append(answer)
        game = content_manager.games_list[state["game_index"]]
        state["question_index"] += 1
        
        if state["question_index"] < len(game["questions"]):
            q = game["questions"][state["question_index"]]
            progress = f"{state['question_index']+1}/{len(game['questions'])}"
            
            flex_msg = create_game_question_flex(
                game.get('title', 'اللعبة'),
                q,
                progress
            )
            safe_reply(event.reply_token, flex_msg)
        else:
            result_text, stats, points = calculate_result(state["answers"], state["game_index"])
            
            display_name = get_user_profile_safe(user_id)
            game_title = game.get('title', 'لعبة شخصية')
            update_user_points(user_id, display_name, points, True, game_title)
            
            flex_msg = create_game_result_flex(result_text, stats, points)
            safe_reply(event.reply_token, flex_msg)
            del user_game_state[user_id]

# ==================== دوال المحتوى ====================
def handle_content_command(event, command: str):
    user_id = event.source.user_id
    
    if command == "لغز":
        riddle = content_manager.get_riddle()
        if not riddle:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="لا توجدألغاز متاحة حالياً", quick_reply=create_main_menu())
            )
        else:
            user_riddle_state[user_id] = riddle
            flex_msg = create_puzzle_flex(riddle, "عادي")
            safe_reply(event.reply_token, flex_msg)
    
    elif command == "إيموجي":
        emoji_puzzle = content_manager.get_emoji_puzzle()
        if not emoji_puzzle:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="لا توجدألغاز إيموجي متاحة حالياً", quick_reply=create_secondary_menu())
            )
        else:
            user_emoji_state[user_id] = emoji_puzzle
            flex_msg = create_puzzle_flex(emoji_puzzle, "إيموجي")
            safe_reply(event.reply_token, flex_msg)
            
    elif command == "شعر":
        poem = content_manager.get_poem()
        if not poem:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="لا يوجد شعر متاح حالياً", quick_reply=create_secondary_menu())
            )
        else:
            flex_msg = create_poem_flex(poem)
            safe_reply(event.reply_token, flex_msg)
            
    elif command == "اقتباسات":
        quote = content_manager.get_quote()
        if not quote:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="لا توجد اقتباسات متاحة حالياً", quick_reply=create_secondary_menu())
            )
        else:
            flex_msg = create_quote_flex(quote)
            safe_reply(event.reply_token, flex_msg)
            
    elif command == "منشن":
        question = content_manager.get_mention_question()
        if not question:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="لا توجد أسئلة منشن متاحة حالياً", quick_reply=create_main_menu())
            )
        else:
            flex_msg = create_content_flex("سؤال منشن", question, "منشن")
            safe_reply(event.reply_token, flex_msg)
            
    else:
        content = content_manager.get_content(command)
        if not content:
            safe_reply(
                event.reply_token,
                TextSendMessage(text=f"لا توجد بيانات متاحة في قسم {command}", quick_reply=create_main_menu())
            )
        else:
            title_map = {"سؤال": "سؤال", "تحدي": "تحدي", "اعتراف": "اعتراف"}
            flex_msg = create_content_flex(
                title_map.get(command, command),
                content,
                command
            )
            safe_reply(event.reply_token, flex_msg)

def handle_answer_command(event, user_id: str):
    if user_id in user_riddle_state:
        riddle = user_riddle_state.pop(user_id)
        flex_msg = create_answer_flex(riddle['answer'], "الإجابة الصحيحة")
        safe_reply(event.reply_token, flex_msg)
    
    elif user_id in user_emoji_state:
        emoji = user_emoji_state.pop(user_id)
        flex_msg = create_answer_flex(emoji['answer'], "الإجابة الصحيحة")
        safe_reply(event.reply_token, flex_msg)

def handle_hint_command(event, user_id: str):
    hint_text = None
    
    if user_id in user_riddle_state:
        riddle = user_riddle_state[user_id]
        hint_text = riddle.get('hint', 'لا يوجد تلميح')
    elif user_id in user_emoji_state:
        emoji = user_emoji_state[user_id]
        hint_text = emoji.get('hint', 'لا يوجد تلميح')
    
    if hint_text:
        flex_msg = create_answer_flex(hint_text, "تلميح")
        safe_reply(event.reply_token, flex_msg)

def safe_reply(reply_token: str, message):
    """إرسال الرد بطريقة آمنة"""
    try:
        line_bot_api.reply_message(reply_token, message)
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")

# ==================== Routes ====================
@app.route("/", methods=["GET"])
def home():
    return "البوت يعمل بنجاح", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy", "service": "line-bot"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("توقيع غير صالح")
        abort(400)
    except Exception as e:
        logger.error(f"خطأ في معالجة الطلب: {e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()

    try:
        with players_lock:
            if user_id not in registered_players:
                registered_players.add(user_id)
                ensure_user_exists(user_id)
        
        if not check_rate_limit(user_id):
            safe_reply(
                event.reply_token,
                TextSendMessage(text="يرجى الانتظار قليلاً قبل إرسال رسالة جديدة")
            )
            return
        
        if text_lower in ["مساعدة", "help", "بداية", "start", "القائمة", "مرحبا"]:
            safe_reply(event.reply_token, create_welcome_flex())
            return
        
        if text_lower in ["ترتيب", "المتصدرين", "leaderboard", "top"]:
            players = get_leaderboard(10)
            flex_msg = create_leaderboard_flex(players)
            safe_reply(event.reply_token, flex_msg)
            return
        
        if text_lower in ["احصائياتي", "نقاطي", "stats", "profile"]:
            stats = get_user_stats(user_id)
            if stats:
                display_name = get_user_profile_safe(user_id)
                flex_msg = create_user_stats_flex(stats, display_name)
                safe_reply(event.reply_token, flex_msg)
            else:
                safe_reply(
                    event.reply_token,
                    TextSendMessage(text="لم تلعب أي لعبة بعد", quick_reply=create_main_menu())
                )
            return
        
        if text_lower in ["المزيد", "more", "ثانوي"]:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="اختر من القائمة", quick_reply=create_secondary_menu())
            )
            return
        
        command = find_command(text)
        if command:
            handle_content_command(event, command)
            return

        if text_lower in ["جاوب", "الجواب", "الاجابة", "اجابة"]:
            handle_answer_command(event, user_id)
            return

        if text_lower in ["لمح", "تلميح", "hint"]:
            handle_hint_command(event, user_id)
            return

        if text_lower in ["لعبة", "لعبه", "العاب", "ألعاب", "game"]:
            if content_manager.games_list:
                flex_msg = create_game_list_flex(content_manager.games_list)
                safe_reply(event.reply_token, flex_msg)
            else:
                safe_reply(
                    event.reply_token,
                    TextSendMessage(text="لا توجد ألعاب متاحة حالياً", quick_reply=create_main_menu())
                )
            return

        if text.isdigit():
            handle_game_selection(event, user_id, int(text))
            return

        if user_id in user_game_state:
            handle_game_answer(event, user_id, text)
            return

        safe_reply(
            event.reply_token,
            TextSendMessage(text="مرحباً! اختر من القائمة أدناه", quick_reply=create_main_menu())
        )

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)
        try:
            safe_reply(
                event.reply_token,
                TextSendMessage(text="حدث خطأ، يرجى المحاولة مرة أخرى", quick_reply=create_main_menu())
            )
        except:
            pass

# ==================== تشغيل التطبيق ====================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
