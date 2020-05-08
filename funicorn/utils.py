import time
import multiprocessing
import threading
import psutil
import logging
import cv2
import numpy as np
# cvt_status = lambda is_alive: 'alive' if is_alive == 'running' else 'dead'


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


def get_logger(name='logger', mode='debug'):
    logger = logging.getLogger(name)
    # https://stackoverflow.com/questions/17745914/python-logging-module-is-printing-lines-multiple-times
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(filename)s-%(funcName)s-%(lineno)04d | %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if mode == 'debug' else logging.INFO)
    return logger
