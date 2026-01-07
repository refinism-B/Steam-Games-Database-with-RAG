import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config.constant import RAW_GAME_ID_SUBFOLDER, GAME_INFO_URL, RAW_GAME_INFO_SUBFOLDER, RAW_INFO_METADATA_SUBFOLDER

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
    project_root: Path = Path(__file__).resolve().parents[2]

    # 輸入路徑設定 (讀取 game_id)
    input_sub_folder: str = RAW_GAME_ID_SUBFOLDER

    # 輸出路徑設定 (儲存 game_info)
    output_sub_folder: str = RAW_GAME_INFO_SUBFOLDER

    # Metadata 輸出路徑 (依據原程式邏輯，維持存放在 game_id/metadata)
    metadata_sub_folder: str = RAW_INFO_METADATA_SUBFOLDER

    # 爬蟲參數
    max_items_per_file: int = 2000     # 每個輸出檔案存幾筆
    max_retries: int = 5               # 最大重試次數
    retry_delay_multiplier: int = 20   # 重試等待時間倍數 (秒)
    request_delay: int = 3             # 每次請求後的休息時間 (秒)
    # 若為 None 則爬取全部；若為整數則代表最多處理幾個 input 檔案
    max_input_files: Optional[int] = None


class SteamGameInfoCrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config

        # 狀態變數
        self.current_info_list: List[Dict] = []
        self.failed_list: List[int] = []
        self.total_data_count: int = 0
        self.failed_count: int = 0
        self.last_appid: Optional[int] = None

        # 檔案編號控制
        self.input_file_num: int = 1
        self.output_file_num: int = 1

        # 時間記錄
        self.start_time: str = datetime.now().strftime("%H:%M:%S")
        self.now_date: str = datetime.now().strftime("%Y-%m-%d")

        # 初始化路徑物件
        self.input_folder = self.config.project_root / self.config.input_sub_folder
        self.output_folder = self.config.project_root / self.config.output_sub_folder
        self.metadata_folder = self.config.project_root / self.config.metadata_sub_folder

        self._ensure_directories()

    def _ensure_directories(self):
        """確保輸出目錄存在"""
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.metadata_folder.mkdir(parents=True, exist_ok=True)

    def _get_game_details_url(self, app_id: int) -> str:
        return GAME_INFO_URL.format(app_id)

    def _fetch_single_game(self, app_id: int) -> Optional[Dict]:
        """執行單一遊戲的 API 請求，包含重試機制"""
        url = self._get_game_details_url(app_id)
        tries = 1

        while tries <= self.config.max_retries:
            try:
                response = requests.get(url, timeout=10)  # 加入 timeout 避免無限等待
                response.raise_for_status()
                return response.json()

            except Exception as e:
                logger.error(f"資料爬取發生錯誤 (AppID: {app_id}): {e}")
                if tries < self.config.max_retries:
                    wait_time = tries * self.config.retry_delay_multiplier
                    logger.warning(f"等待 {wait_time} 秒後再次繼續...")
                    time.sleep(wait_time)
                    tries += 1
                else:
                    logger.error("已達重試次數上限，跳過此筆資料")
                    return None
        return None

    def _save_current_chunk(self):
        """將目前累積的資料寫入 JSON 檔案"""
        now_time = datetime.now().strftime("%H:%M:%S")

        data = {
            "update_date": self.now_date,
            "update_time": now_time,
            "data": self.current_info_list
        }

        file_name = f"game_info_{self.output_file_num}.json"
        save_path = self.output_folder / file_name

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[{self.current_input_filename}] 第 {self.total_data_count} 筆資料儲存完畢！(File: {file_name})")

    def _check_and_rotate_output_file(self):
        """檢查是否達到輸出檔案上限"""
        if len(self.current_info_list) >= self.config.max_items_per_file:
            self.output_file_num += 1
            self.current_info_list.clear()

    def _process_input_file(self, input_file_path: Path):
        """處理單一個 Input ID 檔案"""
        self.current_input_filename = input_file_path.name
        logger.info(f"開始讀取 {self.current_input_filename} 資料...")

        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                game_list_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"無法讀取 JSON 檔案: {input_file_path}")
            return

        game_list = game_list_data.get("data", [])

        for game in game_list:
            app_id = game.get("appid")
            logger.info(
                f"[{self.current_input_filename}] 開始搜尋第 {self.total_data_count + 1} 筆資料 (AppID: {app_id})...")

            game_info = self._fetch_single_game(app_id)

            if game_info:
                # 成功取得資料
                self.current_info_list.append(game_info)
                self.last_appid = app_id
                self.total_data_count += 1

                # 依照原邏輯：每次成功抓取後立即存檔
                self._save_current_chunk()

                # 檢查是否需要換下一個輸出檔案
                self._check_and_rotate_output_file()

                time.sleep(self.config.request_delay)
            else:
                # 失敗處理
                self.failed_count += 1
                self.failed_list.append(app_id)

    def _save_metadata(self):
        """建立並儲存 Metadata"""
        end_time = datetime.now().strftime("%H:%M:%S")
        now_date_filename = datetime.now().strftime("%Y%m%d")

        metadata = {
            "update_date": self.now_date,
            "start_time": self.start_time,
            "end_time": end_time,
            "failed_count": self.failed_count,
            "failed_list": self.failed_list,
            "data_count": self.total_data_count,
            "last_appid": self.last_appid
        }

        metadata_file = f"{now_date_filename}_metadata_game_info.json"
        metadata_path = self.metadata_folder / metadata_file

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Metadata 已儲存至: {metadata_path}")

    def run(self):
        """執行爬蟲主程序"""
        while True:
            # --- 檢查終止機制 ---
            if self.config.max_input_files is not None:
                if self.input_file_num > self.config.max_input_files:
                    logger.info(
                        f"已達到自訂終止限制 (max_input_files: {self.config.max_input_files})，準備結束程式。")
                    break

            input_file_name = f"game_id_{self.input_file_num}.json"
            input_path = self.input_folder / input_file_name

            if not input_path.exists():
                logger.info(f"找不到輸入檔案 {input_file_name}，流程結束。")
                break

            self._process_input_file(input_path)
            self.input_file_num += 1

        self._save_metadata()


if __name__ == "__main__":
    # 初始化設定與爬蟲
    # 可以調整 max_items_per_file
    config = CrawlerConfig(
        max_items_per_file=2000,
        max_input_files=1  # 設定你想終止的數量
    )
    crawler = SteamGameInfoCrawler(config)

    # 開始執行
    crawler.run()
