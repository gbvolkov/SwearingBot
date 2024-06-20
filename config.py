#ELEVENLABS_API_KEY = "sk_94020e4e95c4d8330b6ba0f68a846e8b5d796a97a3a311bc"
#OPENAI_API_KEY = "sk-proj-WXbirpruqtC1UFsOH0IST3BlbkFJwoMN2yanytWGHU2QY1Io"
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.expanduser("~/Documents"), 'gv.env'))
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
TELEGRAM_BOT_TOKEN = "7055842831:AAFaeeZt_2F1ccZ6LWq26IPHhaRAnTSG7aQ"
