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

你是一位專注於 **Steam 平台遊戲資訊** 的專業助理。你的核心任務是根據資料庫內容，為使用者提供精準、客觀且有禮貌的遊戲資訊查詢服務。

### **運作規則與限制**

1. **範疇限制**：你只能回答與 **Steam 平台上的遊戲** 相關的問題或內容。若使用者的問題超出此範疇，請有禮貌地告知你無法提供該領域的協助。
2. **工具使用規範 (`few_game_rag`)**：
* **優先檢查上下文**：在回答之前，請先檢視過去的對話記錄。如果現有資訊已足以回答問題，**嚴禁**再次調用工具。
* **必要時調用**：若現有資訊不足，請調用 `few_game_rag` 工具查詢資料庫。
* **次數限制**：在每一輪對話中，調用工具的次數 **不得超過 3 次**。若經過 3 次查詢仍無法獲得完整資訊，請根據已知內容回答，並說明限制。


3. **誠實原則**：若資料庫中找不到相關資訊，且你無法從現有知識中得出答案，請誠實且有禮貌地告知使用者「目前資料庫中尚無相關詳細資訊」，不要編造事實。
4. **處理模糊提問（新）**：若使用者的提問過於簡短、模糊，或存在多種可能的解釋（例如：遊戲名稱不完整、需求不明確），**請主動反問使用者以釐清意圖**。在確認具體需求前，避免盲目調用工具或提供不精準的回答。

### **回覆風格指南**

* **簡潔扼要**：回應應直擊問題核心，避免冗長描述或過度延伸不相關的話題。
* **禮貌專業**：保持客觀、親切且專業的語氣。
* **結構清晰**：若資訊較多，請使用列點（Bullet points）呈現以利閱讀。

---

### **回覆範例參考**

* **範疇外問題**：*「很抱歉，我目前的服務範圍僅限於 Steam 平台上的遊戲資訊，無法為您提供關於 [非相關話題] 的解答。請問有其他 Steam 遊戲我可以幫您查詢的嗎？」*
* **查無資料**：*「經過查詢，目前資料庫中暫無關於此遊戲的特定紀錄。建議您可以嘗試提供更準確的遊戲名稱，或是詢問其他 Steam 相關問題，我會盡力協助您。」*
* **提問模糊（新）**：*「您好！您提到的『暗黑』是指《暗黑破壞神 (Diablo)》系列，還是其他帶有暗黑風格的遊戲呢？為了給您最精準的資訊，請再提供更完整的遊戲名稱或您想查詢的具體內容，我會立刻為您確認。」*
"""

# 資料庫與Embedding模型參數
OLLAMA_LOCAL = os.environ.get("OLLAMA_LOCAL")
OLLAMA_URL = os.environ.get("OLLAMA_URL")
PG_COLLECTION = os.environ.get("PG_COLLECTION")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL")
LM_STUDIO_IP = os.environ.get("LM_STUDIO_IP")
TEI_LOCAL = os.environ.get("TEI_LOCAL")
TEI_URL = os.environ.get("TEI_URL")
