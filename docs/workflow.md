# 專案工作流程 (Workflow)

本文件描述目前的系統實作流程，對應 `src/` 目錄下的程式碼邏輯。

## 0. 環境與前置作業 (Environment Setup)

- **環境變數**: 需配置 `.env` 檔案，包含 `STEAM_API_KEY` 與資料庫設定。
- **依賴套件**: 透過 `requirements.txt` 安裝 Python 依賴。
- **Embedding 模型 Server**: 專案設定連線至本地 LM Studio (預設 IP: `192.168.0.109:1234`)，使用 `text-embedding-bge-m3` 模型。

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
        -   **硬體需求攤平**: 解析 `pc_requirements`, `mac_requirements` 等欄位，將巢狀結構攤平為 `pc_requirements_minimum` 等格式。
        -   **數值處理**: 轉換價格 (cent to unit)、計算好評率 (`positive_rate`)。
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
        -   **Parent Chunk**: 1000 tokens (負責檢索上下文)。
        -   **Child Chunk**: 300 tokens (負責向量計算)。
    -   **ID 關聯**: 建立 Parent-Child ID 對應 (`_p0x`, `_c0x`)。
2.  **去重複 (Deduplication)**:
    -   在寫入前根據 `doc_id` 檢查並移除重複文件，確保資料庫唯一性。
3.  **向量化 (Embedding)**:
    -   透過 `LmStudioEmbeddings` class 呼叫本地 API (`text-embedding-bge-m3`)。
4.  **向量資料庫儲存**:
    -   使用 `langchain_chroma` 將向量與 Metadata 寫入本地 ChromaDB (`data\vector`)。

## 4. LLM & RAG (Prototype in Notebook)

目前 RAG 功能主要於 `notebooks/llm.ipynb` 進行實驗與驗證，架構如下：

1.  **LLM 模型選擇 (Flexible LLM Backend)**:
    -   支援 **Google Gemini** (`gemini-3-flash-preview`) 透過 `langchain_google_genai` 串接。
    -   支援 **LM Studio** (Local LLM, 如 `gemma-3-12b-it`) 透過 `ChatOpenAI` 介面相容串接。
    -   使用 `stream_chat_bot` 類別封裝，支援串流輸出 (Streaming) 與工具調用 (Tool Calling)。

2.  **RAG 檢索機制 (Parent-Document Retrieval)**:
    -   **檢索工具 (`get_qa` Tool)**: 定義為 LangChain Tool，供 LLM 自主決定何時調用。
    -   **兩階段檢索邏輯**:
        1.  先根據問題搜尋最相似的 $N$ 個子文件 (Child Chunks)。
        2.  取出對應的父文件 ID (`parent_id`) 進行去重 (`seen_ids`)。
        3.  回傳完整的父文件內容作為 Context，保留完整上下文。

3.  **對話流程 (Agent Loop)**:
    -   System Prompt 設定角色與行為。
    -   進入對話迴圈：接收 User Input -> LLM 思考 -> 判斷是否 Call Tool -> 執行檢索 -> 回傳 Tool Result -> LLM 生成最終回答。