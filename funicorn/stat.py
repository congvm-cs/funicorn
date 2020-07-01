import time
import threading
from .table import print_table
from .logger import get_logger

class Statistic():
    def __init__(self, funicorn_app=None):
        self.funicorn_app = funicorn_app
        self.start_time = time.time()
        self.stats_info = {
            'status': 'live',
            'uptime': 0,
            'total_req': 0,
            'total_res': 0,
            'avg_latency': 0,
            'avg_req': 0,
            'avg_res': 0,
            'crashes': 0,
        }
        self.lock = threading.Lock()
        self.logger = get_logger(name='Stat', mode='info')
        self.logger.info('Init statistics')
        
    def __getitem__(self, attr):
        return self.stats_info[attr]

    def __setitem__(self, attr, value):
        with self.lock:
            self.stats_info[attr] = value

    def increment(self, name, value=1):
        with self.lock:
            self.stats_info[name] += value

    def decrement(self, name, value=1):
        with self.lock:
            self.stats_info[name] -= value

    def average(self, name):
        with self.lock:
            return self.stats_info[name]

    @property
    def info(self):
        self.update()
        return self.stats_info

    def update(self):
        uptime = int(time.time() - self.start_time)
        with self.lock:
            self.stats_info['uptime'] = uptime
            self.stats_info['avg_req'] = 0 if uptime == 0 else round(self.stats_info['total_req']/uptime, 2)
            self.stats_info['avg_res'] = 0 if uptime == 0 else round(self.stats_info['total_res']/uptime, 2)

    @property
    def cli_info(self):
        self.update()
        table = [['status', 'uptime', 'total requests', 'total responses', 'avg latency', 'avg requests', 'avg responses', 'crashes'],
                 [self.stats_info['status'], self.stats_info['uptime'], self.stats_info['total_req'], self.stats_info['total_res'],
                  self.stats_info['avg_latency'], self.stats_info['avg_req'], self.stats_info['avg_res'], self.stats_info['crashes']]]
        return print_table(table, color=(0, 255, 0))
