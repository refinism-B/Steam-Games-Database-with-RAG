以下是本專案目錄的架構與介紹

Steam-Games-Database-with-RAG/
├── data/                  # 存放各階段的資料 (不進入 Git)
│   ├── raw/               # 採集到的原始 API JSON 資料
│   └── processed/         # 經過清洗、標準化後的 CSV/Parquet (JSON/Document)
├── src/                   # 核心原始碼
│   ├── __init__.py
│   ├── config/            # 設定檔與常數
│   │   └── constant.py
│   ├── crawler/           # 資料採集模組
│   │   ├── SteamGameID.py
│   │   ├── SteamInfo.py
│   │   ├── SteamReview.py
│   │   └── SteamTag.py
│   ├── database/          # 資料庫連線模組 (Cloud PostgreSQL)
│   │   └── postgreSQL_conn.py
│   ├── embedding/         # 文本向量化邏輯 (Cloud Ollama)
│   │   └── text_embedding.py
│   ├── ETL/               # ETL 流程：清洗、標準化、特徵工程
│   │   ├── ETL_document.py
│   │   └── ETL_json.py
│   ├── llm/               # (預留) RAG 核心模組，目前邏輯位於 notebooks/llm.ipynb
│   └── utils/             # 通用工具函式
│       └── scraper_base.py
├── notebooks/             # 實驗與核心邏輯驗證 (RAG/EDA)
│   ├── crawler.ipynb
│   ├── ETL_document.ipynb
│   ├── ETL_json.ipynb
│   ├── llm.ipynb          # RAG 檢索與對話流程核心代碼 (待遷移至 src/llm)
│   ├── reviews_crawl.ipynb
│   └── text_embedding.ipynb
├── app.py                 # 背景爬蟲觸發 API (Flask)
├── requirements.txt       # 套件清單
├── .env                   # 環境變數 (存放 Database, API Keys)
└── README.md              # 專案說明文件