import telebot
from telebot.apihelper import ApiTelegramException
import schedule
import time
import random
import threading
import logging
from config import Config
from converstion_complete import Colocutor
from swearing_gen import SwearingGenerator
from news_post_gen import NewsPostGenerator
from news_post_gen_v2 import NewsPostGenerator_v2
from voice_gen import generate_audio, get_all_voices
from tts_gen import TTSGenerator, translit2rus
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)
voices = get_all_voices()
print(voices)
sample_rate = 48000
tts = TTSGenerator(sample_rate)
silero_voices = tts.get_all_voices()
print(silero_voices)


def get_random_voice(voices):
    return voices[random.randint(0, len(voices)-1)]

swearing_generator = SwearingGenerator()
colocutor = Colocutor()
news_post_creator = NewsPostGenerator_v2()


STACK_SIZE = 16

SWEAR_PROMPT = Config.SWEAR_PROMPT # "Обзови Алису. Пол: Женский. Возраст: 20 лет."
SWEAR_PERIOD = (90,180)
REMINDER_PERIOD = (90*60, 180*60)
#REMINDER_PERIOD = (2, 4)
TALK_PERIOD = (15*60,240*60)
NEWS_PERIOD = (180*60,360*60)
#NEWS_PERIOD = (2,10)


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
            self.bot.send_message(self.chat_id, escape_markdown_v2(message), parse_mode='MarkdownV2')
            if self.voice_generator and random.randint(0, 9) >= 7:
                voice = self.voice_generator(self, message)
                self.bot.send_voice(self.chat_id, voice)
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
    return swearing_generator.get_answer(SWEAR_PROMPT)

def reminder_generator(sender):
    sentences = ["_Вертится_ __что-то__ на **языке**...", "**Эх**х....", "~Поругаемся~ может?", "Ну *что*?"]
    return sentences[random.randint(0, len(sentences)-1)]

def voice_generator(sender, sentence):
    voice_id = get_random_voice(voices)
    return generate_audio(sentence, voice_id['id'])

def silero_voice_generator(sender, sentence):
    voice_id = get_random_voice(silero_voices)
    return tts.generate_voice(text = translit2rus(sentence), speaker = voice_id)

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

    #initialize senders if not yest initialized
    if chat_id not in chat_senders:
            chat_senders[chat_id] = {
                'swear': PeriodicMessageSender(chat_id, bot, swear_generator, silero_voice_generator, SWEAR_PERIOD),
                'pause': PeriodicMessageSender(chat_id, bot, reminder_generator, None, REMINDER_PERIOD),
                'talk': PeriodicMessageSender(chat_id, bot, talk_generator, None, TALK_PERIOD),
                'news': PeriodicMessageSender(chat_id, bot, news_post_generator, None, NEWS_PERIOD)
            }
    #start/stop sender jobs
    start_stop('swear', chat_senders[chat_id], chat_id)

@bot.message_handler(commands=['stop', 'swear', 'pause', 'talk', 'news'])
def command(message):
    command = message.text[1:]
    chat_id = message.chat.id
    if chat_id in chat_senders:
        start_stop(command, chat_senders[chat_id], chat_id)
    else:
        logger.info(f"Messaging is not scheduled for chat {chat_id}. Command: {command}")

def add_conversation(conversations, conversation):
    conversations.append(conversation)
    if len(conversations) > STACK_SIZE:
        conversations.pop(0)
    print(conversations)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id == bot.get_me().id:
        return
    # Check if the message is sent by the bot itself
    chat_id = message.chat.id
    if chat_id in chats_conversations:
        add_conversation(chats_conversations[chat_id], message.text)
    else:
        chats_conversations[chat_id] = [message.text]
        print(chats_conversations[chat_id])

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
        print(f"Original: {case}")
        escaped_text = escape_markdown_v2(case)
        escaped.append(escaped_text)
        print(f"Escaped:  {escaped_text}")
        print()

if __name__ == "__main__":
    # Start the schedule checker in a separate thread

    checker_thread = threading.Thread(target=schedule_checker)
    checker_thread.start()

    # Start the bot
    run_bot()
