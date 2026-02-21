from elevenlabs.client import ElevenLabs
from config import Config

client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)

def get_all_voices():
	voices = client.voices.get_all()
	return [{'name': voice.name, 'id': voice.voice_id} for voice in voices.voices]

def generate_audio(text: str, voice: str):
	audio = client.generate(
		text=text,
	    voice=voice,
	    model="eleven_multilingual_v2"
		)
	return b''.join(audio)
