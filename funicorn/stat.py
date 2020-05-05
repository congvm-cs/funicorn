import time
import threading


class Statistic():
    def __init__(self, num_workers):
        self.statistics_info = {
            'start_time': time.time(),
            'num_req': 0,
            'num_res': 0,
            'avg_latency': 0,
            'avg_req_per_sec': 0,
            'avg_res_per_sec': 0,
            'crashes': 0,
            'num_workers': num_workers
        }
        self.lock = threading.Lock()

    def __getitem__(self, attr):
        return self.statistics_info[attr]

    def __setitem__(self, attr, value):
        with self.lock:
            self.statistics_info[attr] = value

    def __repr__(self):
        print(self.statistics_info)

    def increment(self, name, value=1):
        with self.lock:
            self.statistics_info[name] += value

    def decrement(self, name, value=1):
        with self.lock:
            self.statistics_info[name] -= value

    def average(self, name, value):
        with self.lock:
            n_req = self.statistics_info['num_req']
            self.statistics_info[name] += value
            self.statistics_info[name] /= n_req

    @property
    def info(self):
        return self.statistics_info

    def update(self, data: dict):
        return self.statistics_info.update(data)