from dotenv import load_dotenv
import os

from pathlib import Path

documents_path = Path.home() / ".env"

load_dotenv(os.path.join(documents_path, 'gv.env'))

class Config:
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_SWEAR_BOT_TOKEN')
    GIGA_CHAT_USER_ID=os.environ.get('GIGA_CHAT_USER_ID')
    GIGA_CHAT_SECRET = os.environ.get('GIGA_CHAT_SECRET')
    GIGA_CHAT_AUTH = os.environ.get('GIGA_CHAT_AUTH')
    NEWSAPI_API_KEY = os.environ.get('NEWSAPI_API_KEY')
    SWEAR_PROMPT = os.environ.get('SWEAR_PROMPT')
    SILERO_LOCAL_PATH = os.environ.get('SILERO_LOCAL_PATH')
