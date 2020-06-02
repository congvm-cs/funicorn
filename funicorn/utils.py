from termcolor import colored
from inspect import getfullargspec
import uuid
import time
import psutil
import cv2
import numpy as np
import sys
import importlib
import os
from PIL import Image
from io import BytesIO, StringIO

#--------------------- Image Encode/Decode ---------------------#


def img_bytes_to_img_arr(img_bytes):
    '''Convert image bytes to image array'''
    img_flatten = np.frombuffer(img_bytes, dtype=np.uint8)
    img_arr_decoded = cv2.imdecode(img_flatten, cv2.IMREAD_ANYCOLOR)
    return img_arr_decoded


def img_arr_to_img_bytes(img_arr, quality=100):
    '''Convert image array to image bytes'''
    ret, img_flatten = cv2.imencode('.jpg', img_arr, params=[
                                    cv2.IMWRITE_JPEG_QUALITY, quality])
    img_bytes = img_flatten.tobytes()
    return img_bytes


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


def colored_worker_name(worker_name):
    return colored(worker_name, 'green', attrs=['bold'])


def colored_funicorn_name(funicorn_app_name='FUNICORN'):
    return colored(funicorn_app_name, 'cyan', attrs=['bold'])


def colored_network_name(network_name):
    return colored(network_name, 'magenta', attrs=['bold'])


#--------------------- CLI ---------------------#
def get_args_from_class(cls):
    init_cls_args = getfullargspec(cls)
    init_cls_args.args.remove('self')
    return init_cls_args.args


def split_class_from_path(path):
    # Append current working directory to search module
    sys.path.append(os.getcwd())
    subpaths = path.split('.')
    if len(subpaths) > 2:
        pkg, cls_name = subpaths[-2:]
    else:
        pkg, cls_name = subpaths
    cls_name = getattr(importlib.import_module(pkg), cls_name)
    return pkg, cls_name


#------------------- OTHERS ------------------#
def get_size(obj, seen=None):
    """Recursively finds size of objects"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([get_size(i, seen) for i in obj])
    return size
