from funicorn.utils import get_logger
import os
import tensorflow as tf

class NSFW_V2():
    def __init__(self, gpu_id, model_path):
        self.logger = get_logger()
        self.graph = tf.Graph()
        self.sess = tf.Session(graph=self.graph)
        with self.graph.as_default():
            self.x = tf.ones(shape=(3, 3), dtype=tf.float32)
            self.y = tf.ones(shape=(3, 3), dtype=tf.float32)

    def predict(self, batch):
        batch_len = len(batch)
        result = []
        for _ in range(batch_len):
            result.append({'val_shape': 3})
        return result

    def postprocess(self, result):
        return result

