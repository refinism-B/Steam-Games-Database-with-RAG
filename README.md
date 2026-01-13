# Steam Games Database with RAG 🎮

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-Integration-green)](https://www.langchain.com/)
[![Chainlit](https://img.shields.io/badge/Chainlit-Frontend-FF69B4.svg)](https://docs.chainlit.io/)
[![Zeabur](https://zeabur.com/button.svg)](https://steam-rag-db.zeabur.app/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**這是一個結合資料工程 (Data Engineering) 與 Agentic RAG 的 Steam 遊戲數據分析專案。**

本專案建構了一個完整的自動化 Pipeline，從 Steam 平台採集遊戲數據，進行標準化 ETL 處理，並建立向量資料庫 (Vector Database)。透過 **Chainlit** 建構的互動式前端，使用者能以自然語言查詢遊戲資訊，系統後端採用 **LangChain** 架構，具備提示詞優化、歷史摘要與 RAG 工具調用功能。

🌟 **線上體驗 (Live Demo)**: [https://steam-rag-db.zeabur.app/](https://steam-rag-db.zeabur.app/)

---

## ✨ 核心功能 (Key Features)

### 🚀 現代化前端 (Frontend)
- **Interactive UI**: 使用 **Chainlit** 打造對話式介面，體驗流暢。
- **Model Switching**: 使用者可於介面切換不同模型：
    - `price/Gemini 3 flash` (完整體驗推薦)
    - `free/Gemini 3 flash`
    - `local/Gemma 3 12B` (需搭配本地伺服器)
- **Transparent Logic**: 可選擇是否展開 **RAG 思考過程**，即時查看「工具調用參數」與「檢索回傳資料」。

### 🧠 智慧後端 (Intelligent Backend)
- **LangChain Agent**: 採用 Tool Use 架構，根據問題自動判斷是否需要檢索 Steam 資料庫。
- **Prompt Engineering**:
    - **Query Rewriting**: 中間層 LLM 自動將口語提問重寫為精準的獨立查詢語句，補全上下文代名詞。
    - **History Summarization**: 當對話過長 (>3 輪) 時自動觸發摘要機制，壓縮歷史訊息以維持長期記憶並節省 Token。
- **RAG Architecture**:
    - **Hybrid Retrieval**: 採用 Parent-Document Retriever 策略，兼顧檢索精準度 (Child Chunk) 與上下文完整性 (Parent Chunk)。
    - **Cloud Integration**: 使用 **Cloud PostgreSQL (pgvector)** 與 **Cloud Ollama** 實現雲端向量存儲與計算。

### 🛠️ 自動化工程 (Data Engineering)
- **Data Ingestion**: 多執行緒爬蟲採集 Steam Info, Reviews, Tags。
- **ETL Pipeline**: 自動清洗 HTML、標準化格式、攤平巢狀結構，並轉換為 RAG 專用 Document 格式。

---

## 🏗️ 系統架構 (Architecture)

```mermaid
graph TD
    subgraph Frontend [Frontend Interface]
        User([User]) <--> Chainlit[Chainlit App<br/>(Zeabur Trigger)]
        Chainlit -->|Config| Settings[Model & RAG Switch]
    end

    subgraph Backend_Agent [Agentic RAG Core]
        Chainlit --> Agent[LangChain Agent]
        Agent --> Rewrite[Query Rewriter]
        Agent --> Summarize[History Summarizer]
        Agent <-->|Tool Call| RAG_Tool[Game DB Retrieval]
        Agent -->|Generate| LLM["LLM Service<br/>(Gemini / Local Gemma)"]
    end

    subgraph Data_Pipe [Data Pipeline]
        Crawler[Crawler Scripts] -->|Fetch| SteamAPI[Steam Web API]
        SteamAPI --> RawData[Raw JSON]
        RawData --> ETL[ETL Process]
        ETL --> Docs[Documents]
    end

    subgraph Vector_System [Cloud Infrastructure]
        Docs --> Embed[Embedding Model<br/>(Cloud Ollama)]
        Embed --> VectorDB[(Vector DB<br/>Cloud PostgreSQL)]
        RAG_Tool <-->|Retrieve| VectorDB
    end

    Data_Pipe --> Vector_System
```

---

## 📂 專案結構 (Directory Structure)

詳細目錄說明請參閱 [Docs/Project Structure](docs/project_structure.md)。

```text
Steam-Games-Database-with-RAG/
├── app.py                 # Chainlit 應用程式入口
├── chainlit.md            # Chainlit 歡迎頁面設定
├── src/                   # 核心原始碼
│   ├── llm/               # Agent 邏輯 (Prompt rewriting, Summarization)
│   ├── rag/               # RAG Tools 定義
│   ├── embedding/         # 向量化服務串接
│   ├── crawler/           # 資料採集腳本
│   ├── ETL/               # 資料清洗轉換
│   └── database/          # PostgreSQL 連線設定
├── data/                  # 本地資料暫存 (Git ignored)
├── docs/                  # 專案文件
├── notebooks/             # 實驗性 Notebooks
└── .env                   # 環境變數設定
```

---

## 🚀 快速開始 (Quick Start)

### 1. 環境準備

確保您的系統已安裝 Python 3.10+。

```bash
git clone https://github.com/your-username/Steam-Games-Database-with-RAG.git
cd Steam-Games-Database-with-RAG
pip install -r requirements.txt
```

### 2. 設定環境變數

在專案根目錄建立 `.env` 檔案：

```ini
# .env Example

# Database (Cloud PostgreSQL)
PG_HOST=your_db_host
PG_DATABASE=your_db_name
PG_USERNAME=your_db_user
PG_PASSWORD=your_db_password
PG_PORT=5432
PG_COLLECTION=steam_games_DB

# Embedding (Cloud Ollama)
OLLAMA_URL=https://your-ollama-service-url
EMBEDDING_MODEL=bge-m3

# LLM Keys
GOOGLE_API=your_gemini_api_key        # Default
GOOGLE_API_PRICE=your_paid_api_key    # Optional
```

### 3. 啟動應用程式

使用 Chainlit 啟動前端介面：

```bash
chainlit run app.py -w
```
瀏覽器將自動開啟 `http://localhost:8000`。

---

## 🗓️ 開發藍圖 (Roadmap)

- [x] **資料工程**: 完成 Steam 爬蟲、ETL 流程與 PostgreSQL 向量庫建置。
- [x] **RAG 系統**: 實作 Parent-Document Retrieval 與 LangChain Agent。
- [x] **前端介面**: 整合 Chainlit 提供對話式 Web UI。
- [x] **雲端部署**: 成功部署至 Zeabur 平台。
- [ ] **多工具擴展**: 增加更多查詢工具（如：價格歷史比對、類似遊戲推薦）。
- [ ] **多模態支援**: 未來計畫加入遊戲截圖或影片的分析能力。

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
