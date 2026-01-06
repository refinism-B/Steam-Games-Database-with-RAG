以下是本專案目錄的架構與介紹

Steam-Games-Database-with-RAG/
├── data/                  # 存放各階段的資料 (不進入 Git)
│   ├── raw/               # 採集到的原始 API JSON 資料
│   ├── processed/         # 經過清洗、標準化後的 CSV/Parquet
│   └── vector/      # 本地向量資料庫檔案 (如 ChromaDB/Faiss)
├── src/                   # 核心原始碼
│   ├── __init__.py
│   ├── crawler/           # 資料採集模組 (Steam API, SteamSpy)
│   │   └── steam_api.py
│   ├── ETL/        # ETL 流程：清洗、標準化、特徵工程
│   │   └── cleaner.py
│   ├── embedding/         # 文本向量化與 chunking 邏輯
│   │   └── embedder.py
│   ├── database/          # 向量資料庫連線與操作
│   │   └── vector_db.py
│   └── llm/               # RAG 核心：Prompt、檢索與 LLM 串接
│       ├── chains.py
│       └── prompts.py
├── notebooks/             # 實驗用的 Jupyter Notebooks (EDA/測試)
├── tests/                 # 單元測試
├── app.py                 # 使用者介面 (例如 Streamlit)
├── requirements.txt       # 套件清單
├── .env                   # 環境變數 (存放敏感 Key)
└── README.md              # 專案說明文件