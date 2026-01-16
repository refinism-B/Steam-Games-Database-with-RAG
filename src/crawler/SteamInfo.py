import logging

from src.config.constant import GAME_INFO_URL
from src.utils.scraper_base import SteamScraperBase

logging.basicConfig(
    level=logging.INFO,  # 設定為 INFO，這樣 Base Class 裡的 logger.info 才會顯示
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


logging.info("收到指令，開始執行 Steam info 爬蟲...")
if __name__ == "__main__":
    info_scraper = SteamScraperBase(
        scraper_type="game_info", url_type=GAME_INFO_URL, max_input_files=2)
    info_scraper.id_file_num = 33
    info_scraper.output_file_num = 65
    info_scraper.run()
    logging.info("Steam Info 爬蟲執行完畢！")
