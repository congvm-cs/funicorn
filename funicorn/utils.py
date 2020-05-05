import time
import multiprocessing
import threading
import psutil

# cvt_status = lambda is_alive: 'alive' if is_alive == 'running' else 'dead'

# def check_ps_status(parent_pid, including_parent=True):
#     status = {}
#     parent = psutil.Process(parent_pid)
#     for idx, child in enumerate(parent.children(recursive=True)):
#         status[f'child-{idx}'] = {'pid': child.pid, 'status': child.status()}
#     if including_parent:
#         status['parent'] = {'pid': parent.pid, 'status': parent.status()}
#     return status


def check_all_ps_status(list_pid):
    status = {}
    for pid in list_pid:
        status[pid] = check_ps_status(pid)
    return status


def check_ps_status(pid):
    ps = psutil.Process(pid)
    return ps.status()


def get_logger(name='logger', mode='debug'):
    import logging
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(filename)s-%(funcName)s-%(lineno)04d | %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if mode == 'debug' else logging.INFO)
    return logger


if __name__ == '__main__':
    def run():
        logger = get_logger('worker-1', mode='debug')
        logger.info('This is a logger for debugging.')
        logger.debug('This is a logger for debugging.')

    print('Starting')
    for _ in range(5):
        t = multiprocessing.Process(target=run, daemon=True)
        t.start()

    while True:
        time.sleep(0.1)
