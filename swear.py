import telebot
from telebot.apihelper import ApiTelegramException
import schedule
import time
import random
import threading
import logging
import json
from pathlib import Path
from config import Config
from converstion_complete import Colocutor
from swearing_gen import SwearingGenerator
from news_post_gen import NewsPostGenerator
from news_post_gen_v2 import NewsPostGenerator_v2
#from voice_gen import generate_audio, get_all_voices
from tts_gen import TTSGenerator
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)
# voices = get_all_voices()
# logger.info(voices)
sample_rate = 48000
tts = TTSGenerator(sample_rate)
silero_voices = tts.get_all_voices()
logger.info(silero_voices)


def get_random_voice(voices):
    return voices[random.randint(0, len(voices)-1)]

swearing_generator = SwearingGenerator()
colocutor = Colocutor()
news_post_creator = NewsPostGenerator_v2()


STACK_SIZE = 16

#SWEAR_PROMPT = Config.SWEAR_PROMPT # "Обзови Алису. Пол: Женский. Возраст: 20 лет."

SWEAR_PERIOD = (90,180)
REMINDER_PERIOD = (90*60, 180*60)
#REMINDER_PERIOD = (2, 4)
TALK_PERIOD = (15*60,240*60)
NEWS_PERIOD = (180*60,360*60)
#NEWS_PERIOD = (2,10)
BOT_MESSAGE_HISTORY_FILE = Path(__file__).with_name("bot_message_history.json")
BOT_MESSAGE_RETENTION_SECONDS = 48 * 60 * 60
CLEANUP_STATUS_TTL_SECONDS = 10
MAX_TRACKED_MESSAGES_PER_CHAT = 5000
TELEGRAM_DELETE_MESSAGES_LIMIT = 100


def escape_markdown_v2(text):
    # Characters that need escaping
    special_chars = r'_[]()~`>#+=|{}.!-'  # Added '-' to the list

    def escape_char(c):
        return '\\' + c if c in special_chars else c

    def handle_formatting(text):
        # Handle bold (asterisks)
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)  # Replace ** with *
        text = re.sub(r'(?<!\\)\*(.+?)(?<!\\)\*', r'*\1*', text)  # Keep single * as is

        # Handle italic (underscores)
        text = re.sub(r'(?<!\\)_(.+?)(?<!\\)_', r'*\1*', text)  # Replace _ with *

        return text

    # First, handle formatting (bold and italic)
    text = handle_formatting(text)

    # Then escape special characters, preserving existing escapes
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text) and text[i+1] in f"{special_chars}*":
            result.append(text[i:i+2])  # Keep existing escapes
            i += 2
        elif text[i] == '*':
            result.append('*')  # Keep * for formatting
            i += 1
        elif text[i] in special_chars:
            result.append('\\' + text[i])  # Escape special chars
            i += 1
        else:
            result.append(text[i])  # Regular character
            i += 1

    return ''.join(result)

def _normalize_tracked_messages(raw_messages):
    now = time.time()
    normalized = []
    if not isinstance(raw_messages, list):
        return normalized

    for item in raw_messages:
        if isinstance(item, dict):
            message_id = item.get("message_id")
            sent_at = item.get("sent_at", now)
        else:
            message_id = item
            sent_at = now

        if not isinstance(message_id, int):
            continue

        try:
            sent_at = float(sent_at)
        except (TypeError, ValueError):
            sent_at = now

        if now - sent_at <= BOT_MESSAGE_RETENTION_SECONDS:
            normalized.append({"message_id": message_id, "sent_at": sent_at})

    return normalized[-MAX_TRACKED_MESSAGES_PER_CHAT:]

def _load_bot_message_history():
    if not BOT_MESSAGE_HISTORY_FILE.exists():
        return {}

    try:
        raw_history = json.loads(BOT_MESSAGE_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Unable to load bot message history: {e}")
        return {}

    if not isinstance(raw_history, dict):
        return {}

    history = {}
    for chat_id, messages in raw_history.items():
        normalized = _normalize_tracked_messages(messages)
        if normalized:
            history[str(chat_id)] = normalized

    return history

def _save_bot_message_history():
    try:
        BOT_MESSAGE_HISTORY_FILE.write_text(
            json.dumps(bot_message_history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error(f"Unable to save bot message history: {e}")

def _prune_tracked_messages(chat_id):
    chat_key = str(chat_id)
    pruned = _normalize_tracked_messages(bot_message_history.get(chat_key, []))
    if pruned:
        bot_message_history[chat_key] = pruned
    else:
        bot_message_history.pop(chat_key, None)

def track_bot_message(message):
    if message is None:
        return message

    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return message

    with bot_message_history_lock:
        chat_key = str(chat_id)
        bot_message_history.setdefault(chat_key, []).append(
            {"message_id": message_id, "sent_at": time.time()}
        )
        _prune_tracked_messages(chat_id)
        _save_bot_message_history()

    return message

def forget_bot_message(chat_id, message_id):
    forget_bot_messages(chat_id, [message_id])

def forget_bot_messages(chat_id, message_ids):
    message_ids = set(message_ids)
    with bot_message_history_lock:
        chat_key = str(chat_id)
        messages = bot_message_history.get(chat_key, [])
        messages = [item for item in messages if item["message_id"] not in message_ids]
        if messages:
            bot_message_history[chat_key] = messages
        else:
            bot_message_history.pop(chat_key, None)
        _save_bot_message_history()

def send_tracked_message(chat_id, *args, **kwargs):
    return track_bot_message(bot.send_message(chat_id, *args, **kwargs))

def reply_tracked_message(message, *args, **kwargs):
    return track_bot_message(bot.reply_to(message, *args, **kwargs))

def send_tracked_voice(chat_id, *args, **kwargs):
    return track_bot_message(bot.send_voice(chat_id, *args, **kwargs))

def delete_tracked_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
        forget_bot_message(chat_id, message_id)
        return True
    except ApiTelegramException as e:
        logger.warning(f"Failed to delete bot message {message_id} in chat {chat_id}: {e}")
        return False

def delete_tracked_message_later(chat_id, message_id, delay_seconds):
    timer = threading.Timer(delay_seconds, delete_tracked_message, args=(chat_id, message_id))
    timer.daemon = True
    timer.start()

def cleanup_tracked_bot_messages(chat_id):
    with bot_message_history_lock:
        _prune_tracked_messages(chat_id)
        messages = list(bot_message_history.get(str(chat_id), []))

    cleared = 0
    failed = 0
    message_ids = [item["message_id"] for item in messages]

    for index in range(0, len(message_ids), TELEGRAM_DELETE_MESSAGES_LIMIT):
        batch = message_ids[index:index + TELEGRAM_DELETE_MESSAGES_LIMIT]
        try:
            bot.delete_messages(chat_id, batch)
            forget_bot_messages(chat_id, batch)
            cleared += len(batch)
        except ApiTelegramException as e:
            logger.warning(f"Bulk delete failed for chat {chat_id}: {e}")
            for message_id in batch:
                if delete_tracked_message(chat_id, message_id):
                    cleared += 1
                else:
                    failed += 1

    with bot_message_history_lock:
        _prune_tracked_messages(chat_id)
        _save_bot_message_history()

    return cleared, failed

bot_message_history_lock = threading.Lock()
bot_message_history = _load_bot_message_history()

class PeriodicMessageSender:
    def __init__(self, chat_id, bot, message_generator, voice_generator, sending_interval_range):
        self.chat_id = chat_id
        self.bot = bot
        self.message_generator = message_generator
        self.voice_generator = voice_generator
        self.sending_interval_range = sending_interval_range
        self.active = False
        self.job = None

    def send_message(self):
        if not self.active:
            return
        try:
            message = self.message_generator(self)
            track_bot_message(self.bot.send_message(self.chat_id, escape_markdown_v2(message), parse_mode='MarkdownV2'))
            if self.voice_generator and random.randint(0, 9) >= 7:
                voice = self.voice_generator(self, message)
                if voice is not None:
                    track_bot_message(self.bot.send_voice(self.chat_id, voice))
            logger.info(f"Sent message {message} to chat {self.chat_id}")
        except ApiTelegramException as e:
            logger.error(f"Failed to send message to chat {self.chat_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when sending message to chat {self.chat_id}: {e}")
        finally:
            self.schedule_next_message()

    def schedule_next_message(self):
        if self.job:
            schedule.cancel_job(self.job)
        
        interval = random.randint(*self.sending_interval_range)
        self.job = schedule.every(interval).seconds.do(self.send_message)
        logger.info(f"Scheduled new job for chat {self.chat_id} with {interval} seconds interval")

    def start(self):
        if not self.active:
            self.active = True
            self.schedule_next_message()
            logger.info(f"Started periodic messages for chat {self.chat_id}")

    def stop(self):
        if self.active:
            self.active = False
            if self.job:
                schedule.cancel_job(self.job)
            logger.info(f"Stopped periodic messages for chat {self.chat_id}")

# Message generators
def swear_generator(sender):
    chat_id = sender.chat_id
    prompt = chat_prompts.get(chat_id, Config.SWEAR_PROMPT)
    return swearing_generator.get_answer(prompt)

def reminder_generator(sender):
    sentences = ["_Вертится_ __что-то__ на **языке**...", "**Эх**х....", "~Поругаемся~ может?", "Ну *что*?"]
    return sentences[random.randint(0, len(sentences)-1)]

#def voice_generator(sender, sentence):
#    voice_id = get_random_voice(voices)
#    return generate_audio(sentence, voice_id['id'])

def silero_voice_generator(sender, sentence):
    voice_id = get_random_voice(silero_voices)
    logger.info(f"Generating voice with {voice_id}")
    try:
        return tts.generate_voice(text=sentence, speaker=voice_id)
    except Exception as e:
        logger.error(f"Voice generation failed for chat {sender.chat_id}: {e}")
        return None

def talk_generator(sender):
    chat_id = sender.chat_id
    conversations = []
    if chat_id in chats_conversations:
        conversations = chats_conversations[chat_id]
    return colocutor.get_answer(conversations)

def news_post_generator(sender):
    chat_id = sender.chat_id
    conversations = []
    if chat_id in chats_conversations:
        conversations = chats_conversations[chat_id]
    return news_post_creator.get_answer(conversations)

# Dictionary to store PeriodicMessageSender instances
chat_senders = {}
chats_conversations = {}
# Словарь для хранения промптов для каждого чата
chat_prompts = {}
# Словарь для хранения активного режима каждого чата
chat_active_modes = {}

def start_stop(command, senders, chat_id):
    try:
        for key, instance in senders.items():
            if key == command:
                if not instance.active:
                    instance.start()
                    logger.info(f"Started {key} messages for chat {chat_id}")
            elif instance.active:
                instance.stop()
                logger.info(f"Stopped {key} messages for chat {chat_id}")
    except ApiTelegramException as e:
        logger.error(f"Telegram API error in start_command for chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in start_command for chat {chat_id}: {e}")

@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id

    user_name = message.from_user.username if message.from_user.username else 'Unknown'
    chat_name = message.chat.username if message.chat.username else message.chat.title if message.chat.title else 'Unknown'

    logger.info(f"Bot started for chat {chat_id}:{chat_name}. User: {user_name}.")
    #initialize senders if not yest initialized
    if chat_id not in chat_senders:
            chat_senders[chat_id] = {
                'swear': PeriodicMessageSender(chat_id, bot, swear_generator, silero_voice_generator, SWEAR_PERIOD),
                'pause': PeriodicMessageSender(chat_id, bot, reminder_generator, None, REMINDER_PERIOD),
                'talk': PeriodicMessageSender(chat_id, bot, talk_generator, None, TALK_PERIOD),
                'news': PeriodicMessageSender(chat_id, bot, news_post_generator, None, NEWS_PERIOD)
            }
    #start/stop sender jobs
    chat_active_modes[chat_id] = "swear"
    if not chat_id in chat_prompts:
        msg = reply_tracked_message(message, "Укажите, кого вы хотите поругать.")
        bot.register_next_step_handler(msg, process_person_step)
    start_stop('swear', chat_senders[chat_id], chat_id)

@bot.message_handler(commands=['stop', 'swear', 'pause', 'talk', 'news'])
def command(message):
    command = message.text[1:]
    chat_id = message.chat.id
    chat_active_modes[chat_id] = command  # Устанавливаем активный режим
    if command == 'swear':
        if not chat_id in chat_prompts:
            msg = reply_tracked_message(message, "Укажите, кого вы хотите поругать.")
            bot.register_next_step_handler(msg, process_person_step)
    if chat_id in chat_senders:
        start_stop(command, chat_senders[chat_id], chat_id)
    else:
        logger.info(f"Messaging is not scheduled for chat {chat_id}. Command: {command}")

def process_person_step(message):
    chat_id = message.chat.id
    person = message.text.strip()

    # Сохраняем промпт для данного чатаs
    chat_prompts[chat_id] = f"Обзови {person}."

    reply_tracked_message(message, f"Хорошо, теперь буду оскорблять {person}.")


@bot.message_handler(commands=['person'])
def set_person_command(message):
    chat_id = message.chat.id

    # Проверяем, активен ли режим 'swear' для данного чата
    if chat_active_modes.get(chat_id) == 'swear':
        # Ожидаем, что после команды /person пользователь отправит имя или описание
        msg = reply_tracked_message(message, "Укажите, кого вы хотите поругать.")
        bot.register_next_step_handler(msg, process_person_step)
    else:
        reply_tracked_message(message, "Команда /person доступна только в режиме 'swear'. Сначала активируйте его командой /swear.")

@bot.message_handler(commands=['cleanup', 'clean'])
def cleanup_command(message):
    chat_id = message.chat.id
    cleared, failed = cleanup_tracked_bot_messages(chat_id)
    status_text = f"Cleanup complete. Cleared {cleared} tracked bot message(s)."
    if failed:
        status_text += f" Failed to delete {failed} tracked message(s)."
    status_message = send_tracked_message(chat_id, status_text)
    delete_tracked_message_later(chat_id, status_message.message_id, CLEANUP_STATUS_TTL_SECONDS)

def add_conversation(conversations, conversation):
    conversations.append(conversation)
    if len(conversations) > STACK_SIZE:
        conversations.pop(0)
    logger.info(conversations)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id == bot.get_me().id:
        return
    # Check if the message is sent by the bot itself
    chat_id = message.chat.id
    if chat_id in chats_conversations:
        add_conversation(chats_conversations[chat_id], message.text)
        logger.info(f'Added message to conversation for chat {chat_id}: {chats_conversations[chat_id]}')
    else:
        chats_conversations[chat_id] = [message.text]
        logger.info(f'New conversation for chat {chat_id}: {chats_conversations[chat_id]}')

def schedule_checker():
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in schedule checker: {e}")
            time.sleep(5)  # Wait a bit longer before retrying if there's an error

def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except ApiTelegramException as e:
            logger.error(f"Telegram API error: {e}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error in bot polling: {e}")
            time.sleep(5)

def test_escape():
    test_cases = [
    "Hello *world*",
    "This **is** bold",
    "This *is* also bold",
    "Unmatched *asterisk",
    "Escaped \\*asterisk",
    "Multiple **underscores**",
    "Mixed *formatting*",
    "Too many ***asterisks***",
    "Special chars: [brackets] (parentheses)",
    "Numbers and +plus -minus =equals",
    "Punctuation! With. Escaping?",
    "world\\!"
    ]
    escaped = []
# sourcery skip: no-loop-in-tests
    for case in test_cases:
        logger.info(f"Original: {case}")
        escaped_text = escape_markdown_v2(case)
        escaped.append(escaped_text)
        logger.info(f"Escaped:  {escaped_text}")
        logger.info()

if __name__ == "__main__":
    # Start the schedule checker in a separate thread

    checker_thread = threading.Thread(target=schedule_checker)
    checker_thread.start()

    # Start the bot
    run_bot()
