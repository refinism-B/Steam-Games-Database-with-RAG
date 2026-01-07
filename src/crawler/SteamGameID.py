import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config.constant import GAME_ID_URL, RAW_GAME_ID_SUBFOLDER


import requests
from dotenv import load_dotenv

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()


@dataclass
class CrawlerConfig:
    """爬蟲設定檔"""
    api_key: str = os.environ.get("STEAM_API_KEY", "")
    base_url: str = GAME_ID_URL
    project_root: Path = Path(__file__).resolve().parents[2]

    # 資料存儲路徑 (相對於 project_root)
    raw_data_sub_folder: str = RAW_GAME_ID_SUBFOLDER
    max_result_per_request: int = 4000  # 每次 API 請求的筆數
    max_items_per_file: int = 4000     # 每個檔案最大儲存筆數
    max_retries: int = 5               # 最大重試次數
    retry_delay_multiplier: int = 10   # 重試等待時間倍數


class SteamAppIDCrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.current_game_list: List[Dict] = []
        self.last_appid: int = 0
        self.search_times: int = 0
        self.data_count: int = 0
        self.file_num: int = 1
        self.start_time: str = datetime.now().strftime("%H:%M:%S")
        self.search_result_status: bool = False

        # 初始化路徑
        self.data_folder = self.config.project_root / self.config.raw_data_sub_folder
        self.metadata_folder = self.data_folder / "metadata"
        self._ensure_directories()

    def _ensure_directories(self):
        """確保輸出目錄存在"""
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.metadata_folder.mkdir(parents=True, exist_ok=True)

    def _get_request_params(self) -> Dict[str, Any]:
        """產生 API 請求參數"""
        return {
            'key': self.config.api_key,
            'include_games': 'true',
            'include_dlc': 'false',
            'include_software': 'false',
            'include_videos': 'false',
            'max_results': self.config.max_result_per_request,
            'last_appid': self.last_appid
        }

    def _fetch_page(self) -> Optional[Dict]:
        """執行單次 API 請求，包含重試機制"""
        tries = 1
        while tries <= self.config.max_retries:
            try:
                logger.info(f"開始第 {self.search_times + 1} 次資料搜尋...")
                response = requests.get(
                    self.config.base_url, params=self._get_request_params())
                response.raise_for_status()  # 檢查 HTTP 錯誤
                return response.json()

            except Exception as e:
                logger.error(f"資料爬取發生錯誤: {e}")
                if tries < self.config.max_retries:
                    wait_time = tries * self.config.retry_delay_multiplier
                    logger.warning(f"等待 {wait_time} 秒後再次繼續...")
                    time.sleep(wait_time)
                    tries += 1
                else:
                    logger.error("已達重試次數上限，終止當前請求")
                    return None
        return None

    def _save_current_chunk(self):
        """將目前累積的資料寫入 JSON 檔案"""
        now_date = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")

        data = {
            "update_date": now_date,
            "update_time": now_time,
            "data": self.current_game_list
        }

        file_name = f"game_id_{self.file_num}.json"
        save_path = self.data_folder / file_name

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.data_count += len(self.current_game_list)

        logger.info(
            f"第 {self.search_times} 次搜尋資料儲存完畢！(File: {file_name}, Count: {len(self.current_game_list)})")

    def _check_and_rotate_file(self):
        """檢查是否達到單檔上限，若是則重置清單並增加檔案編號"""
        if len(self.current_game_list) >= self.config.max_items_per_file:
            self.file_num += 1
            self.current_game_list.clear()

    def _save_metadata(self):
        """建立並儲存 Metadata"""
        end_time = datetime.now().strftime("%H:%M:%S")
        now_date = datetime.now().strftime("%Y-%m-%d")
        now_date_filename = datetime.now().strftime("%Y%m%d")

        metadata = {
            "update_date": now_date,
            "start_time": self.start_time,
            "end_time": end_time,
            "search_result": self.search_result_status,
            "max_result": self.config.max_result_per_request,
            "search_times": self.search_times,
            "data_count": self.data_count,
            "last_appid": self.last_appid
        }

        metadata_file = f"{now_date_filename}_metadata_game_id.json"
        metadata_path = self.metadata_folder / metadata_file

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Metadata 已儲存至: {metadata_path}")

    def run(self):
        """執行爬蟲主程序"""
        if not self.config.api_key:
            logger.error("未設定 STEAM_API_KEY，請檢查 .env 檔案。")
            return

        while True:
            result = self._fetch_page()

            if not result:
                self.search_result_status = False
                break

            response_data = result.get("response", {})
            apps = response_data.get("apps", [])

            new_last_appid = response_data.get("last_appid")

            if new_last_appid:
                self.last_appid = new_last_appid
            elif apps:
                self.last_appid = apps[-1].get("appid")

            more_results = response_data.get("have_more_results")

            # 更新狀態
            self.current_game_list.extend(apps)
            self.search_times += 1

            # 存檔與輪替檢查
            self._save_current_chunk()

            # 模擬人類行為稍微暫停
            time.sleep(3)

            self._check_and_rotate_file()

            if not more_results:
                logger.info("已抓取所有資料。")
                self.search_result_status = True
                break

        # 最終儲存 Metadata
        self._save_metadata()


if __name__ == "__main__":
    # 初始化設定與爬蟲
    config = CrawlerConfig()
    crawler = SteamAppIDCrawler(config)

    # 開始執行
    crawler.run()
