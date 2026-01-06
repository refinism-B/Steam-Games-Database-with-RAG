import json
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# 專案根目錄路徑
PROJECT_ROOT = Path(__file__).resolve().parents[2]

id_file_num = 1
id_sub_folder = r"data\raw\game_id"
id_folder = PROJECT_ROOT / id_sub_folder
info_file_num = 1
info_sub_folder = r"data\raw\game_info"
info_folder = PROJECT_ROOT / info_sub_folder


game_info_list = []
data_count = 0
failed_list = []
failed_count = 0

max_result = 10
tries = 1
last_id = None

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
        url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"

        while tries <= 5:
            try:
                res = requests.get(url)

                game_info = res.json()
                game_info_list.append(game_info)
                last_id = app_id

                now_time = datetime.now().strftime("%H:%M:%S")
                data = {
                    "update_date": now_date,
                    "update_time": now_time,
                    "data": game_info_list
                }

                info_file = f"game_info_{info_file_num}.json"
                info_save_path = info_folder / info_file

                with open(info_save_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                data_count += 1
                print(f"[{id_file}]第{data_count}筆資料儲存完畢！")
                time.sleep(3)

                if len(game_info_list) >= max_result:
                    info_file_num += 1
                    game_info_list.clear()

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

metadata_sub_folder = r"data\raw\game_id\metadata"
metadata_folder = PROJECT_ROOT / metadata_sub_folder
metadata_file = f"{now_date_filename}_metadata_game_info.json"
metadata_path = metadata_folder / metadata_file

with open(metadata_path, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
