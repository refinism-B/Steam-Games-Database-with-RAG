import json
import time
import uuid
from pathlib import Path

import tiktoken
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
# from langchain_ollama import OllamaEmbeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from src.config.constant import (PG_COLLECTION, PROJECT_ROOT, TEI_LOCAL)
# EMBEDDING_MODEL, OLLAMA_LOCAL, OLLAMA_URL

from src.database import postgreSQL_conn as pgc

"""
定義類別及函式
"""


class LmStudioEmbeddings(Embeddings):
    def __init__(self, model_name, url):
        self.model_name = model_name
        self.url = url
        self.client = OpenAI(base_url=url, api_key="lm-studio")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def embed_query(self, text: str):
        text = text.replace("\n", " ")
        response = self.client.embeddings.create(
            input=text,
            model=self.model_name
        )
        return response.data[0].embedding

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def embed_documents(self, texts: list[str]):
        if not texts:
            return []
        texts = [t.replace("\n", " ") for t in texts]
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        return [data.embedding for data in response.data]


def tiktoken_len(text):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    return len(tokens)


def connect_to_vector_db(embeddings, connection, collection_name=PG_COLLECTION):
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=connection,
        use_jsonb=True,
    )


def parent_document_slicer(doc_list, parent_splitter, child_splitter):
    """
    執行 Parent-Document 切割
    """
    all_docs_to_vectorize = []

    parent_docs = parent_splitter.split_documents(doc_list)

    for pi, doc in enumerate(parent_docs):
        steam_appid = doc.metadata.get("steam_appid")
        if not steam_appid:
            base_id = str(uuid.uuid4())
        else:
            base_id = str(steam_appid)

        current_parent_doc_id = base_id + f"_p0{str(pi)}"

        doc.metadata["doc_id"] = current_parent_doc_id
        doc.metadata["parent_id"] = doc.metadata["doc_id"]
        doc.metadata["is_parent"] = True

        all_docs_to_vectorize.append(doc)

        split_docs = child_splitter.split_documents([doc])

        for i, sdoc in enumerate(split_docs):
            sdoc.metadata["parent_id"] = doc.metadata["doc_id"]
            sdoc.metadata["doc_id"] = current_parent_doc_id + f"_c0{str(i)}"
            sdoc.metadata["is_parent"] = False
            all_docs_to_vectorize.append(sdoc)

    print(f"原始父文件數：{len(parent_docs)}")
    print(f"處理後總文件數 (父+子)：{len(all_docs_to_vectorize)}")

    return all_docs_to_vectorize


"""
主流程開始
"""


def main():
    print("正在連線 Embedding 模型...")
    # embeddings = OllamaEmbeddings(
    #     model=EMBEDDING_MODEL,
    #     base_url=OLLAMA_LOCAL,
    #     client_kwargs={"timeout": 300}
    # )

    embeddings = HuggingFaceEndpointEmbeddings(
        model=TEI_LOCAL
    )

    pg_url = pgc.connect_to_pgSQL()
    vector_store = connect_to_vector_db(
        embeddings=embeddings, connection=pg_url)

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=250,
        length_function=tiktoken_len
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=70,
        length_function=tiktoken_len,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""]
    )

    input_num = 1

    while True:
        try:
            current_folder = Path(PROJECT_ROOT) / "data/processed/document"
            # 如果你的環境資料夾結構不同，請在此調整
            if not current_folder.exists():
                print(f"路徑不存在: {current_folder}，請確認路徑配置")
                break

            input_file = f"document_{input_num}.json"
            input_path = current_folder / input_file

            if not input_path.exists():
                print("所有檔案皆以處理完畢")
                break

            print(f"正在讀取: {input_file} ...")
            with open(input_path, "r", encoding="utf-8") as f:
                data_list = json.load(f)

            if not data_list:
                print(f"警告: {input_file} 是空的，跳過。")
                input_num += 1
                continue

            doc_list = [Document(page_content=d.get("context", ""), metadata=d.get("metadata", {}))
                        for d in data_list]

            # 1. 切割與 ID 生成
            total_docs = parent_document_slicer(
                doc_list, parent_splitter, child_splitter)
            ids = [doc.metadata["doc_id"] for doc in total_docs]

            # 2. 輸入PostgreSQL資料庫
            batch_size = 32
            for i in tqdm(range(0, len(total_docs), batch_size), desc=f"寫入進度 ({input_file})"):
                batch_docs = total_docs[i: i + batch_size]
                batch_ids = ids[i: i + batch_size]

                try:
                    # 後續執行：直接使用 add_documents 效率更高
                    vector_store.add_documents(
                        documents=batch_docs,
                        ids=batch_ids
                    )

                except Exception as e:
                    # 這裡捕捉到的錯誤會顯示出來，不會讓程式崩潰
                    print(f"\n寫入批次 {i} 時發生錯誤: {e}")

            print(f"成功處理: {input_file}")
            input_num += 1
            time.sleep(1)

        except Exception as e:
            print(f"處理檔案 {input_num} 時發生未預期的錯誤: {e}")
            break


if __name__ == "__main__":
    main()
