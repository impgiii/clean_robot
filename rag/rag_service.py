from rag.vector_store import VectorStoreService
from model.factory import chat_model
from utils.config_handle import rag_conf
from utils.prompt_handle import load_prompt


class RagService:
    def __init__(self):
        self.vector_store_service = VectorStoreService()
        self.retriever = self.vector_store_service.get_retriever()
        self.chat_model = chat_model

        self.prompt_template = load_prompt(rag_conf['rag_prompt_path'])

    def answer(self,question):
        question = question.strip()
        if not question:
            return "请输入你的问题。"

        documents = self.retriever.invoke(question)

        if not documents:
            return "暂时没有检索到参考资料，请补充型号或问题描述。"

        context_parts = []

        for index,doc in enumerate(documents,start=1):
            source = doc.metadata.get('source','未知')

            part = (
                f"[资料：{index}]\n"
                f"来源：{source}\n"
                f"正文：{doc.page_content}"
            )
            context_parts.append(part)

        context = "\n\n".join(context_parts)

        prompt = self.prompt_template.format(
            context=context,
            question=question,
        )
        response = self.chat_model.invoke(prompt)

        return response.content        

