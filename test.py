# from src import ModelManager
# from src import Funicorn
# from service_streamer import ManagedModel, Streamer
from src import Funicorn, FunicornModel

class TestModel(FunicornModel):
    def init_model(self, *args, **kwargs):
        print('init testmodel')
        # raise ValueError('fake bug')

    def predict(self, batch):
        return batch


if __name__ == '__main__':
#     funicorn = Funicorn(model_cls=TestModel, batch_size=3, batch_timeout=1000,
#                     model_args=('model_path', ), num_workers=2, cuda_devices=[1, 1])
#     funicorn.serve()
    streamer = Funicorn(TestModel, num_workers=3)
    print(streamer.predict(10))
    streamer.serve()