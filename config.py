from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.expanduser("~/Documents"), 'gv.env'))
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
TELEGRAM_BOT_TOKEN = "7055842831:AAFaeeZt_2F1ccZ6LWq26IPHhaRAnTSG7aQ" #bot
