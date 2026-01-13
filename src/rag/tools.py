from langchain_core.tools import tool
from pydantic import BaseModel, Field

"""
RAG工具
"""


class FewGameInput(BaseModel):
    question: str = Field(description="查詢的問題文字")
    k: int = Field(default=2, description="要回傳的文件數量")

def create_few_game_rag_tool(vector_store):

    @tool("few_game_rag", args_schema=FewGameInput)
    def few_game_rag(question, n=10, k=2):
        """
        當使用者詢問關於『特定 1-2 款遊戲』的詳細資訊時使用。
        例如：某款遊戲的背景故事、具體玩法機制、硬體配備要求等。
        這會提供非常完整的文本資料。

        Args:
            question (str): 查詢的問題文字。
            n (int): 搜尋子文件的數量。
            k (int): 要回傳的文件數量，預設為 2。若有需要可以增加查詢筆數。

        Returns:
            documents: 檢索到的相似文件列表。
        """
        # 檢索子文件
        child_docs = vector_store.similarity_search(question, k=n)

        # 提取父文件id
        unique_parent_ids = list(dict.fromkeys([
            doc.metadata["parent_id"] for doc in child_docs if "parent_id" in doc.metadata
        ]))

        target_ids = unique_parent_ids[:k]
        if not target_ids:
            return []

        # 批次查詢父文件
        parent_documents = vector_store.similarity_search(
            query="",
            k=len(target_ids),
            filter={"doc_id": {"$in": target_ids}}  # 假設支援 $in 運算子
        )

        return parent_documents
    return few_game_rag