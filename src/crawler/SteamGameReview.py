import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

# 假設 src.config.constant 存在於你的專案結構中
# 如果在測試環境缺失，請確保相關路徑變數已定義
from src.config.constant import (
    RAW_GAME_ID_SUBFOLDER,
    RAW_GAME_REVIEWS_SUBFOLDER,
    RAW_REVIEW_METADATA_SUBFOLDER,
    GAME_REVIEW_URL
)

# 設定 Logging 格式，讓輸出更專業
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class SteamReviewScraper:
    """
    Steam 遊戲評論爬蟲類別
    負責讀取遊戲 ID，訪問 Steam API 並儲存評論資料。
    """

    def __init__(self, root_path: Path):
        self.root = root_path
        self._init_paths()

        # 設定參數
        self.max_results_per_file = 2000
        self.max_retries = 5
        self.retry_delay_base = 15  # 基礎等待秒數

        # 執行狀態追蹤
        self.id_file_num = 1
        self.review_file_num = 1
        self.data_count = 0
        self.failed_list: List[int] = []
        self.failed_count = 0
        self.last_appid: Optional[int] = None

        # 暫存容器
        self.current_review_list: List[Dict] = []

        # 時間記錄
        self.start_time = datetime.now().strftime("%H:%M:%S")
        self.now_date = datetime.now().strftime("%Y-%m-%d")

    def _init_paths(self):
        """初始化並建立必要的資料夾路徑"""
        self.id_folder = self.root / RAW_GAME_ID_SUBFOLDER
        self.review_folder = self.root / RAW_GAME_REVIEWS_SUBFOLDER
        self.metadata_folder = self.root / RAW_REVIEW_METADATA_SUBFOLDER

        # 確保輸出目錄存在 (Good Practice)
        self.review_folder.mkdir(parents=True, exist_ok=True)
        self.metadata_folder.mkdir(parents=True, exist_ok=True)

    def _fetch_reviews(self, app_id: int) -> Optional[Dict]:
        """
        對單一 AppID 執行 API 請求，包含重試機制
        """
        url = GAME_REVIEW_URL.format(app_id)
        tries = 1

        while tries <= self.max_retries:
            try:
                res = requests.get(url, timeout=10)  # 建議加入 timeout 避免死鎖
                res.raise_for_status()  # 檢查 HTTP 狀態碼
                return res.json()

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
        """儲存目前的評論列表到 JSON 檔案"""
        now_time = datetime.now().strftime("%H:%M:%S")
        data_structure = {
            "update_date": self.now_date,
            "update_time": now_time,
            "data": self.current_review_list
        }

        filename = f"game_review_{self.review_file_num}.json"
        save_path = self.review_folder / filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data_structure, f, ensure_ascii=False, indent=2)

        logger.info(
            f"資料已更新至: {filename} (目前累積 {len(self.current_review_list)} 筆)")

    def _save_metadata(self):
        """儲存最終的執行報告"""
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

        filename = f"{now_date_filename}_metadata_game_review.json"
        save_path = self.metadata_folder / filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Metadata 已儲存至: {save_path}")

    def run(self):
        """執行爬蟲的主流程"""
        logger.info("啟動 Steam 評論爬蟲...")

        while True:
            id_filename = f"game_id_{self.id_file_num}.json"
            id_file_path = self.id_folder / id_filename

            if not id_file_path.exists():
                logger.info(f"找不到檔案 {id_filename}，視為所有清單處理完畢。")
                break

            logger.info(f"正在讀取清單檔案: {id_filename}")

            with open(id_file_path, 'r', encoding='utf-8') as f:
                game_list_data = json.load(f)

            game_list = game_list_data.get("data", [])

            for game in game_list:
                app_id = game.get("appid")
                if not app_id:
                    continue

                logger.info(
                    f"[{id_filename}] 開始處理第 {self.data_count + 1} 筆資料 (AppID: {app_id})...")

                review_data = self._fetch_reviews(app_id)
                review_data["appid"] = app_id

                if review_data:
                    self.current_review_list.append(review_data)
                    self.last_appid = app_id
                    self.data_count += 1

                    # 儲存邏輯：根據原程式碼，每次成功都寫入檔案（為了確保資料安全）
                    self._save_batch_data()

                    # 檢查是否需要切換下一個儲存檔案
                    if len(self.current_review_list) >= self.max_results_per_file:
                        logger.info(
                            f"單檔達到 {self.max_results_per_file} 筆上限，切換至新檔案。")
                        self.review_file_num += 1
                        self.current_review_list.clear()  # 清空暫存列表

                    time.sleep(2)  # 禮貌性等待
                else:
                    self.failed_count += 1
                    self.failed_list.append(app_id)

            self.id_file_num += 1

        self._save_metadata()
        logger.info("爬蟲任務全部完成！")


if __name__ == "__main__":
    # 取得專案根目錄 (根據原程式邏輯，為目前檔案往上兩層)
    project_root = Path(__file__).resolve().parents[2]

    scraper = SteamReviewScraper(project_root)
    scraper.run()
