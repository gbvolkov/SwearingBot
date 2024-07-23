from langchain_openai import OpenAI
from config import Config
import requests
from langchain.prompts import PromptTemplate
from random import randint
from converstion_complete import Colocutor

NEWS_API_KEY = Config.NEWSAPI_API_KEY

# Retrieve news
def get_news(topic, api_key, page_size=3):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={api_key}&language=en&sortBy=publishedAt&pageSize={page_size}"
    response = requests.get(url)
    return response.json()

class NewsPostGenerator_v2():
    def __init__(self):
        self.llm = OpenAI(api_key=Config.OPENAI_API_KEY, temperature=0.7)
        return

    def get_news_topic(self, conversation):
        # Topic generation
        topic_prompt = PromptTemplate(
            input_variables=["conversation"],
            template="Based on the following conversation, generate a relevant news topic to retrieve news from newsapi.org. It should not be more than two words:\n\n{conversation}\n\nTopic:",
        )
        topic_chain = topic_prompt | self.llm #LLMChain(llm=llm, prompt=topic_prompt)
        return topic_chain.invoke(conversation)
    

    def generate_news_summary(self, articles):
        summary_prompt = PromptTemplate(
            input_variables=["articles"],
            template="Summarize the following news articles:\n\n{articles}\n\nSummary:",
        )
        summary_chain = summary_prompt | self.llm #LLMChain(llm=llm, prompt=summary_prompt)
        
        return summary_chain.invoke(articles)

    def generate_news_title(self, summary):
        title_prompt = PromptTemplate(
            input_variables=["summary"],
            template="Generate a clear, explanatory title in Russian for this summary:\n\n{summary}\n\nTitle:",
        )
        title_chain = title_prompt | self.llm #LLMChain(llm=llm, prompt=title_prompt)

        return title_chain.invoke(summary)

    def generate_news_post(self, summary):
        # Generate post
        post_prompt = PromptTemplate(
            input_variables=["summary"],
            template="Generate a clear post in Russian based on this summary (max 512 characters, add emojies and format with MarkdownV2 to highligh most important parts):\n\n{summary}\n\nPost:",
        )
        post_chain = post_prompt | self.llm #LLMChain(llm=llm, prompt=post_prompt)

        return post_chain.invoke(summary)[:512]

    def generate_news_metadata(self, summary, articles):
        # Generate metadata
        metadata_prompt = PromptTemplate(
            input_variables=["summary", "articles"],
            template="Generate metadata for this post, including a short description and links to the original news articles:\n\nSummary: {summary}\n\nArticles: {articles}\n\nMetadata:",
        )
        metadata_chain = metadata_prompt | self.llm #LLMChain(llm=llm, prompt=metadata_prompt)

        return metadata_chain.invoke(input={"summary": summary, "articles": articles})

    def generate_post(self, topic):
        news = get_news(topic, NEWS_API_KEY)
        articles = "\n\n".join([f"Title: {article['title']}\nDescription: {article['description']}\nContent: {article['content']}\nLink: {article['url']}" for article in news['articles']])
        summary = self.generate_news_summary(news)
        title = self.generate_news_title(summary)
        post = self.generate_news_post(summary)
        metadata = "\n\n".join([f"[{article['title']}]({article['url']})" for article in news['articles']])
        #metadata = self.generate_news_metadata(summary, articles)

        return {
            "title": f"*{title}*",
            "meta_description": f"{metadata}",
            "post_content": post,
        }


    def get_answer(self, questions):
        if randint(1, 3) == 3:
            return Colocutor().get_answer(questions)
        #print(f"conversation: {questions}")
        topic = self.get_news_topic(questions)
        #print(f"news topic: {topic}")
        post = self.generate_post(topic)
        
        return f"{post['title']}\n\n{post['post_content']}\n\n{post['meta_description']}"

if __name__ == "__main__":
    generator = NewsPostGenerator_v2()
    answer = generator.get_answer(['Да, хуже только Трамп, наверно.', 'Надо войну заканчивать. Война-это плозо', 'А ты читал Зайончковского?'])
    #print(answer)