# 專案工作流程 (Workflow)

本文件描述目前的系統實作流程，對應 `src/` 目錄下的程式碼邏輯。

## 0. 環境與前置作業 (Environment Setup)

- **環境變數**: 需配置 `.env` 檔案，包含 `STEAM_API_KEY`、`OLLAMA_URL`、`GOOGLE_API_KEY` 與 `PG_HOST`/`PG_PASSWORD` 等資料庫設定。
- **依賴套件**: 透過 `requirements.txt` 安裝 Python 依賴。
- **Cloud Services**:
    -   **Database**: 使用雲端 PostgreSQL (支援 `pgvector` 擴充)。
    -   **Embedding Model**: 介接雲端 Ollama 服務 (預設使用 `bge-m3` 模型)。
    -   **LLM Provider**: 支援 Google Gemini (Cloud) 或 LM Studio (Local)。

## 1. 資料擷取 (Data Ingestion)

目前主要透過直接執行 `src/crawler/` 下的 Python 腳本進行資料採集。

1.  **取得 App ID 列表**:
    -   **執行腳本**: `src/crawler/SteamGameID.py`
    -   **功能**: 呼叫 Steam Web API，取得所有遊戲的 `appid`。
    -   **機制**: 包含自動重試、分批儲存 (`game_id_x.json`) 與 Metadata 紀錄。
2.  **執行爬蟲任務**:
    -   **遊戲詳細資訊**: `src/crawler/SteamInfo.py`
    -   **遊戲評論**: `src/crawler/SteamReview.py`
    -   **遊戲標籤**: `src/crawler/SteamTag.py`
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
        -   **Context**: 包含描述性欄位 (`detailed_description`, `short_description` 等) 的純文字組合。
        -   **Metadata**: 包含數值與過濾用欄位 (`price`, `release_date`, `tags`, `genres`, `parent_id` 等)。
    -   **輸出**: 存入 `data/processed/document/`。

## 3. Text Embedding & Vector Storage

由 `src/embedding/text_embedding.py` 執行向量化與存儲。

1.  **文件讀取與切割**:
    -   讀取 Document 格式的 JSON 檔案。
    -   **Parent-Document Splitter**:
        -   **Parent Chunk**: 1000 tokens (負責檢索完整上下文)。
        -   **Child Chunk**: 300 tokens (負責向量相似度計算)。
    -   **ID 關聯**: 建立 Parent-Child ID 對應。
2.  **向量化 (Embedding)**:
    -   呼叫雲端 **Ollama API** 進行 Embedding (使用 `bge-m3` 模型)。
3.  **向量資料庫儲存 (Cloud PostgreSQL)**:
    -   透過 `src/database/postgreSQL_conn.py` 連線至雲端資料庫。
    -   使用 `UPSERT` 邏輯寫入 `document_embeddings` 表格。
    -   同時儲存 `embedding` (向量), `content` (文字), `metadata` (屬性)。

## 4. Agentic RAG & Chat System

核心邏輯位於 `src/llm/llm.py`，採用 LangChain 透過 Tool Calling 實現 Agentic RAG。

1.  **核心組件 (`stream_chat_bot`)**:
    -   **LLM Model**: 支援切換 `Gemini 3 flash` (Free/Price) 或 `Gemma 3 12B` (Local)。
    -   **Tools Binding**: 使用 `llm.bind_tools` 綁定 RAG 工具 (`few_game_rag`)。
    -   **Message History**: 維護對話歷史，包含 System Prompt、User Message、AI Message 及 Tool Message。

2.  **智慧優化流程**:
    -   **Prompt Rewriting (`_rephrase_query`)**: 
        -   在進入主要對話前，使用中間層 LLM 將使用者的口語提問轉換為完整的獨立查詢語句。
        -   參考最近的對話歷史以補全代名詞或上下文。
    -   **History Summarization (`_summarize_history`)**:
        -   當對話紀錄過長 (>3 輪) 時，自動觸發摘要機制。
        -   保留 System Prompt 與最新兩則訊息，其餘壓縮為摘要文字，節省 Token 並維持長期記憶。

3.  **RAG 檢索工具 (`src/rag/tools.py`)**:
    -   **Tool**: `few_game_rag`
    -   **觸發條件**: 當 LLM 判斷需要外部資訊回答遊戲細節時自動呼叫。
    -   **Parent-Document Retrieval**:
        1.  先檢索 `Child Chunks` (Top-N)。
        2.  回溯對應的 `Parent Documents` (Top-K)。
        3.  回傳完整的父文件內容給 LLM 進行生成。

## 5. 使用者介面 (User Interface)

前端採用 **Chainlit** 框架 (`app.py`)，提供互動式 Web 介面。

1.  **初始化與設定**:
    -   使用者可選擇 LLM 模型 (Gemini/Gemma)。
    -   開關 `Show RAG` 選項，決定是否顯示詳細的思考與檢索過程。
2.  **串流互動**:
    -   使用 `async` 非同步處理與 `yield` 串流輸出。
    -   **透明化過程**: 若開啟 RAG 顯示，會即時在 UI 呈現：
        -   `[執行]`: 顯示 LLM 正呼叫的工具與參數。
        -   `[結果]`: 顯示 RAG 檢索回來的資料內容。
    -   最後串流輸出 LLM 的最終回答。
