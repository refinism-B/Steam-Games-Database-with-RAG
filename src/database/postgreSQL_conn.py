import os
import json

import psycopg2
from dotenv import load_dotenv
from ollama import Client
from pgvector.psycopg2 import register_vector

load_dotenv()

YOUR_PG_HOST = os.environ.get("PG_HOST")
YOUR_DB_NAME = os.environ.get("PG_DATABASE")
YOUR_USER = os.environ.get("PG_USERNAME")
YOUR_PASSWORD = os.environ.get("PG_PASSWORD")
YOUR_PORT = os.environ.get("PG_PORT")
OLLAMA_URL = os.environ.get("OLLAMA_URL")


def connect_to_pgSQL():
    DB_CONFIG = {
        "host": YOUR_PG_HOST,
        "database": YOUR_DB_NAME,
        "user": YOUR_USER,
        "password": YOUR_PASSWORD,
        "port": YOUR_PORT
    }

    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)  # 註冊 pgvector 型別
    cur = conn.cursor()
    return conn, cur


def connect_to_ollama():
    client = Client(OLLAMA_URL)
    return client


def upsert_documents(documents):
    client = connect_to_ollama()
    conn, cur = connect_to_pgSQL()

    upsert_query = """
    INSERT INTO document_embeddings (doc_id, content, metadata, embedding)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (doc_id) 
    DO UPDATE SET 
        content = EXCLUDED.content,
        metadata = EXCLUDED.metadata,
        embedding = EXCLUDED.embedding;
    """

    try:
        data_count = 1
        for doc in documents:
            # 先取出doc_id作為unique key
            doc_id = doc.metadata.get("doc_id")
            if not doc_id:
                print("跳過無 doc_id 的文件")
                continue

            # 生成向量
            text = doc.page_content
            response = client.embed(model='bge-m3', input=text)
            embedding = response['embeddings'][0]

            # 寫入資料庫
            cur.execute(
                upsert_query,
                (doc_id, text, json.dumps(doc.metadata), embedding)
            )

            if data_count % 100 == 0:
                conn.commit()
            data_count += 1

        conn.commit()
        print(f"成功處理 {len(documents)} 筆資料")

    except Exception as e:
        print(f"發生錯誤: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
