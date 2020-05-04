# from src import ModelManager
# from src import Funicorn
from service_streamer import ManagedModel, Streamer

class TestModel(ManagedModel):
    def init_model(self, *args, **kwargs):
        print('init testmodel')

    def predict(self, batch):
        return batch


if __name__ == '__main__':
#     funicorn = Funicorn(model_cls=TestModel, batch_size=3, batch_timeout=1000,
#                     model_args=('model_path', ), num_workers=2, cuda_devices=[1, 1])
#     funicorn.serve()
    streamer = Streamer(TestModel, 2, worker_num=2, cuda_devices=[0, 0])
    print(streamer.predict([10]))