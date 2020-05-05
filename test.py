from funicorn import Funicorn
import os


class TestModel():
    def __init__(self, *args, **kwargs):
        print('CUDA_VISIBLE_DEVICES: ', os.getenv('CUDA_VISIBLE_DEVICES'))

    def predict(self, batch):
        return batch


if __name__ == '__main__':
    funicorn = Funicorn(TestModel, num_workers=3, gpu_devices=[1, 2, 3, 4, 5])
    print(funicorn.predict(10))
    funicorn.serve()
