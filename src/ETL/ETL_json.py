import json
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.config.constant import (INFO_MAIN_COLS, PROJECT_ROOT, RAW_DATA_PATH,
                                 REVIEW_MAIN_COLS, TAG_MAIN_COLS, PROCESSED_DATA_PATH)


def read_file(file_type: str, input_file_num: int):
    input_folder = PROJECT_ROOT / RAW_DATA_PATH.format(file_type)
    input_file = f"{file_type}_{input_file_num}.json"
    input_path = input_folder / input_file

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def clean_html_tag(raw_str: str):
    soup = BeautifulSoup(raw_str, "html.parser")
    return soup.get_text(separator=" ").strip()


def batch_clean_html(data: dict, col_list: list[str]):
    for col in col_list:
        data[col] = clean_html_tag(raw_str=data.get(col, None))
        data[col] = " ".join(data[col].split())
        data[col] = data[col].replace("*", "").replace(" , ", ", ").strip()
    return data


def clean_hardware_requirement(data):
    hardware_list = ['pc_requirements',
                     'mac_requirements', 'linux_requirements']
    for hardware in hardware_list:
        if hardware not in data or data[hardware] is None:
            data[hardware] = None
            continue

        req_data = data[hardware]
        if isinstance(req_data, dict):
            for req_key, raw_value in req_data.items():
                req_data[req_key] = clean_html_tag(raw_str=raw_value)
                req_data[req_key] = " ".join(req_data[req_key].split())
                req_data[req_key] = req_data[req_key].replace(
                    "*", "").replace(" , ", ", ").strip()
    return data


"""
讀取檔案，並將三類資料合併
"""
# 設定起始檔案序號
input_file_num = 1

while True:
    input_folder = PROJECT_ROOT / RAW_DATA_PATH.format("game_info")
    input_file = f"game_info_{input_file_num}.json"
    input_path = input_folder / input_file

    if not Path(input_path).exists():
        print("已處理完所有檔案！")
        break

    # 讀取json檔
    info_data = read_file(file_type="game_info", input_file_num=input_file_num)
    tag_data = read_file(file_type="game_tag", input_file_num=input_file_num)
    review_data = read_file(file_type="game_review",
                            input_file_num=input_file_num)

    # 取得data中的資料列表
    info_list = info_data.get("data")
    tag_list = tag_data.get("data")
    review_list = review_data.get("data")

    # 先轉換tag和review，添加app_id為key
    tag_lookup = {str(item['appid']): item for item in tag_list}
    review_lookup = {str(item['appid']): item for item in review_list}

    final_json_data = {}
    data_list = []

    # 開始迴圈逐筆資料處理
    for single_data in info_list:
        # 保留info資料需要的欄位
        key_list = list(single_data.keys())
        raw_game_info = single_data.get(key_list[0]).get("data")
        new_game_info = {k: v for k,
                         v in raw_game_info.items() if k in INFO_MAIN_COLS}

        # 保留review資料需要的欄位
        raw_game_review = review_lookup[key_list[0]]
        new_game_review = {k: v for k, v in raw_game_review .items()
                           if k in REVIEW_MAIN_COLS}

        # 保留tag資料需要的欄位
        raw_game_tag = tag_lookup[key_list[0]]
        new_game_tag = {k: v for k, v in raw_game_tag .items()
                        if k in TAG_MAIN_COLS}

        # 三類資料合併
        new_game_info.update(new_game_review)
        new_game_info.update(new_game_tag)
        new_game_info.pop("appid", None)

        """
        進行數值與類別型欄位處理
        """
        # 處理category
        new_category_list = []
        for category in new_game_info["categories"]:
            new_category_list.append(category.get("description"))

        new_game_info["categories"] = ", ".join(new_category_list)

        # 處理tags
        new_tag_list = []
        n = 0
        for tag in new_game_info["tags"]:
            new_tag_list.append(tag)
            n += 1

            if n >= 15:
                break
        new_game_info["tags"] = ", ".join(new_tag_list)

        # 處理genres
        new_genres_list = []
        for genres in new_game_info["genres"]:
            new_genres_list.append(genres.get("description"))
        new_game_info["genres"] = ", ".join(new_genres_list)

        # 處理developers和publishers
        new_game_info["developers"] = ", ".join(new_game_info["developers"])
        new_game_info["publishers"] = ", ".join(new_game_info["publishers"])

        # 處理price_overview
        price_cols = ['currency', 'initial']
        price = new_game_info["price_overview"]
        price = {k: v for k, v in price.items() if k in price_cols}
        price['initial'] = float(price['initial']) / 100
        new_game_info["price_overview"] = price

        # 處理platforms
        platform_list = []
        for platform in new_game_info['platforms']:
            if new_game_info['platforms'][platform] is True:
                platform_list.append(platform)
        new_game_info['platforms'] = ", ".join(platform_list)

        # 處理metacritic
        new_game_info['metacritic_score'] = new_game_info['metacritic']['score']
        new_game_info.pop('metacritic', None)
        new_game_info['metacritic_score']

        # 處理release_date
        if new_game_info['release_date'].get("coming_soon"):
            new_game_info['release_date'] = "coming_soon"
        else:
            release_date_str = new_game_info['release_date'].get("date")
            release_date_obj = datetime.strptime(release_date_str, '%d %b, %Y')
            release_date_iso = release_date_obj.strftime('%Y-%m-%d')
            release_date_timestamp = int(release_date_obj.timestamp())
            new_release_date = {
                "release_date": release_date_iso,
                "release_date_timestamp": release_date_timestamp,
                "release_date_year": release_date_obj.year,
                "release_date_month": release_date_obj.month,
            }
            new_game_info['release_date'] = new_release_date

        # 處理query_summary（review）
        review_overview = new_game_info["query_summary"]
        review_overview.pop('num_reviews', None)
        review_overview.pop('review_score', None)

        total = review_overview.get('total_reviews', 0)
        pos = review_overview.get('total_positive', 0)
        positive_rate = round(pos / total, 4) if total > 0 else 0.0
        review_overview["positive_rate"] = positive_rate
        review_overview["rate_percentage"] = f"{positive_rate:.1%}"

        new_game_info["review"] = review_overview
        new_game_info.pop("query_summary", None)

        """
        進行描述型欄位處理
        """
        # 處理'detailed_description', 'about_the_game', 'short_description', 'supported_languages'
        descriptive_col = ['detailed_description', 'about_the_game',
                           'short_description', 'supported_languages']
        new_game_info = batch_clean_html(
            data=new_game_info, col_list=descriptive_col)

        # 處理hardware_requirements
        new_game_info = clean_hardware_requirement(data=new_game_info)

        """
        儲存處理完的檔案
        """
        update_date = datetime.now().strftime("%Y-%m-%d")
        update_time = datetime.now().strftime("%H:%M:%S")
        data_list.append(new_game_info)

        final_json_data["update_date"] = update_date
        final_json_data["update_time"] = update_time
        final_json_data["data"] = data_list

        json_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("json")
        json_file_name = f"json_data_{input_file_num}.json"
        save_path = json_folder / json_file_name

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(final_json_data, f, ensure_ascii=False, indent=2)

    input_file_num += 1
