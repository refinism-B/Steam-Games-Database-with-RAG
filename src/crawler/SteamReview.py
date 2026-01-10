import logging

from src.config.constant import GAME_REVIEW_URL
from src.utils.scraper_base import SteamScraperBase

logging.basicConfig(
    level=logging.INFO,  # 設定為 INFO，這樣 Base Class 裡的 logger.info 才會顯示
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def run_steam_review():
    logging.info("收到指令，開始執行 Steam review 爬蟲...")
    # if __name__ == "__main__":
    review_scraper = SteamScraperBase(
        scraper_type="game_review", url_type=GAME_REVIEW_URL)
    # review_scraper.id_file_num = 2
    # review_scraper.output_file_num = 3
    review_scraper.run()
    logging.info("Steam review 爬蟲執行完畢！")
