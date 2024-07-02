import telebot
from telebot.apihelper import ApiTelegramException
import schedule
import time
import random
import threading
import logging
from config import Config
from swearing_gen import SwearingGenerator
from voice_gen import generate_audio, get_all_voices

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)
voices = get_all_voices()
def get_random_voice(voices):
    return voices[random.randint(0, len(voices)-1)]

swearing_generator = SwearingGenerator()

SWEAR_PROMPT = "Обзови Веронику. Пол: Женский. Возраст: 33 года."
SWEAR_PERIOD = (6,18)
REMINDER_PERIOD = (20, 30)

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
            message = self.message_generator()
            self.bot.send_message(self.chat_id, message)
            if self.voice_generator and random.randint(0, 9) >= 9:
                voice = self.voice_generator(message)
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
def swear_generator():
    return swearing_generator.get_answer(SWEAR_PROMPT)

def reminder_generator():
    sentences = ["Вертится что-то на языке...", "Эхх....", "Поругаемся?", "Ну что?"]
    return sentences[random.randint(0, len(sentences)-1)]

def voice_generator(sentence):
    voice_id = get_random_voice(voices)
    return generate_audio(sentence, voice_id['id'])


# Dictionary to store PeriodicMessageSender instances
chat_senders = {}

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
                'swear': PeriodicMessageSender(chat_id, bot, swear_generator, voice_generator, SWEAR_PERIOD),
                'pause': PeriodicMessageSender(chat_id, bot, reminder_generator, None, REMINDER_PERIOD)
            }
    #start/stop sender jobs
    start_stop('swear', chat_senders[chat_id], chat_id)

@bot.message_handler(commands=['stop', 'swear', 'pause'])
def command(message):
    command = message.text[1:]
    chat_id = message.chat.id
    if chat_id in chat_senders:
        start_stop(command, chat_senders[chat_id], chat_id)
    else:
        logger.info(f"Messaging is not scheduled for chat {chat_id}. Command: {command}")

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

if __name__ == "__main__":
    # Start the schedule checker in a separate thread
    checker_thread = threading.Thread(target=schedule_checker)
    checker_thread.start()

    # Start the bot
    run_bot()
