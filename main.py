import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import Config
from sber_swearing_gen import SberSwearingGenerator
from voice_gen import get_all_voices, generate_audio
import schedule
import time
import threading
import random
from swearing_gen import SwearingGenerator
import requests

# Initialize the bot with your token
bot = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)

# Store user data
user_data = {}
voices = []


swearing_generator = SwearingGenerator()
bsend = False


def get_random_voice(voices):
    return voices[random.randint(0, len(voices)-1)]

def send_reminder(user_id):
    if not user_data[user_id]['bsend']:
        sentences = ["Вертится что-то на языке...", "Эхх....", "Поругаемся?", "Ну что?"]
        sentence = sentences[random.randint(0, len(sentences)-1)]
        try:
            bot.send_message(user_id, sentence)
            print(f"Sent reminder: {sentence} to user {user_id}")
        except Exception as e:
            print(f"Failed to send reminder to user {user_id}: {e}")

#
# Function to send a message
def send_swearing(user_id):
    if user_data[user_id]['bsend']:
        sentence = swearing_generator.get_answer("Обзови Веронику. Пол: Женский. Возраст: 33 года.")
        
        try:
            bot.send_message(user_id, sentence)
            if random.randint(0, 9) >= 9:
                voice_id = get_random_voice(voices)
                audio = generate_audio(sentence, voice_id['id'])
                bot.send_voice(user_id, audio)
                print(f"Sweared: {sentence} to user {user_id} with {voice_id}")
            else:
                print(f"Sweared: {sentence} to user {user_id} with no voice")
        except Exception as e:
            print(f"Failed to swear to user {user_id}: {e}")

# Schedule the message sending for a specific user
def start_sending_swearings(user_id):
    def swear():
        send_swearing(user_id)
    schedule.every(random.randint(45, 75)).seconds.do(swear)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Schedule the message sending for a specific user
def start_sending_reminders(user_id):
    def remind():
        send_reminder(user_id)
    schedule.every(random.randint(90, 120)).minutes.do(remind)
    while True:
        schedule.run_pending()
        time.sleep(1)


# Handle /start command
@bot.message_handler(commands=['start'])
def start_swearing(message):
    #global bsend
    if message.chat.id in user_data:
        user_thread = user_data[message.chat.id]['Thread']
        if user_thread is not None:
            #user_thread.join()
            del user_thread
    user_data[message.chat.id] = {'voices': voices, 
                                  'selected_voice': None, 
                                  'bsend': True, 
                                  'Thread': threading.Thread(target=start_sending_swearings, args=(message.chat.id,))}
    user_data[message.chat.id]['Thread'].start()
    bot.send_message(message.chat.id, "Start swearing.")
    print("Swearing started")
    #markup = ReplyKeyboardMarkup(row_width=2)
    #for voice in voices:
    #    markup.add(KeyboardButton(voice['name']))
    #user_id = message.chat.id
    #if user_id in user_data and user_data[user_id]['selected_voice'] is None:
    #    bot.send_message(message.chat.id, "Привет! Я бот для создания озвучки! Выбери голос, который будет использоваться при создании озвучки.", reply_markup=markup)

# Handle /stop command
@bot.message_handler(commands=['stop'])
def stop_swearing(message):
    if message.chat.id in user_data:
        #print("Inside 1")
        user_thread = user_data[message.chat.id]['Thread']
        if user_thread is not None:
            #print("Joining thread")
            #user_thread.join()
            #print("removing thread")
            del user_thread
        user_data[message.chat.id]['bsend'] = False
        user_data[message.chat.id]['Thread'] = threading.Thread(target=start_sending_reminders, args=(message.chat.id,))
        #print("starting thread")
        user_data[message.chat.id]['Thread'].start()
    # Create a ReplyKeyboardRemove object
    markup = ReplyKeyboardRemove()
    # Send a message with the ReplyKeyboardRemove object to clear the keyboard
    bot.send_message(message.chat.id, "Swearing stopped.", reply_markup=markup)
    print("Swearing stopped")

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
    while True:
        try:
            voices = get_all_voices()
            bot.polling(none_stop=True, timeout=60)
        except requests.exceptions.ReadTimeout:
            print("ReadTimeout occurred, retrying...")
            time.sleep(5)           
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(5)