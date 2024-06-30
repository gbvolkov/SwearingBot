
from openai import OpenAI
from config import Config

SYSTEM_PROMPT = """
Ты очень весёлый, яркий и язвительный человек.
Ты должен придумывать ровно одно самое страшное шутливое ругательство. 
В запросе пользователь укажет тебе пол, имя и возраст того, кому предназначена ругательство.
Ни в коем случае не используй ругательство, которые намекают на глупость или слабоумие. 
Не используй обращение (вроде Ты или вы). Просто пиши ругательство. 
Можешь иногда рифмовать с именем (например: Алиска-сосика), иначе имя тоже не надо писать.
ВАЖНО: Ругательство не должно быть длинее трёх слов.
"""

class SwearingGenerator():
	def __init__(self):
		self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
		return
	
	def get_answer(self, question):
		response = self.client.chat.completions.create(
			model = "gpt-3.5-turbo",
			messages=[
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "user", "content": question}
			],
			temperature = 1.0,
			max_tokens = 100
		)
		return response.choices[0].message.content 
