import json
import logging
from pathlib import Path

# 假設這些常數已在 src.config.constant 定義
from src.config.constant import CONTEXT_COLS, METADATA_COLS, PROCESSED_DATA_PATH, PROJECT_ROOT

# 設定簡單的日誌記錄 (保險機制：記錄錯誤但不中斷程式)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def read_file(input_path: Path):
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logging.error(f"讀取檔案 {input_path} 時發生錯誤: {e}")
        return None


input_file_num = 1

# [新加入] 確保儲存資料夾存在
save_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("document")
save_folder.mkdir(parents=True, exist_ok=True)

while True:
    input_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("json_data")
    input_file = f"json_data_{input_file_num}.json"
    input_path = input_folder / input_file

    if not input_path.exists():
        print(f"已處理完所有檔案！(共處理 {input_file_num - 1} 個檔案)")
        break

    print(f"正在處理第 {input_file_num} 個檔案...")

    # 讀取json資料
    json_data = read_file(input_path=input_path)

    # [新加入] 防呆：檢查資料內容是否有效
    if json_data is None or not isinstance(json_data.get("data"), list):
        logging.warning(f"檔案 {input_file} 格式不正確，跳過此檔案。")
        input_file_num += 1
        continue

    document_list = []
    json_data_list = json_data.get("data")

    for single_data in json_data_list:
        # 將硬體需求欄位名加入metadata欄位列表
        key_list = list(single_data.keys())
        requirement_keys = [key for key in key_list if "requirements" in key]
        new_metadata_cols = METADATA_COLS + requirement_keys

        doc_data = {
            "context": "",
            "metadata": {}
        }

        # 處理 Metadata
        for col in new_metadata_cols:
            doc_data["metadata"][col] = single_data.get(col, None)

        # 處理 Context (組合文字資訊)
        for col in CONTEXT_COLS:
            # [新加入] 防呆：避免 col 不存在時產生的 NoneType 錯誤
            val = single_data.get(col, "N/A")
            doc_data["context"] += f"{col}: {val}\n"

        document_list.append(doc_data)

    # 儲存處理完的檔案
    file_name = f"document_{input_file_num}.json"
    save_path = save_folder / file_name

    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(document_list, f, ensure_ascii=False, indent=2)
        print(f"已成功儲存 {file_name} 資料！")
    except Exception as e:
        logging.error(f"儲存 {file_name} 時發生意外: {e}")

    # [關鍵修正] 增加計數器，避免無限迴圈
    input_file_num += 1

print("--- ETL 轉換任務結束 ---")
