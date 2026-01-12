import json
import os
import time

import psycopg2
from dotenv import load_dotenv
from ollama import Client
from pgvector.psycopg2 import register_vector
from psycopg2.extras import execute_values

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

    pg_url = f"postgresql+psycopg2://{DB_CONFIG["user"]}:{DB_CONFIG["password"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}/{DB_CONFIG["database"]}"
    return pg_url


def upsert_documents(documents, client, batch_size=20):
    conn, cur = connect_to_pgSQL()

    upsert_query = """
    INSERT INTO document_embeddings (doc_id, content, metadata, embedding)
    VALUES %s
    ON CONFLICT (doc_id)
    DO UPDATE SET
        content = EXCLUDED.content,
        metadata = EXCLUDED.metadata,
        embedding = EXCLUDED.embedding;
    """

    try:
        for i in range(0, len(documents), batch_size):
            batch = documents[i: i + batch_size]

            # 1. 準備批次文字與 Metadata
            batch_texts = [doc.page_content for doc in batch]
            batch_metadatas = [json.dumps(doc.metadata) for doc in batch]
            batch_ids = [doc.metadata.get("doc_id") for doc in batch]

            # 2. 批次生成向量
            current_end = min(i + batch_size, len(documents))
            print(f"開始進行批次向量化資料:第{i}筆到第{current_end}筆")
            response = client.embed(model='bge-m3', input=batch_texts)
            batch_embeddings = response['embeddings']

            # 3. 整理資料格式
            data_to_upsert = [
                (doc_id, text, meta, emb)
                for doc_id, text, meta, emb in zip(batch_ids, batch_texts, batch_metadatas, batch_embeddings)
                if doc_id  # 確保 doc_id 存在
            ]

            # 4. 執行批次寫入
            print(f"批次寫入資料庫:第{i}筆到第{current_end}筆")
            execute_values(cur, upsert_query, data_to_upsert)
            conn.commit()
            time.sleep(1)

    except Exception as e:
        print(f"發生錯誤: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
