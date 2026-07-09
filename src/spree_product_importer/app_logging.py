import logging
import sys


logger = logging.getLogger("spree_product_importer")
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
    )
    logger.addHandler(stream_handler)
