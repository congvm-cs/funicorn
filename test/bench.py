from funicorn.client import ClientRPC
from funicorn.logger import get_logger
from funicorn.utils import colored_network_name
from concurrent.futures import ThreadPoolExecutor
import time
import numpy as np

logger = get_logger(colored_network_name('CLIENT'))

def sequential_test():
    print('='*100)
    N = 10000
    print('Sequential Requests with {}\n'.format(N))
    rpc = ClientRPC(port=8001)
    t = time.time()
    for i in range(N):
        rpc.ping()
    logger.info('Latency: {}'.format((time.time() - t)/N))


def parallel_test():
    print('='*100)
    num_clients = 30
    num_requests_per_client = 1000

    print('Parallel Requests with num_clients: {} - num_requests_per_client: {}\n'.format(num_clients, num_requests_per_client))

    def ping(num_requests_per_client):
        rpc = ClientRPC(port=8001)
        for _ in range(num_requests_per_client):
            rpc.ping()

    clients  = []
    with ThreadPoolExecutor(max_workers=num_clients) as executor:
        t = time.time()
        for i in range(num_clients):
            # logger.info('Start {}'.format(i))
            future = executor.submit(ping, num_requests_per_client)
            clients.append(future)
        for f in clients:
            f.result()
        logger.info('Latency: {}'.format((time.time() - t)/(num_clients*num_requests_per_client)))

def test_send_bytes():
    img_bytes = np.ones((320, 240, 3), np.uint8).tobytes()
    print('='*100)
    num_clients = 10
    num_requests_per_client = 1000

    print('Parallel Requests with num_clients: {} - num_requests_per_client: {}\n'.format(num_clients, num_requests_per_client))

    def send_bytes(img_bytes, num_requests_per_client):
        rpc = ClientRPC(port=8001)
        for _ in range(num_requests_per_client):
            rpc.predict_img_bytes(img_bytes)

    clients  = []
    with ThreadPoolExecutor(max_workers=num_clients) as executor:
        t = time.time()
        for i in range(num_clients):
            # logger.info('Start {}'.format(i))
            future = executor.submit(send_bytes, img_bytes, num_requests_per_client)
            clients.append(future)
        for f in clients:
            f.result()
        logger.info('Latency: {}'.format((time.time() - t)/(num_clients*num_requests_per_client)))


test_send_bytes()