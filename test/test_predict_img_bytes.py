from funicorn import Funicorn, HttpAPI
from funicorn import ThriftAPIV2
from funicorn import Statistic
from funicorn.logger import get_logger
import os
import tensorflow as tf


class TestModel():
    def __init__(self, gpu_id, model_path):
        self.logger = get_logger()

    def predict(self, batch):
        batch_len = len(batch)
        result = []
        for _ in range(batch_len):
            result.append({'val_shape': 3})
        return result

    def postprocess(self, result):
        return result

if __name__ == '__main__':
    app = Funicorn(TestModel,
                   batch_size=1, batch_timeout=0.01,
                   num_workers=2, gpu_devices=[1, 1, 1, 4, 5],
                   model_init_kwargs={'model_path': 'path'})
    stat = Statistic(funicorn_app=app)
    http_api = HttpAPI(funicorn_app=app, stat=stat)
    thrift_api = ThriftAPIV2(funicorn_app=app, host='0.0.0.0', stat=stat, port=5005, threads=2)
    
    app.serve()
