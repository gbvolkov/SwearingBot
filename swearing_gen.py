
from openai import OpenAI
from config import OPENAI_API_KEY

class SwearingGenerator():
	def __init__(self):
		self.client = OpenAI(api_key=OPENAI_API_KEY)
		return
	
	def get_answer(self, question):
		response = self.client.chat.completions.create(
			model = "gpt-3.5-turbo",
			messages=[
				{"role": "system", "content": "Ты очень весёлый, яркий и язвительный человек."},
				{"role": "user", "content": question}
			],
			temperature = 1.0,
			max_tokens = 100
		)
		return response.choices[0].message.content 
