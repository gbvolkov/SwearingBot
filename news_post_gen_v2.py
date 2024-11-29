from langchain_openai import ChatOpenAI
from config import Config
import requests
from langchain.prompts import PromptTemplate
from random import randint
from converstion_complete import Colocutor

NEWS_API_KEY = Config.NEWSAPI_API_KEY

import logging  
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Retrieve news
def get_news(topic, api_key, page_size=3):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={api_key}&language=en&sortBy=publishedAt&pageSize={page_size}"
    response = requests.get(url)
    return response.json()

def run_chain(template, input, llm):
    input_variables = list(input.keys())

    prompt = PromptTemplate(
        input_variables=input_variables,
        template=template,
    )
    chain = prompt | llm
    return chain.invoke(input).content

class NewsPostGenerator_v2():
    def __init__(self):
        self.llm = ChatOpenAI(api_key=Config.OPENAI_API_KEY, temperature=0.7, model="gpt-4o-mini")
        return

    def get_news_topic(self, conversation):
        # Generate news topic
        return run_chain(
            "Based on the following conversation, generate a relevant news topic to retrieve news from newsapi.org. It should not be more than two words:\n\n{conversation}\n\nTopic:", 
            {"conversation": conversation}, 
            self.llm)
    

    def generate_news_summary(self, articles):
        # Generate news summary
        return run_chain(
            "Summarize the following news articles in one sentence:\n\n{articles}\n\nSummary:", 
            {"articles": articles}, 
            self.llm)

    def generate_news_title(self, summary):
        # Generate post title
        return run_chain(
            "Generate a clear, explanatory title in Russian for this summary:\n\n{summary}\n\nTitle:", 
            {"summary": summary}, 
            self.llm)

    def generate_news_post(self, summary):
        # Generate post
        return run_chain(
            "Generate a clear post in Russian based on this summary (max 512 characters, do not split by articles, express in one sentence, add emojies and format with MarkdownV2 to highligh most important parts):\n\n{summary}\n\nPost:", 
            {"summary": summary}, 
            self.llm)

    def generate_news_metadata(self, summary, articles):
        # Generate metadata
        return run_chain(
            "Generate metadata for this post, including a short description and links to the original news articles:\n\nSummary: {summary}\n\nArticles: {articles}\n\nMetadata:", 
            {"summary": summary, "articles": articles}, 
            self.llm)

    def generate_post(self, topic):
        news = get_news(topic, NEWS_API_KEY)
        articles = "\n\n".join([f"Title: {article['title']}\nDescription: {article['description']}\nContent: {article['content']}\nLink: {article['url']}" for article in news['articles']])
        summary = self.generate_news_summary(news)
        title = self.generate_news_title(summary)
        post = self.generate_news_post(summary)
        metadata = "\n\n".join([f"[{article['title']}]({article['url']})" for article in news['articles']])
        return {
            "title": f"*{title}*",
            "meta_description": f"{metadata}",
            "post_content": post,
        }


    def get_answer(self, questions):
        if randint(1, 3) == 3:
            return Colocutor().get_answer(questions)
        topic = self.get_news_topic(questions)
        post = self.generate_post(topic)
        return f"{post['title']}\n\n{post['post_content']}\n\n{post['meta_description']}"

if __name__ == "__main__":
    generator = NewsPostGenerator_v2()
    answer = generator.get_answer(['Сральник отхожий!', 'Каторжница заскорузлая!', 'Братомучительница!', 'я все!', 'Ура! И как?', 'очень хорошо прошло! я рассчитываю либо на 2.0 либо 2.3', 'Уррряяаааааа!!!;)', 'Марадец!!!', 'там было два задания, которые я не сделала, но все остальное все сделала:)', 'Уря!:))))', 'И что теперь? Каникулы? Или ещё нет?', 'ну я работаю теперь', 'Это конец? Остальные теперь будут в сентябре?', 'Молодец!! Умница!', 'В смысле Бикини? Ты ж теперь в Митте?', 'это в системе не так написано'])
    logging.info(answer)