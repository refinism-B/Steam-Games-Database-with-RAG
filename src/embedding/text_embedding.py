import json
import time

import tiktoken
from langchain.embeddings.base import Embeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from tqdm import tqdm

from src.config.constant import (CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR,
                                 PROCESSED_DATA_PATH, PROJECT_ROOT)


EMBEDDING_MODEL = "text-embedding-bge-m3"
EMBEDDING_URL = "http://192.168.0.109:1234/v1"


# 自訂 LM Studio 文字嵌入類別，繼承自 LangChain 的 Embeddings
class LmStudioEmbeddings(Embeddings):
    def __init__(self, model_name, url):
        """
        初始化 LM Studio Embeddings
        :param model_name: 要使用的嵌入模型名稱
        :param url: LM Studio 本地或遠端 API 的位址
        """
        self.model_name = model_name
        self.url = url
        # 建立 OpenAI 客戶端，連接 LM Studio 的 API
        self.client = OpenAI(base_url=url, api_key="lm-studio")

    def embed_query(self, text: str):
        """
        將單筆文字轉換為向量
        :param text: 要嵌入的文字
        :return: 向量 (list of float)
        """
        response = self.client.embeddings.create(
            input=text,      # 傳入單筆文字
            model=self.model_name  # 指定使用的模型
        )
        # 回傳第一筆 embedding
        return response.data[0].embedding

    def embed_documents(self, texts: list[str]):
        """
        將多筆文字轉換為向量
        :param texts: 要嵌入的文字列表
        :return: 向量列表，每個元素對應一筆文字
        """
        response = self.client.embeddings.create(
            input=texts,     # 傳入多筆文字
            model=self.model_name  # 指定使用的模型
        )
        # 回傳每筆文字的 embedding
        return [x.embedding for x in response.data]


def tiktoken_len(text):
    tokenizer = tiktoken.encoding_for_model("gpt-4")
    tokens = tokenizer.encode(text)
    return len(tokens)


def connect_to_vector_db(collection_name, embeddings):
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,     # 向量資料表名稱
        embedding_function=embeddings,              # 指定embedding模型
        persist_directory=CHROMA_PERSIST_DIR        # 向量資料庫存取路徑
    )


def parent_document_slicer(parent_docs, child_splitter):
    total_docs = []
    for doc in parent_docs:
        parent_id = str(doc.metadata.get("steam_appid"))
        doc.metadata["parent_id"] = parent_id
        doc.metadata["doc_id"] = parent_id

        split_docs = child_splitter.split_documents([doc])
        num = 1
        for sdoc in split_docs:
            sdoc.metadata["parent_id"] = parent_id
            sdoc.metadata["doc_id"] = parent_id + f"_0{str(num)}"
            num += 1 + 1
        total_docs.append(doc)
        total_docs.extend(split_docs)

    print(f"父層文件（原始）數量：{len(parent_docs)}")
    print(f"分段後文件數量：{len(total_docs)}")

    return total_docs


def deduplicated_docs(total_docs):
    # 輸入向量資料庫前先進行簡單去重複
    ids = [doc.metadata['doc_id'] for doc in total_docs]

    # 藉由重新配對doc和ids，將重複值去除
    unique_data = {doc_id: doc for doc_id, doc in zip(ids, total_docs)}

    # 取得新的ids和docs
    unique_ids = list(unique_data.keys())
    unique_docs = list(unique_data.values())

    print(f"去重前資料筆數: {len(total_docs)}, {len(ids)}")
    print(f"去重後資料筆數: {len(unique_docs)}, {len(unique_ids)}")

    return unique_docs, unique_ids


"""讀取資料"""
input_num = 1

while True:
    input_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("document")
    input_file = f"document_{input_num}.json"
    input_path = input_folder / input_file

    if not input_path.exists():
        print("所有檔案皆以處理完畢")
        break

    with open(input_path, "r", encoding="utf-8") as f:
        data_list = json.load(f)

    print(f"讀入document_{input_num}.json檔案，共{len(data_list)}筆資料")

    """計算單筆資料文本平均字數"""
    total = 0
    for doc in data_list:
        word = doc.get("context", "")
        total += len(word)

    token_count = (total / len(data_list)) / 4

    print(f"粗估平均token數: {token_count}")

    """轉換成Document物件"""
    doc_list = [Document(page_content=d["context"], metadata=d["metadata"])
                for d in data_list]

    print(f"已成功轉換{len(doc_list)}筆Document物件資料！")

    """載入Embedding模型"""
    embeddings = LmStudioEmbeddings(
        model_name=EMBEDDING_MODEL, url=EMBEDDING_URL)
    print("已建立embedding模型連線")

    """進行文本切割"""
    # 父文件不切割，用完整文件列表
    parent_docs = doc_list

    # 建立子文件切割器
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300, chunk_overlap=70, length_function=tiktoken_len)

    total_docs = parent_document_slicer(
        parent_docs, child_splitter=child_splitter)

    """存入前清洗"""

    unique_docs, unique_ids = deduplicated_docs(total_docs)

    """建立向量資料庫並存入資料"""
    vector_store = connect_to_vector_db(
        collection_name=CHROMA_COLLECTION_NAME, embeddings=embeddings)

    batch_size = 200
    total_docs_count = len(total_docs)

    for i in tqdm(range(0, len(unique_docs), batch_size), desc="寫入進度"):
        batch_docs = unique_docs[i: i + batch_size]
        batch_ids = unique_ids[i: i + batch_size]

        vector_store.add_documents(
            documents=batch_docs,
            ids=batch_ids
        )
        time.sleep(1)

    print(
        f"已成功將document_{input_num}.json的{len(total_docs)}筆資料存入向量資料庫({CHROMA_PERSIST_DIR})")

    input_num += 1
