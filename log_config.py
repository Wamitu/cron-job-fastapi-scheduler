# log_config.py
import logging
import sys
from loguru import logger
import structlog

logger.remove()

logger.add(
    "logs/{time:YYYY}/week_{time:WW}/system_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    compression="zip",
    serialize=True,
)
logger.add(sys.stdout, format="{time} {level} {message}", level="INFO")

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)

app_logger = structlog.get_logger()
