import logging
import uuid
from logging import Formatter
import os

#--------------------- Logger ---------------------#

MAPPING = {
    'DEBUG': 37,  # white
    'INFO': 36,  # cyan
    'WARNING': 33,  # yellow
    'ERROR': 31,  # red
    'CRITICAL': 41,  # white on red bg
}

PREFIX = '\033['
SUFFIX = '\033[0m'


class ColoredFormatter(Formatter):
    def __init__(self, patern):
        Formatter.__init__(self, patern)

    def format(self, record):
        levelname = record.levelname
        seq = MAPPING.get(levelname, 37)  # default white
        colored_levelname = ('{0}{1}m{2}{3}').format(
            PREFIX, seq, levelname, SUFFIX)
        record.levelname = colored_levelname
        return Formatter.format(self, record)


def get_logger(name=f'logger-{str(uuid.uuid4())}', mode='debug'):
    logger = logging.getLogger(name)
    # https://stackoverflow.com/questions/17745914/python-logging-module-is-printing-lines-multiple-times
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if mode == 'debug' else logging.INFO)
    return logger


def get_fstream_logger(file_path, name=f'{str(uuid.uuid4())}', mode='debug'):
    name = 'fstream_logger-{}'.format(name)
    logger = logging.getLogger(name)
    # https://stackoverflow.com/questions/17745914/python-logging-module-is-printing-lines-multiple-times
    if not logger.hasHandlers():
        handler = logging.FileHandler(file_path)
        formatter = Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if mode == 'debug' else logging.INFO)
    return logger


class Logger():
    def __init__(self, log_dir, log_prefix):
        error_file_path = os.path.join(log_dir, log_prefix + '.error')
        info_file_path = os.path.join(log_dir, log_prefix + '.info')
        self.error_logger = get_fstream_logger(
            error_file_path, name=log_prefix + '.error')
        self.info_logger = get_fstream_logger(
            info_file_path, name=log_prefix + '.info')

    def info(self, msg):
        self.info_logger.info(msg)

    def error(self, msg):
        self.error_logger.info(msg)
