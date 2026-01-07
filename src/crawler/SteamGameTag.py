import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

# 引用專案設定檔
# 請確保 src.config.constant 存在且定義了正確變數
try:
    from src.config.constant import (
        RAW_GAME_ID_SUBFOLDER,
        RAW_GAME_TAG_SUBFOLDER,
        RAW_TAG_METADATA_SUBFOLDER,
        GAME_TAG_URL
    )
except ImportError:
    # 為了讓此腳本能獨立測試，若找不到 config 則提供預設值 (僅供測試用)
    logging.warning("未找到 src.config.constant，使用預設路徑設定。")
    RAW_GAME_ID_SUBFOLDER = "data/raw/game_id"
    RAW_GAME_TAG_SUBFOLDER = "data/raw/game_tag"
    RAW_TAG_METADATA_SUBFOLDER = "data/raw/game_tag/metadata"
    GAME_TAG_URL = "https://store.steampowered.com/app/{}?cc=us&l=english" # 範例 URL，實際請以您的 config 為準

# 設定 Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class SteamTagScraper:
    """
    Steam 遊戲標籤 (Tag) 爬蟲類別
    負責讀取遊戲 ID，訪問 API 取得標籤資料並儲存。
    """

    def __init__(self, root_path: Path):
        self.root = root_path
        self._init_paths()
        
        # 爬蟲設定參數
        self.max_results_per_file = 2000
        self.max_retries = 5
        self.retry_delay_base = 10
        
        # 狀態追蹤
        self.id_file_num = 1
        self.tag_file_num = 1
        self.data_count = 0
        self.failed_list: List[int] = []
        self.failed_count = 0
        self.last_appid: Optional[int] = None
        
        # 資料容器
        self.current_tag_list: List[Dict] = []
        
        # 時間戳記
        self.start_time = datetime.now().strftime("%H:%M:%S")
        self.now_date = datetime.now().strftime("%Y-%m-%d")

    def _init_paths(self):
        """初始化資料夾路徑，確保目標資料夾存在"""
        self.id_folder = self.root / RAW_GAME_ID_SUBFOLDER
        self.tag_folder = self.root / RAW_GAME_TAG_SUBFOLDER
        self.metadata_folder = self.root / RAW_TAG_METADATA_SUBFOLDER
        
        # 自動建立輸出目錄
        self.tag_folder.mkdir(parents=True, exist_ok=True)
        self.metadata_folder.mkdir(parents=True, exist_ok=True)

    def _fetch_single_game_tag(self, app_id: int) -> Optional[Dict]:
        """
        爬取單一遊戲的 Tag 資料 (包含重試機制)
        """
        url = GAME_TAG_URL.format(app_id)
        tries = 1
        
        while tries <= self.max_retries:
            try:
                res = requests.get(url, timeout=10)
                # 若 API 回傳非 200，這裡可以選擇是否要 raise_for_status
                # 視具體 API 行為而定，通常建議加上檢查
                if res.status_code != 200:
                    logger.warning(f"AppID {app_id} 回傳狀態碼 {res.status_code}")
                
                # 嘗試解析 JSON
                tag_data = res.json()
                return tag_data

            except Exception as e:
                logger.warning(f"爬取 AppID {app_id} 發生錯誤 (第 {tries} 次): {e}")
                if tries < self.max_retries:
                    sleep_time = tries * self.retry_delay_base
                    logger.info(f"等待 {sleep_time} 秒後重試...")
                    time.sleep(sleep_time)
                    tries += 1
                else:
                    logger.error(f"已達重試上限，跳過 AppID {app_id}")
                    return None
        return None

    def _save_batch_data(self):
        """將目前的 Tag 列表寫入檔案"""
        now_time = datetime.now().strftime("%H:%M:%S")
        
        output_data = {
            "update_date": self.now_date,
            "update_time": now_time,
            "data": self.current_tag_list
        }
        
        filename = f"game_tag_{self.tag_file_num}.json"
        save_path = self.tag_folder / filename
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[{filename}] 資料儲存完畢 (目前累積 {len(self.current_tag_list)} 筆)")

    def _save_metadata(self):
        """儲存執行報告 (Metadata)"""
        end_time = datetime.now().strftime("%H:%M:%S")
        now_date_filename = datetime.now().strftime("%Y%m%d")
        
        metadata = {
            "update_date": self.now_date,
            "start_time": self.start_time,
            "end_time": end_time,
            "failed_count": self.failed_count,
            "failed_list": self.failed_list,
            "data_count": self.data_count,
            "last_appid": self.last_appid
        }

        filename = f"{now_date_filename}_metadata_game_tag.json"
        save_path = self.metadata_folder / filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Metadata 已儲存至: {save_path}")

    def run(self):
        """執行爬蟲主程序"""
        logger.info("啟動 Steam Tag 爬蟲...")

        while True:
            id_filename = f"game_id_{self.id_file_num}.json"
            id_path = self.id_folder / id_filename

            if not id_path.exists():
                logger.info(f"找不到檔案 {id_filename}，視為所有清單處理完畢。")
                break

            logger.info(f"正在讀取清單檔案: {id_filename}")
            
            with open(id_path, 'r', encoding='utf-8') as f:
                game_list_data = json.load(f)

            game_list = game_list_data.get("data", [])

            for game in game_list:
                app_id = game.get("appid")
                if not app_id:
                    continue
                
                logger.info(f"[{id_filename}] 開始搜尋第 {self.data_count + 1} 筆資料 (AppID: {app_id})...")

                tag_data = self._fetch_single_game_tag(app_id)

                if tag_data:
                    self.current_tag_list.append(tag_data)
                    self.last_appid = app_id
                    self.data_count += 1
                    
                    # 依照原始邏輯：每抓一筆就存檔一次 (Checkpoint)
                    self._save_batch_data()
                    time.sleep(2) # 禮貌性延遲

                    # 檢查是否需要換檔
                    if len(self.current_tag_list) >= self.max_results_per_file:
                        logger.info(f"單檔已達 {self.max_results_per_file} 筆，切換至下一個檔案。")
                        self.tag_file_num += 1
                        self.current_tag_list.clear()
                else:
                    self.failed_count += 1
                    self.failed_list.append(app_id)

            self.id_file_num += 1

        self._save_metadata()
        logger.info("爬蟲任務全部完成！")

if __name__ == "__main__":
    # 取得專案根目錄 (假設此 script 位於專案結構深處，往上兩層為 root)
    project_root = Path(__file__).resolve().parents[2]
    
    scraper = SteamTagScraper(project_root)
    scraper.run()