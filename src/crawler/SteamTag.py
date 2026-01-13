import logging

from src.config.constant import GAME_TAG_URL
from src.utils.scraper_base import SteamScraperBase

logging.basicConfig(
    level=logging.INFO,  # 設定為 INFO，這樣 Base Class 裡的 logger.info 才會顯示
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def run_steam_tag():
    logging.info("收到指令，開始執行 Steam tag 爬蟲...")
    if __name__ == "__main__":
        tag_scraper = SteamScraperBase(
            scraper_type="game_tag", url_type=GAME_TAG_URL)
        tag_scraper.run()
    logging.info("Steam tag 爬蟲執行完畢！")
