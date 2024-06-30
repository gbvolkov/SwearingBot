from dotenv import load_dotenv
import os

from pathlib import Path

documents_path = Path.home() / ".env"

load_dotenv(os.path.join(documents_path, 'gv.env'))

class Config:
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
    TELEGRAM_BOT_TOKEN = "7055842831:AAFaeeZt_2F1ccZ6LWq26IPHhaRAnTSG7aQ" #bot
