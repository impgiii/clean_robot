import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from utils.config_handle import rag_conf

load_dotenv()

class BaseModelFactory(ABC):
    @abstractmethod

    def generator(self):
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self)->ChatOpenAI:
        return ChatOpenAI(
            model = rag_conf['chat_model'],
            api_key = os.getenv("OPENAI_API_KEY"),
            base_url = os.getenv("OPENAI_BASE_URL"),
        )

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self)->OpenAIEmbeddings:
        return OpenAIEmbeddings(
            model = rag_conf['embedding_model'],
            api_key = os.getenv("OPENAI_API_KEY"),
            base_url = os.getenv("OPENAI_BASE_URL"),
        )

chat_model = ChatModelFactory().generator()
embeddings = EmbeddingModelFactory().generator()
