import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from config import TELEGRAM_BOT_TOKEN
from sber_swearing_gen import SberSwearingGenerator
from voice_gen import get_all_voices, generate_audio
import schedule
import time
import threading
import random
from swearing_gen import SwearingGenerator

# Initialize the bot with your token
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Store user data
user_data = {}
voices = []


swearing_generator = SwearingGenerator()
bsend = False


def get_random_voice(voices):
    return voices[random.randint(0, len(voices)-1)]

#
# Function to send a message
def send_message(user_id):
    if user_data[user_id]['bsend']:
        sentence = swearing_generator.get_answer("Пожалуйста, придумай для меня ровно одно самое страшное шутливое ругательство для лица женского гендера. Не используй ругательства, которые намекают на глупость или слабоумие. Ругательство не должно быть длинее трёх слов.")
        
        try:
            bot.send_message(user_id, sentence)
            voice_id = get_random_voice(voices)
            audio = generate_audio(sentence, voice_id['id'])
            bot.send_voice(user_id, audio)
            print(f"Sent message: {sentence} to user {user_id} with {voice_id}")
        except Exception as e:
            print(f"Failed to send message to user {user_id}: {e}")

# Schedule the message sending for a specific user
def start_sending_messages(user_id):
    def job():
        send_message(user_id)
    schedule.every(1).minute.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Handle /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    #global bsend
    user_data[message.chat.id] = {'voices': voices, 'selected_voice': None, 'bsend': True}
    threading.Thread(target=start_sending_messages, args=(message.chat.id,)).start()
    #markup = ReplyKeyboardMarkup(row_width=2)
    #for voice in voices:
    #    markup.add(KeyboardButton(voice['name']))
    #user_id = message.chat.id
    #if user_id in user_data and user_data[user_id]['selected_voice'] is None:
    #    bot.send_message(message.chat.id, "Привет! Я бот для создания озвучки! Выбери голос, который будет использоваться при создании озвучки.", reply_markup=markup)

# Handle /stop command
@bot.message_handler(commands=['stop'])
def send_welcome(message):
    user_data[message.chat.id]['bsend'] = False

# Handle text messages for voice selection and text input
#@bot.message_handler(func=lambda message: True)
#def handle_message(message):
#    user_id = message.chat.id
#    if user_id in user_data and user_data[user_id]['selected_voice'] is None:
#        selected_voice = next((voice for voice in user_data[user_id]['voices'] if voice['name'] == message.text), None)
#        if selected_voice:
#            user_data[user_id]['selected_voice'] = selected_voice
#            bot.send_message(user_id, f"Вы выбрали голос: {selected_voice['name']}.")
#            # Start sending messages after the voice is selected
#        else:
#            bot.send_message(user_id, "Пожалуйста, выберите голос с клавиатуры.")
#    #else:
#    #    if user_id in user_data and user_data[user_id]['selected_voice']:
#    #        voice_id = user_data[user_id]['selected_voice']['id']
#    #        audio = generate_audio(message.text, voice_id)
#    #        bot.send_voice(user_id, audio)

# Start polling for new messages
if __name__ == "__main__":
    voices = get_all_voices()
    bot.polling(none_stop=True)
