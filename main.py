from rag.vector_store import VectorStoreService


if __name__ == "__main__":
    service = VectorStoreService()

    # 准备知识库
    service.load_doc()

    # 检索相关资料
    retriever = service.get_retriever()
    documents = retriever.invoke("扫地机器人不出水怎么办？")

    print(f"\n检索到 {len(documents)} 个片段")

    for index, doc in enumerate(documents, start=1):
        print(f"\n--- 资料 {index} ---")
        print(doc.page_content)