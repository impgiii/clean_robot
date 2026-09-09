import os
import hashlib

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


def get_file_md5(file_path):
    md5_obj = hashlib.md5()

    with open(file_path, "rb") as f:
        while 1:
            chunk = f.read(4096)

            if not chunk:
                break

            md5_obj.update(chunk)

    return md5_obj.hexdigest()


def listdir_with_allowed_type(path, allowed_types):

    if not os.path.isdir(path):
        raise FileNotFoundError(f"路径 {path} 不存在")

    suffixes = tuple("." + file_type.lstrip(".").lower() for file_type in allowed_types)


    files = []

    for name in sorted(os.listdir(path)):
        file_path = os.path.join(path, name)

        if not os.path.isfile(file_path):
            continue

        if name.lower().endswith(suffixes):
            files.append(file_path)
    return tuple(files)


def pdf_loader(file_path,password = None) -> list[Document]:
    loader = PyPDFLoader(file_path, password = password,mode = "page")
    return loader.load()

def txt_loader(file_path,encoding = "utf-8") -> list[Document]:
    loader = TextLoader(file_path, encoding = encoding)
    return loader.load()
