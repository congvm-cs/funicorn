# import tensorflow as tf
from funicorn import Funicorn
from funicorn.utils import get_args_from_class
import click

def hello():
    print("Hello World")


class HelloClass():
    def call(self):
        print("Hello from HelloClass")


# init_args = get_args_from_class(Funicorn)
# funicorn_options = ['click.option(' + str(('--' + str(arg), 'help=' + str(arg.replace('_', " ")))) for arg in init_args]
# print(funicorn_options)