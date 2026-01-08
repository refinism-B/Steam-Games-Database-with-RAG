from pathlib import Path

# 爬取game id的API端點
GAME_ID_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

# 爬取game info的API端點
GAME_INFO_URL = "https://store.steampowered.com/api/appdetails?appids={}"

# 爬取game review的API端點
GAME_REVIEW_URL = "https://store.steampowered.com/appreviews/{}?json=1&language=all&num_per_page=0"

# 爬取game tag的API端點
GAME_TAG_URL = "https://steamspy.com/api.php?request=appdetails&appid={}"

# raw資料存放路徑
RAW_GAME_ID_SUBFOLDER = r"data\raw\game_id"
RAW_ID_METADATA_SUBFOLDER = r"data\raw\game_id\metadata"

RAW_DATA_PATH = r"data\raw\{}"
RAW_METADATA_PATH = r"data\raw\{}\metadata"

PROCESSED_DATA_PATH = r"data\processed\{}"

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
