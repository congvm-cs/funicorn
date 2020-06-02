from funicorn import Funicorn, HttpAPI
from funicorn.logger import get_logger
import os
import tensorflow as tf


class TestModel():
    def __init__(self, gpu_id):
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
                   num_workers=1, gpu_devices=[1, 1, 1, 4, 5],
                   model_init_kwargs={'model_path': 'path'})
    http_api = HttpAPI(funicorn_app=app)
    app.serve()
