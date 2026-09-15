from langchain_chroma import Chroma
from model.factory import embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abs_path
from utils.config_handle import chroma_conf
from utils.file_handle import listdir_with_allowed_type,get_file_md5,txt_loader,pdf_loader


class VectorStoreService:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf['chunk_size'],
            chunk_overlap=chroma_conf['chunk_overlap'],
            separators=chroma_conf['separator'],
            length_function=len,
        )


        db_path = get_abs_path(chroma_conf['persist_directory'])

        self.vector_store = Chroma(
            collection_name=chroma_conf["collection"],
            embedding_function=embeddings,
            persist_directory=str(db_path),
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(
            search_kwargs={"k":chroma_conf['k']}
        )

    def load_doc(self):
        data_path=get_abs_path(chroma_conf['data_path'])
        md5_path=get_abs_path(chroma_conf['md5_hex_store'])

        processed_md5 = set()

        if md5_path.exists():
            with md5_path.open("r",encoding="utf-8") as f:
                processed_md5 = {
                    line.strip()
                    for line in f
                    if line.strip()
                }

        files = listdir_with_allowed_type(data_path,chroma_conf['allow_types'])

        for file_path in files:
            file_md5 = get_file_md5(file_path)

            if file_md5 in processed_md5:
                print(f"该文档已入库：{file_path}")
                continue

            print(f"准备加载文件：{file_path}")

            if file_path.lower().endswith(".pdf"):
                documents = pdf_loader(file_path)
            elif file_path.lower().endswith(".txt"):
                documents = txt_loader(file_path)
            else:
                continue

            print(f"文件 {file_path} 加载 {len(documents)} 个文档")

            chunks = self.splitter.split_documents(documents)

            chunks = [
                chunk for chunk in chunks
                if chunk.page_content.strip()
            ]

            if not chunks:
                print(f"没有可入库的正文，跳过：{file_path}")
                continue

            print(f"切分完成，共 {len(chunks)} 个片段")

            self.vector_store.add_documents(chunks)

            with md5_path.open("a",encoding="utf-8") as f:
                f.write(f"{file_md5}\n")
            processed_md5.add(file_md5)
            print(f"文件 {file_path} 入库完成")
