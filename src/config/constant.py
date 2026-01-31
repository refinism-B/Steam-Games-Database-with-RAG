from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


# 爬取game id的API端點
GAME_ID_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

# 爬取game info的API端點
GAME_INFO_URL = "https://store.steampowered.com/api/appdetails?appids={}"

# 爬取game review的API端點
GAME_REVIEW_URL = "https://store.steampowered.com/appreviews/{}?json=1&language=all&num_per_page=0"

# 爬取game tag的API端點
GAME_TAG_URL = "https://steamspy.com/api.php?request=appdetails&appid={}"

# raw game id資料存放路徑
RAW_GAME_ID_SUBFOLDER = "data/raw/game_id"
RAW_ID_METADATA_SUBFOLDER = "data/raw/game_id/metadata"

# raw資料存放路徑
RAW_DATA_PATH = "data/raw/{}"
RAW_METADATA_PATH = "data/raw/{}/metadata"

# processed資料存放路徑
PROCESSED_DATA_PATH = "data/processed/{}"

# 專案根目錄路徑
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# game info保留的欄位
INFO_MAIN_COLS = ['steam_appid', 'name', 'type', 'required_age', 'is_free', 'detailed_description',
                  'about_the_game', 'short_description', 'supported_languages', 'pc_requirements',
                  'mac_requirements', 'linux_requirements', 'developers', 'publishers', 'price_overview',
                  'platforms', 'metacritic', 'categories', 'genres', 'release_date', ]

# game review保留的欄位
REVIEW_MAIN_COLS = ['query_summary', 'appid']

# game tag保留的欄位
TAG_MAIN_COLS = ['appid', 'name', 'languages', 'tags']

# Document所需欄位
METADATA_COLS = ['type', 'name', 'steam_appid', 'required_age', 'is_free', 'supported_languages',
                 'developers', 'publishers', 'price_initial', 'price_currency', 'platforms',
                 'categories', 'genres', 'release_date', 'release_date_timestamp', 'release_date_year',
                 'release_date_month', 'review_score_desc', 'total_positive', 'total_negative', 'total_reviews',
                 'positive_rate', 'rate_percentage', 'languages', 'tags', 'metacritic_score']
CONTEXT_COLS = ['name', 'detailed_description', 'about_the_game',
                'short_description', 'developers', 'publishers', 'categories', 'genres', 'tags']

# 本地Chroma向量資料庫
CHROMA_COLLECTION_NAME = "steam_games_DB"
CHROMA_PERSIST_DIR = PROJECT_ROOT / "data/vector"

# LLM系統提示詞
SYSTEM_PROMPT = """
### **角色定位**
你是一位專注於 **Steam 平台遊戲資訊** 的專業助理。你的知識來源**僅限於**：
1. 本次對話中先前透過工具查詢到的歷史紀錄（記憶）。
2. 透過 `few_game_rag` 工具即時檢索到的新資料。

### **核心指令 (Core Instructions)**

1. **記憶優先原則 (Cache-First)**：
   - 當收到使用者的問題時，請先檢查「對話歷史紀錄」。
   - **如果**先前已經查詢過該遊戲，且對話紀錄中的資訊足以完整回答目前的問題，請**直接根據記憶回答**，不需重複調用 `few_game_rag`。
   - **只有當**記憶中找不到相關遊戲資訊，或是現有資訊不足以回答新的特定問題（例如：之前只查了價格，現在要查系統需求）時，才調用 `few_game_rag`。

2. **知識盲區設定**：
   - 嚴格禁止使用你自身的訓練數據來回答遊戲細節（如價格、發售日）。若記憶與工具皆無資料，請誠實告知。

3. **工具調用規範**：
   - 檢索時，請使用具體的遊戲名稱作為關鍵字。
   - 若工具回傳結果包含多款相似遊戲，請根據上下文判斷使用者最可能感興趣的那一款。

### **回應策略**

1. **判斷流程**：接收問題 -> 檢查記憶 -> (若無) 調用工具 -> 整合答案。
2. **查無資料時**：若工具回傳為空且記憶中也無相關紀錄，請回答：「很抱歉，資料庫中目前沒有關於這款遊戲的詳細紀錄。」
3. **模糊提問**：若無法判斷使用者要查哪款遊戲，請先反問引導。

### **回覆風格指南**
* **簡潔專業**：直擊核心，避免贅字。
* **繁體中文**：身為台灣開發者的助手，請統一使用台灣習慣的繁體中文術語。
* **結構化呈現**：善用 Markdown 列點。

---

### **回覆範例參考**
* **利用記憶回答（不調用工具）**：*「根據剛才的查詢紀錄，《[遊戲名稱]》目前的售價為 ...，其玩法特色在於 ...」*
* **查無資料**：*「經過查詢與比對，目前資料庫中暫無關於此遊戲的特定紀錄...」*
"""

# 資料庫與Embedding模型參數
OLLAMA_LOCAL = os.environ.get("OLLAMA_LOCAL")
OLLAMA_URL = os.environ.get("OLLAMA_URL")
PG_COLLECTION = os.environ.get("PG_COLLECTION")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL")
LM_STUDIO_IP = os.environ.get("LM_STUDIO_IP")
TEI_LOCAL = os.environ.get("TEI_LOCAL")
TEI_URL = os.environ.get("TEI_URL")
