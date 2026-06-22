import logging
from rich.logging import RichHandler

# Set up root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove any existing handlers
for handler in list(root_logger.handlers):
    root_logger.removeHandler(handler)

import os
os.makedirs("logs", exist_ok=True)

# File Handler: Clean ASCII logging for filesystem storage
file_handler = logging.FileHandler("logs/log.txt")
file_formatter = logging.Formatter(
    fmt="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

# Rich Console Handler: Gorgeous, high-tech, minimalist terminal output
console_handler = RichHandler(
    rich_tracebacks=True,
    markup=True,
    show_path=False,
    show_time=False,
    show_level=False,
)
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Mute noisy internal dependencies
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
