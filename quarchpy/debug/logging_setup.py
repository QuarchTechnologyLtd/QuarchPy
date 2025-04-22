import logging


# -------------------------------------
#  Logging Utilities
# -------------------------------------
def setup_logger(name, log_file, level=logging.INFO):
    """Set up a logger for different modules."""
    logger = logging.getLogger(name)
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
