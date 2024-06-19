from elevenlabs import save
from elevenlabs.client import ElevenLabs
from config import ELEVENLABS_API_KEY

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

def get_all_voices():
	voices = client.voices.get_all()
	return [{'name': voice.name, 'id': voice.voice_id} for voice in voices.voices]

def generate_audio(text: str, voice: str):
	audio = client.generate(
		text=text,
	    voice=voice,
	    model="eleven_multilingual_v2"
		)
	audio_bytes = b''.join(audio)
	return audio_bytes
