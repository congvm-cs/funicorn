import requests
import click
from ..funicorn import Funicorn
from ..flaskorn import HttpApi
from ..thriftcorn import ThriftAPI
from ..stat import Statistic
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

funicorn_app_options = [
    click.option('--funicorn-cls', type=str, default=None,
                 help='Model class to use'),
    click.option('--model-cls', type=str, default=None,
                 help='Model class to use'),
    click.option('--http-cls', type=str, default=None,
                 help='Model class to use'),
    click.option('--rpc-cls', type=str, default=None,
                 help='Model class to use'),
    click.option('--num-workers', type=int, default=1,
                 help='A number of workers'),
    click.option('--batch-size', type=int, default=1,
                 help='Inference batch size'),
    click.option('--batch-timeout', type=float,
                 default=10, help='Batch timeout (ms)'),
    click.option('--max-queue-size', type=int,
                 default=1000, help='Max queue size'),
    click.option('--http-host', type=str, default='0.0.0.0', help='HTTP host'),
    click.option('--http-port', type=int, default=5000, help='HTTP port'),
    click.option('--http-threads', type=int, default=10, help='HTTP threads'),
    click.option('--rpc-host', type=str, default='0.0.0.0', help='RPC host'),
    click.option('--rpc-port', type=int, default=None, help='RPC port'),
    click.option('--rpc-threads', type=int, default=10,
                 help='A number of RPC threads'),
    click.option('--gpu-devices', type=str, default=None, help='GPU devices'),
    click.option('--debug', type=bool, default=False, help='debug'),
    click.argument('model-init-kwargs', nargs=-1),  # help='model init kwargs'
]


def cli_requests(url, method='get', params=None):
    if method == 'get':
        resp = requests.get(url, params=params, timeout=1000)
    elif method == 'post':
        resp = requests.post(url, timeout=1000)
    return resp.json()


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


@click.command()
@add_options(common_options)
def worker_terminate(host, port):
    url = f'http://{host}:{port}/terminate'
    print('> Waiting for terminate to complete...')
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_idle(host, port):
    url = f'http://{host}:{port}/idle'
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_resume(host, port):
    url = f'http://{host}:{port}/resume'
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_restart(host, port):
    url = f'http://{host}:{port}/restart'
    print('> Waiting for restart to complete...')
    stt = cli_requests(url)
    print('> ' + stt)

@click.command()
@add_options(common_options)
@click.option('--num-workers', type=int, default=0, show_default=True,
                 help='Additional num workers')
@click.option('--gpu-devices', type=str, default=None, show_default=True, help='GPU devices')
def add_workers(host, port, num_workers, gpu_devices):
    url = f'http://{host}:{port}/add_workers'
    print('> Add more workers...')
    params = {'num_workers': num_workers, 'gpu_devices': gpu_devices}
    stt = cli_requests(url, params=params)
    print('> ' + stt)


def split_class_from_path(path):
    subpaths = path.split('.')
    if len(subpaths) > 2:
        pkg, cls_name = subpaths[-2:]
    else:
        pkg, cls_name = subpaths
    cls_name = getattr(importlib.import_module(pkg), cls_name)
    return pkg, cls_name

@click.command(context_settings=CONTEXT_SETTINGS)
@add_options(funicorn_app_options)
def start(funicorn_cls=None, model_cls=None, http_cls=None, rpc_cls=None,
          num_workers=0, batch_size=1, batch_timeout=10,
          max_queue_size=1000,
          http_host='0.0.0.0', http_port=5000, http_threads=30,
          rpc_host='0.0.0.0', rpc_port=None, rpc_threads=30,
          gpu_devices=None, model_init_kwargs=None, debug=False):

    # Append current working directory to search module
    sys.path.append(os.getcwd())

    if funicorn_cls is None:
        funicorn_cls = Funicorn
    else:
        pkg, funicorn_cls = split_class_from_path(funicorn_cls)    

    if model_cls is not None:
        pkg, model_cls = split_class_from_path(model_cls)

        if model_init_kwargs:
            model_init_kwargs = dict(kwarg.split(':')
                                     for kwarg in model_init_kwargs)

    if gpu_devices:
        gpu_devices = [
            gpu_id for gpu_id in gpu_devices.split(',') if gpu_id != '']

    funicorn_app = funicorn_cls(model_cls=model_cls,
                                num_workers=num_workers,
                                batch_size=batch_size,
                                batch_timeout=batch_timeout,
                                max_queue_size=max_queue_size,
                                gpu_devices=gpu_devices,
                                model_init_kwargs=model_init_kwargs,
                                debug=debug)

    stat = Statistic(num_workers=num_workers)

    if (rpc_host and http_host) and (rpc_port == http_port):
        raise ConnectionError('rpc_port and http_port must be different.')

    if http_port:
        if http_cls is not None:
            pkg, http_cls = split_class_from_path(http_cls)
            assert issubclass(http_cls, HttpApi)
        else:
            http_cls = HttpApi
        http = http_cls(funicorn_app=funicorn_app, stat=stat,
                        host=http_host, port=http_port,
                        threads=rpc_threads,
                        debug=debug)
    if rpc_port:
        if rpc_cls is not None:
            pkg, rpc_cls = split_class_from_path(rpc_cls)
            assert issubclass(rpc_cls, ThriftAPI)
        else:
            rpc_cls = ThriftAPI
        rpc = rpc_cls(funicorn_app=funicorn_app, stat=stat,
                      host=rpc_host, port=rpc_port,
                      threads=rpc_threads,
                      debug=debug)
    funicorn_app.serve()
