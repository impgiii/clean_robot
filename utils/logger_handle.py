import logging
from logging.handlers import RotatingFileHandler
from utils.path_tool import get_abs_path

logger = logging.getLogger("clean_robot")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    log_dir = get_abs_path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    #输出到文件保存，单个文件最多5mb，3个备份
    file_handler = RotatingFileHandler(
        log_dir/"app.log",
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
