from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.expanduser("~/Documents"), 'gv.env'))
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')

