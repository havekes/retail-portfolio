import logging


def init_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    requests_logger = logging.getLogger("urllib3")
    requests_logger.setLevel(logging.DEBUG)
    requests_logger.propagate = True
