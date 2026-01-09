import logging

from src.config.constant import GAME_REVIEW_URL
from src.utils.scraper_base import SteamScraperBase

logging.basicConfig(
    level=logging.INFO,  # 設定為 INFO，這樣 Base Class 裡的 logger.info 才會顯示
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

if __name__ == "__main__":
    review_scraper = SteamScraperBase(
        scraper_type="game_review", url_type=GAME_REVIEW_URL, max_input_files=1)
    # review_scraper.id_file_num = 2
    # review_scraper.output_file_num = 3
    review_scraper.run()
