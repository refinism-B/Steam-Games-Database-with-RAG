import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# 專案根目錄路徑
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 設定搜尋參數
api_key = os.environ.get("STEAM_API_KEY")
url = f"https://api.steampowered.com/IStoreService/GetAppList/v1/"
now_date = datetime.now().strftime("%Y-%m-%d")
max_result = 100
max_save = 3000
last_id = 0
search_result = None

# 設定追蹤或存取值
game_list = []
start_time = datetime.now().strftime("%H:%M:%S")
search_times = 0
file_num = 1
tries = 1
sub_folder = r"data\raw\game_id"
folder = PROJECT_ROOT / sub_folder

# 開始迴圈爬取資料
while True:
    params = {
        'key': api_key,
        'include_games': 'true',     # 包含遊戲
        'include_dlc': 'false',      # 排除 DLC
        'include_software': 'false',  # 排除軟體
        'include_videos': 'false',   # 排除影片
        'max_results': max_result,
        'last_appid': last_id
    }

    try:
        # 訪問 API 取得資料
        print(f"開始第{search_times+1}次資料搜尋...")
        res = requests.get(url, params=params)
        result_list = res.json()

        # 將資料存入 result_list，查詢次數+1
        game_list.extend(result_list.get("response").get("apps"))
        last_id = result_list.get("response").get("last_appid")
        more_results = result_list.get("response").get("have_more_results")

        # 加入日期時間資訊
        now_time = datetime.now().strftime("%H:%M:%S")
        data = {
            "update_date": now_date,
            "update_time": now_time,
            "data": game_list
        }

        # 進行存檔
        file = f"game_id_{file_num}.json"
        save_path = folder / file

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        search_times += 1
        tries = 1
        print(f"第{search_times}次搜尋資料儲存完畢！")
        time.sleep(3)

        # 如果 game_list 資料筆數超過設定值，則將存檔編號+1
        # 將 game_list 清空再次循環
        if len(game_list) >= max_save:
            file_num += 1
            game_list.clear()

        if not more_results:
            search_result = True
            break

    except Exception as e:
        print(f"資料爬取發生錯誤: {e}")
        if tries < 5:
            print(f"等待{tries*10}秒後再次繼續...")
            time.sleep(tries*10)
            tries += 1
            continue
        else:
            print("已達重試次數上限，終止程式")
            search_result = False
            break


# 資料抓取完畢，建立 metadata
now_date_filename = datetime.now().strftime("%Y%m%d")
end_time = datetime.now().strftime("%H:%M:%S")

metadata = {
    "update_date": now_date,
    "start_time": start_time,
    "end_time": end_time,
    "search_result": search_result,
    "max_result": max_result,
    "search_times": search_times,
    "data_count": max_result * search_times,
    "last_appid": last_id
}

# 以日期命名並存檔 metadata
metadata_sub_folder = r"data\raw\game_id\metadata"
metadata_folder = PROJECT_ROOT / metadata_sub_folder
metadata_file = f"{now_date_filename}_metadata_game_id.json"
metadata_path = metadata_folder / metadata_file

with open(metadata_path, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
