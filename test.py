from funicorn import Funicorn
import os


class TestModel():
    def __init__(self, model_path):
        print('CUDA_VISIBLE_DEVICES: ', os.getenv('CUDA_VISIBLE_DEVICES'))
        print(model_path)
    def predict(self, batch):
        return batch


if __name__ == '__main__':
    funicorn = Funicorn(TestModel,
                        http_host='0.0.0.0', http_port=8123,
                        num_workers=3, gpu_devices=[1, 1, 1, 4, 5], 
                        model_init_kwargs={'model_path': 'path'})
    print(funicorn.predict(10))
    funicorn.serve()
