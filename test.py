from funicorn import Funicorn
import os
import tensorflow as tf


class TestModel():
    def __init__(self, gpu_id, model_path):
        print('CUDA_VISIBLE_DEVICES: ', os.getenv('CUDA_VISIBLE_DEVICES'))
        self.graph = tf.Graph()
        self.sess = tf.Session(graph=self.graph)
        with self.graph.as_default():
            self.x = tf.ones(shape=(3, 3), dtype=tf.float32)
            self.y = tf.ones(shape=(3, 3), dtype=tf.float32)

    def predict(self, batch):
        batch_len = len(batch)
        result = []
        with self.graph.as_default():
            for _ in range(batch_len):
                val = self.sess.run(self.x + self.y)
                result.append(val.shape)
        return result

    def postprocess(self, result):
        return result


if __name__ == '__main__':
    funicorn = Funicorn(TestModel,
                        http_host='0.0.0.0', http_port=8000,
                        batch_size=1, batch_timeout=0.001,
                        num_workers=5, gpu_devices=[1, 1, 1, 4, 5],
                        model_init_kwargs={'model_path': 'path'})
    funicorn.serve()
