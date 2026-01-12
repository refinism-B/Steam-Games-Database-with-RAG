# 專案工作流程 (Workflow)

本文件描述目前的系統實作流程，對應 `src/` 目錄下的程式碼邏輯。

## 0. 環境與前置作業 (Environment Setup)

- **環境變數**: 需配置 `.env` 檔案，包含 `STEAM_API_KEY`、`OLLAMA_URL` 與 `PG_HOST`/`PG_PASSWORD` 等資料庫設定。
- **依賴套件**: 透過 `requirements.txt` 安裝 Python 依賴。
- **Cloud Services**:
    -   **Database**: 使用雲端 PostgreSQL (支援 `pgvector` 擴充)。
    -   **Embedding Model**: 介接雲端 Ollama 服務 (預設使用 `bge-m3` 模型)。

## 1. 資料擷取 (Data Ingestion)

主要透過 `app.py` 提供的 Flask API 介面觸發背景爬蟲任務，或直接執行 `src/crawler/` 下的腳本。

1.  **取得 App ID 列表**:
    -   **執行腳本**: `src/crawler/SteamGameID.py`
    -   **功能**: 呼叫 Steam Web API，取得所有遊戲的 `appid`。
    -   **機制**: 包含自動重試、分批儲存 (`game_id_x.json`) 與 Metadata 紀錄。
2.  **觸發爬蟲 (透過 Web API)**:
    -   啟動 `app.py` 後，可透過以下 API 觸發背景執行緒 (`threading.Thread`) 進行爬取：
        -   `/run/info`: 觸發 `src/crawler/SteamInfo.py` (遊戲詳細資訊)
        -   `/run/review`: 觸發 `src/crawler/SteamReview.py` (遊戲評論)
        -   `/run/tag`: 觸發 `src/crawler/SteamTag.py` (遊戲標籤)
3.  **原始資料儲存**:
    -   資料存入 `data/raw/` 對應子目錄 (`game_info`, `game_review`, `game_tag`)，格式為分批的 JSON 檔案。

## 2. ETL 流程 (ETL Process)

ETL 分為兩個階段：清洗合併 (`ETL_json.py`) 與 文件結構化 (`ETL_document.py`)。

1.  **資料合併與清洗 (`src/ETL/ETL_json.py`)**:
    -   **輸入**: 讀取 `data/raw/` 下的三類原始 JSON 檔案。
    -   **合併**: 依據 `appid` 將 Info, Review, Tag 資料合併為單一物件。
    -   **清洗邏輯**:
        -   **HTML 去除**: 使用 `BeautifulSoup` 去除描述欄位中的 HTML 標籤。
        -   **硬體需求攤平**: 解析 `pc_requirements`, `mac_requirements` 等欄位，將巢狀結構攤平。
        -   **數值處理**: 轉換價格、計算好評率 (`positive_rate`)。
    -   **輸出**: 存入 `data/processed/json_data/`。

2.  **文件結構化 (`src/ETL/ETL_document.py`)**:
    -   **輸入**:讀取 `data/processed/json_data/`。
    -   **轉換**: 將資料重組為 RAG 專用的 Document 格式：
        -   `context`: 包含描述性欄位 (`detailed_description`, `short_description` 等) 的純文字組合。
        -   `metadata`: 包含數值與過濾用欄位 (`price`, `release_date`, `tags`, `genres` 等)。
    -   **輸出**: 存入 `data/processed/document/`。

## 3. Text Embedding & Vector Storage

由 `src/embedding/text_embedding.py` 執行向量化與存儲。

1.  **文件讀取與切割**:
    -   讀取 Document 格式的 JSON 檔案。
    -   **Parent-Document Splitter**:
        -   **Parent Chunk**: 1000 tokens (負責檢索完整上下文)。
        -   **Child Chunk**: 300 tokens (負責向量相似度計算)。
    -   **ID 關聯**: 建立 Parent-Child ID 對應 (`_p0x`, `_c0x`)。
2.  **向量化 (Embedding)**:
    -   呼叫雲端 **Ollama API** 進行 Embedding (使用 `bge-m3` 模型)。
    -   批次處理以提升效率。
3.  **向量資料庫儲存 (Cloud PostgreSQL)**:
    -   透過 `src/database/postgreSQL_conn.py` 連線至雲端資料庫。
    -   使用 `UPSERT` 邏輯寫入 `document_embeddings` 表格 (避免重複 ID)。
    -   同時儲存 `embedding` (向量), `content` (文字), `metadata` (屬性)。

## 4. LLM & RAG (Implemented in Notebook)

目前 RAG 檢索與對話邏輯位於 `notebooks/llm.ipynb`。

1.  **LLM 模型選擇**:
    -   可切換 **Google Gemini** (Cloud) 或 **LM Studio** (Local) 作為推論核心。
    -   使用 `stream_chat_bot` 支援串流輸出與 Tool Calling。

2.  **RAG 檢索機制 (Parent-Document Retrieval)**:
    -   **檢索工具 (`get_qa`)**:
        -   LLM 根據使用者問題自動決定是否調用檢索工具。
    -   **兩階段優化流程**:
        1.  **子文件檢索**: 使用 `vector_store.similarity_search` 找出 Top-N 個最相關的 Child Chunks。
        2.  **父文件回溯**: 從 Child Chunks 解析出唯一的 `parent_id`。
        3.  **完整上下文獲取**: 根據 `parent_id` 從 PostgreSQL 拉取完整的 Parent Documents。
        4.  **去重**: 確保回傳給 LLM 的是獨特且完整的遊戲資訊片段。

3.  **系統提示與互動**:
    -   System Prompt 設定角色為「Steam 遊戲資料研究員」。
    -   回答嚴格基於檢索到的 Context，若無資料則誠實告知。