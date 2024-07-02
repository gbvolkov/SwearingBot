
from openai import OpenAI
from config import Config

SYSTEM_PROMPT = """
You are a thoughtful and polite conversationalist. 
Keep the chat conversation going based on the last few messages. 
The most recent post determines the topic. 
If previous messages don't fit the topic, consider them marginally. 
Your reply should be short, no more than 200 characters. 
Try to add references to philosophers and works of fiction. 
Answer in Russian.
"""

class Colocutor():
	def __init__(self):
		self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
		return
	
	def get_answer(self, questions):
		messages=[
		    {"role": "system", "content": SYSTEM_PROMPT},
		]
		messages.extend(
			{"role": "user", "content": question} for question in questions
		)
		response = self.client.chat.completions.create(
		    model = "gpt-3.5-turbo",
		    #model = "gpt-4o",
		    messages=messages,
		    temperature = 0.4,
		    max_tokens = 200
		)
		return response.choices[0].message.content 
