from logging import Formatter
from copy import copy
from termcolor import colored
from inspect import formatargspec, getfullargspec
import uuid
import time
import multiprocessing
import threading
import psutil
import logging
import cv2
import numpy as np

#--------------------- Image Encode/Decode ---------------------#

def img_bytes_to_img_arr(img_bytes):
    img_flatten = np.frombuffer(img_bytes, dtype=np.uint8)
    img_arr_decoded = cv2.imdecode(img_flatten, cv2.IMREAD_ANYCOLOR)
    return img_arr_decoded


def check_tree_status(parent_pid, including_parent=True):
    status = {}
    parent = psutil.Process(parent_pid)
    for idx, child in enumerate(parent.children(recursive=True)):
        status[f'child-{idx}'] = {'pid': child.pid, 'status': child.status()}
    if including_parent:
        status['parent'] = {'pid': parent.pid, 'status': parent.status()}
    return status


def check_all_ps_status(list_pid):
    status = {}
    for pid in list_pid:
        status[pid] = check_ps_status(pid)
    return status


def check_ps_status(pid):
    ps = psutil.Process(pid)
    return ps.status()

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

def coloring_worker_name(worker_name):
    return colored(worker_name, 'green', attrs=['bold'])

def coloring_funicorn_name():
    return colored('FUNICORN', 'cyan', attrs=['bold'])

def coloring_network_name(network_name):
    return colored(network_name, 'blue', attrs=['bold'])


#--------------------- CLI ---------------------#
def get_args_from_class(cls):
    init_cls_args = getfullargspec(cls)
    init_cls_args.args.remove('self')
    return init_cls_args.args
