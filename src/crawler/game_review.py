import json
import time
from datetime import datetime
from pathlib import Path

import requests

from src.config.constant import (RAW_GAME_ID_SUBFOLDER,
                                 RAW_GAME_REVIEWS_SUBFOLDER,
                                 RAW_REVIEW_METADATA_SUBFOLDER)


# 取得根目錄路徑
root = Path(__file__).resolve().parents[2]

# game id路徑
id_sub_folder = RAW_GAME_ID_SUBFOLDER
id_folder = root / id_sub_folder

# review路徑
review_sub_folder = RAW_GAME_REVIEWS_SUBFOLDER
review_folder = root / review_sub_folder

# metadata路徑
metadata_sub_folder = RAW_REVIEW_METADATA_SUBFOLDER
metadata_folder = root / metadata_sub_folder

# 設定檔案起始編號
id_file_num = 1
review_file_num = 1

# 建立空的清單容器
review_list = []
data_count = 0
failed_list = []
failed_count = 0

# 設定單檔最大資料筆數
max_result = 2000
tries = 1
last_id = None

# 紀錄開始時間日期
now_date = datetime.now().strftime("%Y-%m-%d")
start_time = datetime.now().strftime("%H:%M:%S")


while True:
    id_file = f"game_id_{id_file_num}.json"
    id_path = id_folder / id_file

    if not id_path.exists():
        search_result = True
        break

    with open(id_path, 'r', encoding='utf-8') as f:
        game_list_data = json.load(f)

    print(f"開始讀取{id_file}資料...")
    game_list = game_list_data.get("data")

    for game in game_list:
        tries = 1
        print(f"[{id_file}]開始搜尋第{data_count+1}筆資料...")

        app_id = game.get("appid")
        url = f"https://store.steampowered.com/appreviews/{app_id}?json=1&language=all"

        while tries <= 5:
            try:
                res = requests.get(url)

                review_data = res.json()
                review_list.append(review_data)
                last_id = app_id

                now_time = datetime.now().strftime("%H:%M:%S")
                data = {
                    "update_date": now_date,
                    "update_time": now_time,
                    "data": review_list
                }

                review_file = f"game_review_{review_file_num}.json"
                info_save_path = review_folder / review_file

                with open(info_save_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                data_count += 1
                print(f"[{id_file}]第{data_count}筆資料儲存完畢！")
                time.sleep(2)

                if len(review_list) >= max_result:
                    review_file_num += 1
                    review_list.clear()

                break

            except Exception as e:
                print(f"資料爬取發生錯誤: {e}")
                if tries < 5:
                    print(f"等待{tries*10}秒後再次繼續...")
                    time.sleep(tries*10)
                    tries += 1
                    continue
                else:
                    print("已達重試次數上限，跳過此筆資料")
                    failed_count += 1
                    failed_list.append(app_id)
                    break

    id_file_num += 1


now_date_filename = datetime.now().strftime("%Y%m%d")
end_time = datetime.now().strftime("%H:%M:%S")

metadata = {
    "update_date": now_date,
    "start_time": start_time,
    "end_time": end_time,
    "failed_count": failed_count,
    "failed_list": failed_list,
    "data_count": data_count,
    "last_appid": last_id
}

metadata_folder = Path(
    r"C:\Users\add41\Documents\Data_Engineer\Project\Steam-Games-Database-with-RAG\data\raw\game_review\metadata")
metadata_file = f"{now_date_filename}_metadata_game_review.json"
metadata_path = metadata_folder / metadata_file

with open(metadata_path, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
