import click
from ..funicorn import Funicorn
from ..utils import get_args_from_class
import importlib
import os
import sys

CONTEXT_SETTINGS = {'show_default': True}

common_options = [
    click.option('-h', '--host', default='0.0.0.0', show_default=True,
                 help='funicorn service host.'),
    click.option('-p', '--port', required=True, show_default=True,
                 type=int, help='funicorn service port.')
]

funicorn_options = [
    click.option('--model-cls', type=str, required=True,
                 help='Model class to use'),
    click.option('--num-workers', type=int, default=1,
                 help='A number of workers'),
    click.option('--batch-size', type=int, default=1,
                 help='Inference batch size'),
    click.option('--batch-timeout', type=float,
                 default=10, help='Batch timeout (ms)'),
    click.option('--max-queue-size', type=int,
                 default=1000, help='Max queue size'),
    click.option('--http-host', type=str, default=None, help='HTTP host'),
    click.option('--http-port', type=int, default=5005, help='HTTP port'),
    click.option('--http-threads', type=int, default=10, help='HTTP threads'),
    click.option('--rpc-host', type=str, default=None, help='RPC host'),
    click.option('--rpc-port', type=int, default=5006, help='RPC port'),
    click.option('--rpc-threads', type=int, default=10,
                 help='A number of RPC threads'),
    click.option('--gpu-devices', type=str, default=None, help='GPU devices'),
    click.option('--debug', type=bool, default=False, help='debug'),
    click.argument('model-init-kwargs', nargs=-1), # help='model init kwargs'
]


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


@click.command()
@add_options(common_options)
def terminate(host, port):
    print(f"{host}:{port} to use in terminate")


@click.command()
@add_options(common_options)
def restart(host, port):
    print(f"{host}:{port} to use in restart")


@click.command()
@add_options(common_options)
def idle(host, port):
    print(f"{host}:{port} to use in idle")


# @click.group()
@click.command(context_settings=CONTEXT_SETTINGS)
@add_options(funicorn_options)
def start(model_cls, num_workers=1, batch_size=1, batch_timeout=10,
          max_queue_size=1000,
          http_host=None, http_port=5000, http_threads=30,
          rpc_host=None, rpc_port=5001, rpc_threads=30,
          gpu_devices=None, model_init_kwargs=None, debug=False):
    
    sys.path.append(os.getcwd())
    subpaths = model_cls.split('.')
    if len(subpaths) > 2:
        pkg, model_cls_name = subpaths[-2:]
    else:
        pkg, model_cls_name = subpaths
    model_cls = getattr(importlib.import_module(pkg), model_cls_name)

    if model_init_kwargs:
        model_init_kwargs = dict(kwarg.split(':') for kwarg in model_init_kwargs)

    if gpu_devices:
        gpu_devices = [gpu_id for gpu_id in gpu_devices.split(',') if gpu_id != '']
    funicorn_service = Funicorn(model_cls, num_workers, batch_size, batch_timeout,
                                max_queue_size,
                                http_host, http_port, http_threads,
                                rpc_host, rpc_port, rpc_threads,
                                gpu_devices, model_init_kwargs, debug)
    funicorn_service.serve()


