import logging


def init_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    requests_logger = logging.getLogger("urllib3")
    requests_logger.setLevel(logging.DEBUG)
    requests_logger.propagate = True
