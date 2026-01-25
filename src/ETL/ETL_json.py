import json
import math
import traceback
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.config.constant import (INFO_MAIN_COLS, PROCESSED_DATA_PATH,
                                 PROJECT_ROOT, RAW_DATA_PATH, REVIEW_MAIN_COLS,
                                 TAG_MAIN_COLS)


def read_file(file_type: str, input_file_num: int):
    input_folder = PROJECT_ROOT / RAW_DATA_PATH.format(file_type)
    input_file = f"{file_type}_{input_file_num}.json"
    input_path = input_folder / input_file

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def clean_html_tag(raw_str: str):
    if raw_str is None:
        return ""
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


def flatten_hardware_requirement(data):
    hardware_list = ['pc_requirements',
                     'mac_requirements', 'linux_requirements']
    new_requirement_dict = {}

    for hardware in hardware_list:
        # 增加 isinstance(data[hardware], dict) 的檢查
        if hardware not in data or not isinstance(data[hardware], dict):
            # 如果不是字典（可能是 None 或 []），就設為 None 並跳過
            data[hardware] = None
            continue

        for spec in list(data[hardware].keys()):
            new_requirement_dict[f"{hardware}_{spec}"] = data[hardware][spec]

        data.pop(hardware, None)

    data.update(new_requirement_dict)
    return data


def clean_languages(languages_data):
    main_part = languages_data.split("<br>")[0]
    return main_part.strip()


def final_clean_nan(data):
    """
    遞迴清理資料，將所有 NaN 替換為 None，確保符合 JSON 規範。
    """
    if isinstance(data, dict):
        # 處理 Dictionary
        return {k: final_clean_nan(v) for k, v in data.items()}
    elif isinstance(data, list):
        # 處理 List
        return [final_clean_nan(item) for item in data]
    elif isinstance(data, float):
        # 核心檢查：處理真正的 NaN (math.isnan 只接受 float)
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, str):
        # 處理可能的字串型態 "nan" (雖然較少見，但預防萬一)
        if data.lower() == "nan":
            return None
        return data
    else:
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

    print(f"正在處理第 {input_file_num} 個檔案...")  # 增加進度提示

    # 讀取json檔
    try:
        info_data = read_file(file_type="game_info",
                              input_file_num=input_file_num)
        tag_data = read_file(file_type="game_tag",
                             input_file_num=input_file_num)
        review_data = read_file(file_type="game_review",
                                input_file_num=input_file_num)
    except Exception as e:
        print(f"讀取檔案 {input_file_num} 發生錯誤: {e}")
        input_file_num += 1
        continue

    # 取得data中的資料列表
    info_list = info_data.get("data", [])
    tag_list = tag_data.get("data", [])
    review_list = review_data.get("data", [])

    # 先轉換tag和review，添加app_id為key
    tag_lookup = {str(item['appid']): item for item in tag_list}
    review_lookup = {str(item['appid']): item for item in review_list}

    final_json_data = {}
    data_list = []

    # 開始迴圈逐筆資料處理
    for single_data in info_list:
        try:
            # 保留info資料需要的欄位
            key_list = list(single_data.keys())
            if not key_list:
                continue  # 防呆：空字典跳過

            appid = key_list[0]
            raw_game_info = single_data.get(appid).get("data", {})

            # 若 raw_game_info 為 None (有些 Steam API 回傳 success: false)，則跳過
            if not raw_game_info:
                continue

            new_game_info = {k: v for k,
                             v in raw_game_info.items() if k in INFO_MAIN_COLS}

            # 保留review資料需要的欄位 (使用 .get 避免 KeyError)
            raw_game_review = review_lookup.get(appid, {})
            new_game_review = {
                k: v for k, v in raw_game_review.items() if k in REVIEW_MAIN_COLS}

            # 保留tag資料需要的欄位 (使用 .get 避免 KeyError)
            raw_game_tag = tag_lookup.get(appid, {})
            new_game_tag = {k: v for k,
                            v in raw_game_tag.items() if k in TAG_MAIN_COLS}

            # 三類資料合併
            new_game_info.update(new_game_review)
            new_game_info.update(new_game_tag)
            new_game_info.pop("appid", None)

            """
            進行描述型欄位處理
            """
            new_game_info["supported_languages"] = clean_languages(
                new_game_info.get("supported_languages", ""))

            # 處理'detailed_description', 'about_the_game', 'short_description'
            descriptive_col = ['detailed_description', 'about_the_game',
                               'short_description', 'supported_languages']
            new_game_info = batch_clean_html(
                data=new_game_info, col_list=descriptive_col)

            # 處理hardware_requirements
            new_game_info = clean_hardware_requirement(data=new_game_info)
            new_game_info = flatten_hardware_requirement(data=new_game_info)

            """
            進行數值與類別型欄位處理
            """
            # 處理category
            new_category_list = []
            if new_game_info.get("categories"):  # 檢查是否存在且不為 None
                for category in new_game_info["categories"]:
                    new_category_list.append(category.get("description", ""))
            new_game_info["categories"] = new_category_list

            # 處理tags (增加安全檢查)
            new_tag_list = []
            if new_game_info.get("tags") and isinstance(new_game_info["tags"], dict):
                n = 0
                for tag in new_game_info["tags"]:
                    new_tag_list.append(tag)
                    n += 1
                    if n >= 15:
                        break
            new_game_info["tags"] = new_tag_list

            # 處理genres
            new_genres_list = []
            if new_game_info.get("genres"):
                for genres in new_game_info["genres"]:
                    new_genres_list.append(genres.get("description", ""))
            new_game_info["genres"] = new_genres_list

            # 處理price_overview (增加 None 檢查)
            price_cols = ['currency', 'initial']
            price = new_game_info.get("price_overview")
            if price:
                price = {k: v for k, v in price.items() if k in price_cols}
                # 確保 initial 存在且為數字
                if 'initial' in price and price['initial'] is not None:
                    try:
                        price['initial'] = float(price['initial']) / 100
                    except (ValueError, TypeError):
                        price['initial'] = 0.0

                price["price_initial"] = price.pop("initial", None)
                price["price_currency"] = price.pop("currency", None)

                new_game_info.update(price)
                new_game_info.pop("price_overview", None)
            else:
                new_game_info["price_overview"] = None

            # 處理platforms
            platform_list = []
            platforms = new_game_info.get('platforms', {})
            if platforms:
                for platform, is_supported in platforms.items():
                    if is_supported is True:
                        platform_list.append(platform)
            new_game_info['platforms'] = ", ".join(platform_list)

            # 處理metacritic (增加檢查)
            if 'metacritic' in new_game_info and new_game_info['metacritic']:
                new_game_info['metacritic_score'] = new_game_info['metacritic'].get(
                    'score')
            else:
                new_game_info['metacritic_score'] = None
            new_game_info.pop('metacritic', None)

            # 處理language
            new_languages = new_game_info.get("supported_languages", [])
            if type(new_languages) == str:
                new_languages = new_languages.replace(
                    "languages with full audio support", "")
                new_languages = new_languages.split(", ")
                new_languages = [item.strip()
                                 for item in new_languages if type(item) == str]
                new_game_info["languages"] = new_languages
                new_game_info.pop("supported_languages", None)
            else:
                new_game_info["supported_languages"] = []
                print(f"第{info_list.index(single_data)}筆資料無語言資訊")

            # 處理release_date (增加格式錯誤處理)
            release_info = new_game_info.get('release_date', {})
            # 預設值
            new_release_date = {
                "release_date": None,
                "release_date_timestamp": None,
                "release_date_year": None,
                "release_date_month": None,
            }

            if release_info.get("coming_soon"):
                new_game_info['release_date'] = "coming_soon"
            else:
                release_date_str = release_info.get("date", "")
                if release_date_str:
                    try:
                        release_date_obj = datetime.strptime(
                            release_date_str, '%d %b, %Y')
                        new_release_date.update({
                            "release_date": release_date_obj.strftime('%Y-%m-%d'),
                            "release_date_timestamp": int(release_date_obj.timestamp()),
                            "release_date_year": release_date_obj.year,
                            "release_date_month": release_date_obj.month,
                        })
                    except ValueError:
                        # 遇到無法解析的日期格式 (如 "Oct 2020")，保留原始字串或設為 None
                        pass
                new_game_info.pop("release_date", None)
                new_game_info.update(new_release_date)

            # 處理query_summary（review）
            # 需先檢查是否拿到 query_summary，若無則給預設字典
            review_overview = new_game_info.get("query_summary", {})
            review_overview.pop('num_reviews', None)
            review_overview.pop('review_score', None)

            total = review_overview.get('total_reviews', 0)
            # 確保 total 是數字
            if not isinstance(total, (int, float)):
                total = 0

            pos = review_overview.get('total_positive', 0)
            if not isinstance(pos, (int, float)):
                pos = 0

            positive_rate = round(pos / total, 4) if total > 0 else 0.0
            review_overview["positive_rate"] = positive_rate
            review_overview["rate_percentage"] = f"{positive_rate:.1%}"

            new_game_info.update(review_overview)
            # new_game_info["review"] = review_overview
            new_game_info.pop("query_summary", None)

            """最後清理NaN"""
            new_game_info = final_clean_nan(new_game_info)

            # 加入列表
            data_list.append(new_game_info)

        except Exception as e:
            # 捕捉單筆資料處理失敗，印出錯誤但不中斷整個迴圈
            print(
                f"處理第 {info_list.index(single_data)} 筆資料時時發生錯誤: {e}")
            traceback.print_exc()  # 如果需要詳細錯誤訊息可以取消註解
            continue

    """
    儲存處理完的檔案 (移出迴圈外)
    """
    if data_list:  # 確保有資料才寫入
        update_date = datetime.now().strftime("%Y-%m-%d")
        update_time = datetime.now().strftime("%H:%M:%S")

        final_json_data["update_date"] = update_date
        final_json_data["update_time"] = update_time
        final_json_data["data"] = data_list

        json_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("json_data")
        # 確保目標資料夾存在
        json_folder.mkdir(parents=True, exist_ok=True)

        json_file_name = f"json_data_{input_file_num}.json"
        save_path = json_folder / json_file_name

        print(f"正在寫入檔案: {save_path}")
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(final_json_data, f, ensure_ascii=False, indent=2)
    else:
        print(f"檔案 {input_file_num} 無有效資料，跳過寫入。")

    input_file_num += 1
