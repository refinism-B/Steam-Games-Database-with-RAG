import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

# 假設 constant 都在這裡，若無則需要確認路徑
try:
    from src.config.constant import RAW_DATA_PATH, RAW_METADATA_PATH, PROJECT_ROOT
except ImportError:
    # 提供預設值以防單檔測試時報錯
    RAW_DATA_PATH = "data/raw/{}"
    RAW_METADATA_PATH = "data/metadata/{}"
    PROJECT_ROOT = Path(__file__).resolve().parents[2]


logger = logging.getLogger(__name__)


class SteamScraperBase:
    """
    Steam 通用爬蟲基底類別
    負責讀取遊戲 ID，根據傳入的 URL 模板訪問 Steam API 並儲存資料。
    """

    def __init__(self, scraper_type: str, url_type: str, max_input_files: Optional[int] = None):
        """
        初始化爬蟲
        :param scraper_type: 爬蟲類型 (用於資料夾命名，如 'game_review', 'game_tag')
        :param url_type: API URL 模板 (需包含 {} 以供 format 使用)
        :param max_input_files: 指定要爬取幾個 Input ID 檔案 (預設為 None，代表爬完所有檔案)
        """
        self.root = PROJECT_ROOT
        self.scraper_type = scraper_type
        self.url_type = url_type
        self.max_input_files = max_input_files  # 新增參數儲存
        self._init_paths()

        # 設定參數
        self.max_results_per_file = 2000
        self.max_retries = 5
        self.retry_delay_base = 15
        self.max_data_per_save = 200

        # 執行狀態追蹤
        self.id_file_num = 1
        self.output_file_num = 1
        self.data_count = 0
        self.failed_list: List[int] = []
        self.failed_count = 0
        self.last_appid: Optional[int] = None

        # 暫存容器
        self.current_data_list: List[Dict] = []

        # 時間記錄
        self.start_time = datetime.now().strftime("%H:%M:%S")
        self.now_date = datetime.now().strftime("%Y-%m-%d")

    def _init_paths(self):
        """初始化並建立必要的資料夾路徑"""
        # 注意：這裡依賴 constant 中的 formatting string
        self.id_folder = self.root / RAW_DATA_PATH.format("game_id")
        self.data_folder = self.root / RAW_DATA_PATH.format(self.scraper_type)
        self.metadata_folder = self.root / \
            RAW_METADATA_PATH.format(self.scraper_type)

        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.metadata_folder.mkdir(parents=True, exist_ok=True)

    def _fetch_single_data(self, app_id: int) -> Optional[Dict]:
        """
        對單一 AppID 執行 API 請求
        """
        # 使用初始化的 url_template
        url = self.url_type.format(app_id)
        tries = 1

        while tries <= self.max_retries:
            try:
                # 建議加入 headers 模擬瀏覽器，降低被擋機率 (Optional but recommended)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                res = requests.get(url, headers=headers, timeout=10)

                # 特定 API 可能回傳 200 但內容是 null，需視情況處理
                if res.status_code != 200:
                    logger.warning(f"AppID {app_id} 回傳狀態碼: {res.status_code}")

                # 這裡假設回傳的一定是 JSON
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
        """儲存目前的資料列表到 JSON 檔案"""
        now_time = datetime.now().strftime("%H:%M:%S")
        data_structure = {
            "update_date": self.now_date,
            "update_time": now_time,
            "data": self.current_data_list
        }

        filename = f"{self.scraper_type}_{self.output_file_num}.json"
        save_path = self.data_folder / filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data_structure, f, ensure_ascii=False, indent=2)

        logger.info(
            f"資料已更新至: {filename} (目前累積 {len(self.current_data_list)} 筆)")

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

        filename = f"{now_date_filename}_metadata_{self.scraper_type}.json"
        save_path = self.metadata_folder / filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Metadata 已儲存至: {save_path}")

    def run(self):
        """執行爬蟲的主流程"""
        logger.info(f"啟動 {self.scraper_type} 爬蟲...")

        # 新增變數：記錄目前已處理了幾個檔案
        files_processed_count = 0

        while True:
            # 新增邏輯：檢查是否已達到指定的 input 檔案數量上限
            if self.max_input_files is not None and files_processed_count >= self.max_input_files:
                logger.info(
                    f"已達到設定的讀取檔案數量上限 ({self.max_input_files} 個檔案)，停止爬蟲。")
                break

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

                # 呼叫 API 抓取
                single_data = self._fetch_single_data(app_id)

                # 先檢查是否抓取成功，再進行字典操作
                if single_data:
                    # 有些 API 回傳是 List 而非 Dict (如 Tag)，需做防呆
                    if isinstance(single_data, dict):
                        single_data["appid"] = app_id
                    elif isinstance(single_data, list):
                        # 如果 API 回傳 list，將其包裝成 dict 以便加入 appid
                        single_data = {"appid": app_id, "results": single_data}

                    self.current_data_list.append(single_data)
                    self.last_appid = app_id
                    self.data_count += 1

                    if self.data_count % self.max_data_per_save == 0:
                        self._save_batch_data()

                    if len(self.current_data_list) >= self.max_results_per_file:
                        logger.info(
                            f"單檔達到 {self.max_results_per_file} 筆上限，切換至新檔案。")
                        self.output_file_num += 1
                        self.current_data_list.clear()

                    time.sleep(2)
                else:
                    self.failed_count += 1
                    self.failed_list.append(app_id)

            # 檔案處理完畢，計數器 +1
            files_processed_count += 1
            self.id_file_num += 1

        self._save_metadata()
        logger.info("爬蟲任務全部完成！")
