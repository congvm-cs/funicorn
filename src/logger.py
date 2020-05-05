import threading
import multiprocessing
import time


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
        # t = threading.Thread(target=run, daemon=False)
        t = multiprocessing.Process(target=run, daemon=True)
        t.start()

    while True:
        time.sleep(0.1)
