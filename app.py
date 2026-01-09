import os
import threading

from flask import Flask, jsonify

from src.crawler.SteamInfo import run_steam_info
from src.crawler.SteamReview import run_steam_review
from src.crawler.SteamTag import run_steam_tag

app = Flask(__name__)


@app.route('/')
def index():
    return "爬蟲調度系統運行中：可用路徑 /run/a 或 /run/b"


@app.route('/run/info')
def trigger_Info():
    # 使用 Thread 確保爬蟲在背景執行，不會阻塞網頁回應
    thread = threading.Thread(target=run_steam_info)
    thread.start()
    return jsonify({"status": "Success", "message": "SteamInfo 已在背景啟動"})


@app.route('/run/review')
def trigger_Review():
    thread = threading.Thread(target=run_steam_review)
    thread.start()
    return jsonify({"status": "Success", "message": "SteamReview 已在背景啟動"})


@app.route('/run/tag')
def trigger_Tag():
    thread = threading.Thread(target=run_steam_tag)
    thread.start()
    return jsonify({"status": "Success", "message": "SteamTag 已在背景啟動"})


if __name__ == "__main__":
    # Zeabur 會自動注入 PORT 環境變數，如果沒有則預設 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
