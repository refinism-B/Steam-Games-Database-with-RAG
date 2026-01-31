import time

from langchain_core.tools import tool
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from src.database.postgreSQL_conn import connect_to_pgSQL

"""
RAG工具
"""

# 建立 SQLAlchemy engine（模組層級，避免重複建立）
_pg_url = connect_to_pgSQL()
_engine = create_engine(_pg_url)


class FewGameInput(BaseModel):
    question: str = Field(description="查詢的問題文字")
    k: int = Field(default=2, description="要回傳的文件數量")


def create_few_game_rag_tool(vector_store):

    @tool("few_game_rag", args_schema=FewGameInput)
    def few_game_rag(question, n=10, k=2):
        """
        [強制使用] 當使用者詢問任何關於 Steam 遊戲的具體內容（如背景、玩法、價格、評價、系統需求等）時，必須使用此工具查詢。
        不要依賴你自己的知識，必須以工具回傳的資料為準。

        Args:
            question (str): 查詢的問題文字。
            n (int): 搜尋子文件的數量。
            k (int): 要回傳的文件數量，預設為 2。若有需要可以增加查詢筆數。

        Returns:
            documents: 檢索到的相似文件列表。
        """
        rag_start = time.time()

        # 步驟 1：計算 Embedding (約 0.9s)
        query_vector = vector_store.embeddings.embed_query(question)
        step1_end = time.time()
        print(f"⏱️ Step 1 (Embedding) 耗時: {step1_end - rag_start:.4f} 秒")
        
        # 步驟 2：使用 Raw SQL 檢索子文件 (優化 HNSW 索引)
        # [關鍵優化] 1. 只選取 metadata 減少資料傳輸量
        #            2. 設定 ef_search=40 避免搜尋過深
        target_ids = []
        try:
            # 格式化向量為 PostgreSQL 接受的字串格式
            vector_str = f"[{','.join(map(str, query_vector))}]"
            
            with _engine.connect() as conn:
                # [關鍵指令 1] 設定 HNSW ef_search 參數確保檢索速度
                conn.execute(text("SET LOCAL hnsw.ef_search = 40;"))
                
                # [關鍵指令 2] 執行向量查詢 SQL，只選取 metadata
                vector_sql = text("""
                    SELECT metadata 
                    FROM document_embeddings 
                    ORDER BY embedding <=> :vector_str 
                    LIMIT :n;
                """)
                result = conn.execute(vector_sql, {"vector_str": vector_str, "n": n})
                rows = result.fetchall()
            
            # 從結果中提取 parent_id 並去重
            unique_parent_ids = list(dict.fromkeys([
                row[0].get("parent_id") for row in rows if row[0].get("parent_id") is not None
            ]))
            # [關鍵修正] 強制轉型為字串，確保與 PG 索引 (metadata->>'doc_id') 的型態一致
            target_ids = [str(pid) for pid in unique_parent_ids[:k]]
            
        except Exception as e:
            print(f"❌ Step 2 向量檢索失敗：{e}")
        
        step2_end = time.time()
        print(f"⏱️ Step 2 (HNSW Search) 耗時: {step2_end - step1_end:.4f} 秒")

        if not target_ids:
            return []

        # ===== 重點優化：使用 Raw SQL 直接查詢，強制使用 B-tree 索引 =====
        # 完全捨棄向量搜尋，直接使用 doc_id 進行精確查找
        
        parent_documents = []
        try:
            # 使用 SQLAlchemy 執行 Raw SQL 查詢
            sql = text("""
                SELECT content, metadata 
                FROM document_embeddings 
                WHERE metadata->>'doc_id' = ANY(:ids)
            """)
            
            with _engine.connect() as conn:
                result = conn.execute(sql, {"ids": target_ids})
                rows = result.fetchall()
            
            # 將 SQL 結果轉換回 LangChain Document 物件
            for row in rows:
                parent_documents.append(
                    Document(page_content=row[0], metadata=row[1])
                )
                
        except Exception as e:
            print(f"❌ 取得父文件失敗：{e}")

        step3_end = time.time()
        print(f"⏱️ Step 3 (SQL Fetch) 耗時: {step3_end - step2_end:.4f} 秒")

        total_rag_duration = time.time() - rag_start
        print(f"⏱️ 優化後總 RAG 費時：{total_rag_duration:.2f} 秒")

        return parent_documents
    return few_game_rag
