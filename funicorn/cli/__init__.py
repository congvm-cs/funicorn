import requests
from requests.exceptions import ConnectionError
from ..exceptions import CommandError
import click
from ..funicorn import Funicorn
from ..http_api import HttpAPI
from ..rpc import ThriftAPI
from ..stat import Statistic
from ..table import print_rows_in_table
from ..utils import get_args_from_class, split_class_from_path
import importlib
import os
import sys
import time


CONTEXT_SETTINGS = {'show_default': True}

common_options = [
    click.option('-h', '--host', default='0.0.0.0', show_default=True,
                 help='funicorn service host.'),
    click.option('-p', '--port', required=True, show_default=True,
                 type=int, help='funicorn service port.')
]

funicorn_app_options = [
    click.option('--model-cls', type=str, required=True,
                 help='Model class'),
    click.option('--funicorn-cls', type=str, default=None,
                 help='Customized Funicorn class [optional]'),
    click.option('--http-cls', type=str, default=None,
                 help='Customized HTTP class [optional]'),
    click.option('--rpc-cls', type=str, default=None,
                 help='Customized RPC class [optional]'),
    click.option('--num-workers', type=int, default=1,
                 help='A number of workers'),
    click.option('--batch-size', type=int, default=1,
                 help='Inference batch size'),
    click.option('--batch-timeout', type=float,
                 default=10, help='Batch timeout (ms)'),
    click.option('--max-queue-size', type=int,
                 default=1000, help='Max queue size'),
    click.option('--http-host', type=str, default='0.0.0.0', help='HTTP host'),
    click.option('--http-port', type=int, default=5000,
                 required=True, help='HTTP port'),
    click.option('--http-threads', type=int, default=10, help='HTTP threads'),
    click.option('--rpc-host', type=str, default='0.0.0.0',
                 help='RPC (Thrift) host'),
    click.option('--rpc-port', type=int, default=None,
                 help='RPC (Thrift) port'),
    click.option('--rpc-threads', type=int, default=10,
                 help='A number of RPC threads'),
    click.option('--gpu-devices', type=str, default=None, help='GPU devices'),
    click.option('--debug', type=bool, default=False, help='debug'),
    click.argument('model-init-kwargs', nargs=-1),
]


def cli_requests(url, method='get', params=None, timeout=1):
    try:
        if method == 'get':
            resp = requests.get(url, params=params, timeout=timeout)
        elif method == 'post':
            resp = requests.post(url, timeout=timeout)
        return resp.json()
    except ConnectionError:
        print('Cannot connect to service! Service may not be started or stopped.')
        exit()


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


@click.command()
@add_options(common_options)
@click.option('--refresh', type=int, default=1, show_default=True,
              help='Refresh time')
def status(host, port, refresh=1):
    ''' View dashboard CLI
    '''
    if refresh < 1:
        refresh = 1
    is_print_header = True
    url = f'http://{host}:{port}/api/cli_status'
    while True:
        try:
            stt = cli_requests(url)
            print_rows_in_table(stt, print_headers=is_print_header)
            if is_print_header:
                is_print_header = False
            time.sleep(refresh)
        except KeyboardInterrupt:
            exit()


@click.command()
@add_options(common_options)
def worker_terminate(host, port):
    ''' Terminate all workers CLI
    '''
    url = f'http://{host}:{port}/api/terminate'
    print('> Waiting for terminate to complete...')
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_idle(host, port):
    ''' Idle all workers CLI
    '''
    url = f'http://{host}:{port}/api/idle'
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_resume(host, port):
    ''' Resume all workers CLI
    '''
    url = f'http://{host}:{port}/api/resume'
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
def worker_restart(host, port):
    ''' Restart all workers CLI
    '''
    url = f'http://{host}:{port}/api/restart'
    print('> Waiting for restart to complete...')
    stt = cli_requests(url)
    print('> ' + stt)


@click.command()
@add_options(common_options)
@click.option('--num-workers', type=int, default=0, show_default=True,
              help='Additional num workers')
@click.option('--gpu-devices', type=str, default=None, show_default=True, help='GPU devices')
def add_workers(host, port, num_workers, gpu_devices):
    url = f'http://{host}:{port}/api/add_workers'
    print('> Add more workers...')
    params = {'num_workers': num_workers, 'gpu_devices': gpu_devices}
    stt = cli_requests(url, params=params)
    print('> ' + stt)


@click.command(context_settings=CONTEXT_SETTINGS)
@add_options(funicorn_app_options)
def start(model_cls, funicorn_cls=None, http_cls=None, rpc_cls=None,
          num_workers=1, batch_size=1, batch_timeout=10,
          max_queue_size=1000,
          http_host='0.0.0.0', http_port=5000, http_threads=30,
          rpc_host='0.0.0.0', rpc_port=None, rpc_threads=30,
          gpu_devices=None, model_init_kwargs=None, debug=False):
    """ Welcome to Funicorn CLI.\n
        Funicorn CLI is about to help developers start Deep Learning service in the fastest way!\n

        Example:\n
            funicorn --model-cls main.Model --batch-size 4 --num-workers 4 --gpu-devices 1,2,3            
        
        Additionally, developers can try:\n
            - funicorn-add: Add more model workers.\n
            - funicorn-idle: Idle all model workers.\n
            - funicorn-resume: Resume all model workers.\n
            - funicorn-terminate: Terminate all model workers.\n
            - funicorn-status: View the service's dashboard .\n
    """
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

    stat = Statistic(funicorn_app=funicorn_app)

    if (rpc_host and http_host) and (rpc_port == http_port):
        raise ConnectionError('rpc_port and http_port must be different.')

    if http_port:
        if http_cls is not None:
            pkg, http_cls = split_class_from_path(http_cls)
            assert issubclass(http_cls, HttpAPI)
        else:
            http_cls = HttpAPI
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
