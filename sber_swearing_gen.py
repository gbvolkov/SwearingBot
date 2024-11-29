import requests
import json
import time
import uuid
from config import Config

import logging  
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

headers_sber = {
  'Content-Type': 'application/x-www-form-urlencoded',
  'Accept': 'application/json',
  'RqUID': 'идентификатор_запроса',
  'Authorization': 'Basic <авторизацонные_данные>'
}
SCOPE_SBER = "GIGACHAT_API_PERS"
GIGA_CHAT_USER_ID=Config.GIGA_CHAT_USER_ID
GIGA_CHAT_SECRET = Config.GIGA_CHAT_SECRET
GIGA_CHAT_AUTH = Config.GIGA_CHAT_AUTH
SYSTEM_PROMPT = """
Ты очень весёлый, яркий и язвительный человек.
Ты должен придумывать ровно одно самое страшное шутливое ругательство. 
В запросе пользователь укажет тебе пол, имя и возраст того, кому предназначена ругательство.
Ни в коем случае не используй ругательство, которые намекают на глупость или слабоумие. 
Не используй обращение (вроде Ты или вы). Просто пиши ругательство. Можешь иногда рифмовать с именем (например: Алиска-сосика).
ВАЖНО: Ругательство не должно быть длинее трёх слов.
"""

promt_sber = {
    "model": "GigaChat",
    "messages": [
        {'role':'system', 'content':SYSTEM_PROMPT}
       , {'role': 'user', 'content':''}
    ],
    "temperature": 1,
    "top_p": 0.1,
    "n": 1,
    "stream": False,
    "max_tokens": 24,
    "repetition_penalty": 5
}


class SberSwearingGenerator():
	def __init__(self):
		return
	def get_auth_token(self):
		auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
		payload = f'scope={SCOPE_SBER}'
		rq_uid = uuid.uuid4()
		headers = {
			'Content-Type': 'application/x-www-form-urlencoded',
			'Accept': 'application/json',
			'RqUID': str(rq_uid),
			'Authorization': f'Basic {GIGA_CHAT_AUTH}',
		}
		response = requests.request("POST", auth_url, headers=headers, data=payload, verify=True)
		return json.loads(response.text)['access_token']
	
	def get_answer(self, question):
		access_token = self.get_auth_token()
		completion_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
		promt_sber['messages'][len(promt_sber['messages'])-1]['content'] = question

		payload = json.dumps(promt_sber)
		headers = {
			'Content-Type': 'application/json',
			'Accept': 'application/json',
			'Authorization': f'Bearer {access_token}',
		}
		try:
			response = requests.request("POST", completion_url, headers=headers, data=payload, verify=True)
		except Exception:
			time.sleep(10)
			return ""
		if response.status_code != 200:
			time.sleep(10)
			logger.info(f"ERROR:{response.status_code} {response.reason}\n")
			return ""
		return json.loads(response.text)['choices'][0]['message']['content']

