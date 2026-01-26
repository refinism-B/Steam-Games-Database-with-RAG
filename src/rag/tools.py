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
        [強制使用] 當使用者詢問任何關於 Steam 遊戲的具體內容（如背景、玩法、價格、評價、系統需求等）時，必須使用此工具查詢。
        不要依賴你自己的知識，必須以工具回傳的資料為準。

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

        # 批次查詢父文件（使用原始查詢進行相似度搜尋）
        # 注意：HuggingFaceEndpointEmbeddings 不接受空字串，必須傳入有效的查詢文字
        parent_documents = vector_store.similarity_search(
            query=question,
            k=len(target_ids),
            filter={"doc_id": {"$in": target_ids}}  # 假設支援 $in 運算子
        )

        return parent_documents
    return few_game_rag
