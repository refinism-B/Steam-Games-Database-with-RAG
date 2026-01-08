import json
from pathlib import Path

from src.config.constant import CONTEXT_COLS, METADATA_COLS, PROCESSED_DATA_PATH, PROJECT_ROOT


def read_file(input_path: Path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


input_file_num = 1

while True:
    input_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("json_data")
    input_file = f"json_data_{input_file_num}.json"
    input_path = input_folder / input_file

    if not Path(input_path).exists():
        print("已處理完所有檔案！")
        break

    print(f"正在處理第 {input_file_num} 個檔案...")  # 增加進度提示

    document_list = []
    # 讀取json資料
    json_data = read_file(input_path=input_path)
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

        for col in new_metadata_cols:
            doc_data["metadata"][col] = single_data.get(col, None)

        for col in CONTEXT_COLS:
            doc_data["context"] += f"{col}: {single_data.get(col, None)}\n"

        document_list.append(doc_data)

    # 儲存處理完的檔案 (移出迴圈外)
    save_folder = PROJECT_ROOT / PROCESSED_DATA_PATH.format("document")
    file_name = f"document_{input_file_num}.json"
    save_path = save_folder / file_name

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(document_list, f, ensure_ascii=False, indent=2)

    print(f"已儲存{file_name}資料！")
