''' Notes on multiprocessing in python 
'''
import os
import multiprocessing as mp
from random import randint
import threading
from collections import namedtuple
import uuid
import time
import json
from queue import Empty
from queue import Queue
from .exceptions import LengthEqualtyError
from .utils import get_logger, img_bytes_to_img_arr
from .utils import coloring_worker_name, coloring_funicorn_name
from .stat import Statistic

from .flaskorn import HttpApi
from .thriftcorn import ThriftAPI

MAX_QUEUE_SIZE = 1000
RESULT_TIMEOUT = 0.001
DEFAULT_TIMEOUT = 500
WORKER_TIMEOUT = 3
DEFAULT_BATCH_TIMEOUT = 0.01

# mp = multiprocessing.get_context("spawn") # Error on Server

__all__ = ['Funicorn']
Task = namedtuple('Task', ['request_id', 'data'])


class BaseWorker():
    def __init__(self, model_cls, input_queue=None, result_dict=None,
                 batch_size=1, batch_timeout=DEFAULT_BATCH_TIMEOUT,
                 ready_event=None, destroy_event=None, model_init_kwargs=None,
                 debug=False):
        self._model_init_kwargs = model_init_kwargs or {}
        self._model_cls = model_cls
        self._input_queue = input_queue
        self._result_dict = result_dict
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._ready_event = ready_event
        self._destroy_event = destroy_event
        self._pid = os.getpid()
        self._model = None
        self._debug = debug
        self.logger = get_logger(coloring_worker_name(
            'BASE-WORKER'), mode='debug' if self._debug else 'info')

    def _recv_request(self):
        raise NotImplementedError

    def _send_response(self, request_id, result):
        raise NotImplementedError

    def _init_environ(self):
        # INFO messages are not printed
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'

    def run_once(self):
        # Get data from queue
        batch = []
        start_time = time.time()
        for _ in range(self.batch_size):
            try:
                task = self._recv_request()
            except TimeoutError:
                break
            else:
                batch.append(task)
        if not batch:
            return 0

        batch_size = len(batch)
        model_input = [task.data for task in batch]

        # Model predict
        start_model_time = time.time()
        results = self._model.predict(model_input)
        end_model_time = time.time()
        assert isinstance(results, list), ValueError(
            '`results` must be a list')
        assert len(results) == len(batch), LengthEqualtyError(
            'Length of result and batch must be equal')
        for (task, result) in zip(batch, results):
            self._send_response(task.request_id, result)
        self.logger.info(
            f'Inference with batch_size: {batch_size} - inference-time: {time.time() - start_time}\
                 - model-time: {end_model_time - start_model_time}')
        # Return None or something to notify number of data in queue
        return batch_size

    def run(self):
        '''Loop into a queue'''
        while True:
            try:
                handled = self.run_once()
                if self._destroy_event and self._destroy_event.is_set():
                    break
                if not handled:
                    time.sleep(RESULT_TIMEOUT)
            except Exception as e:
                self.logger.error(e)


class Worker(BaseWorker):
    def _recv_request(self):
        try:
            start_time = time.time()
            task = self._wrk_queue.get(timeout=self.batch_timeout)
            self.logger.info(
                f'[_recv_request] get from queue {time.time() - start_time}')
        except Empty:
            raise TimeoutError
        else:
            return task

    def _send_response(self, request_id, result):
        self._result_dict[request_id] = result

    def run(self, worker_id=None, gpu_id=None, ready_event=None, destroy_event=None, wrk_queue=None):
        ''' Init process parameters
            Every param initialized here are seperable among processes
        '''
        self.logger = get_logger(
            coloring_worker_name(f'WORKER-{worker_id}'), mode='debug' if self._debug else 'info')
        self._init_environ()
        self._wrk_queue = wrk_queue or self._input_queue
        self._worker_id = worker_id
        self._pid = os.getpid()
        self._model_init_kwargs.update({'gpu_id': gpu_id})

        device = f'GPU-{gpu_id}' if gpu_id else 'CPU'
        self.logger.info(f'Initializing model in {device}')
        self._model = self._model_cls(**self._model_init_kwargs)

        if ready_event:
            ready_event.set()  # tell father process that init is finished
        if destroy_event:
            self._destroy_event = destroy_event

        # Run in loop
        super().run()


class Funicorn():
    def __init__(self, model_cls=None, num_workers=0, batch_size=1, batch_timeout=10,
                 max_queue_size=1000,
                 http_host=None, http_port=5000, http_threads=30,
                 rpc_host=None, rpc_port=5001, rpc_threads=30,
                 gpu_devices=None,
                 model_init_kwargs=None, debug=False, timeout=5000):
        self.model_cls = model_cls
        self.logger = get_logger(
            coloring_funicorn_name(), mode='debug' if debug else 'info')
        self._model_init_kwargs = model_init_kwargs or {}
        self.timeout = timeout
        self.debug = debug

        self.http_host = http_host
        self.http_port = http_port
        self.http_threads = http_threads

        self.rpc_host = rpc_host
        self.rpc_port = rpc_port
        self.rpc_threads = rpc_threads

        if (self.rpc_host and self.http_host) and (self.rpc_port == self.http_port):
            raise ConnectionError('rpc_port and http_port must be different.')
        self.gpu_devices = gpu_devices
        self.num_workers = num_workers
        self._input_queue = Queue(maxsize=max_queue_size)
        self._result_dict = mp.Manager().dict()

        self._wrk = Worker(self.model_cls, self._input_queue, self._result_dict,
                           batch_size=batch_size, batch_timeout=batch_timeout/1000,
                           model_init_kwargs=model_init_kwargs)

        self.pid = os.getpid()
        self._init_stat()

        self.wrk_ps = []
        self.wrk_ready_events = []
        self.wrk_destroy_events = []
        self.queue_ps = []
        self.http = None
        self.rpc = None

        if self.http_host:
            self.http = self.init_http_server(funicorn_app=self,
                                              host=self.http_host, port=self.http_port,
                                              stat=self.stat, threads=self.rpc_threads,
                                              timeout=self.timeout, debug=self.debug)
        if self.rpc_host:
            self.rpc = self.init_rpc_server(funicorn_app=self,
                                            host=self.rpc_host, port=self.rpc_port,
                                            stat=self.stat, threads=self.rpc_threads,
                                            timeout=self.timeout, debug=self.debug)

    def get_worker_pids(self):
        return [wrk.pid for wrk in self.wrk_ps]

    def _init_stat(self):
        self.stat = Statistic(num_workers=self.num_workers)
        self.stat.update({'parent_pid': self.pid})

    def init_rpc_server(self, funicorn_app, host, port, stat=None,
                        threads=40, timeout=1000, debug=False):
        rpc = ThriftAPI(funicorn_app=funicorn_app,
                        host=host, port=port,
                        stat=stat, threads=threads,
                        timeout=timeout,
                        debug=debug)
        return rpc

    def init_http_server(self, funicorn_app, host, port, stat=None,
                         threads=40, timeout=1000, debug=False):
        http = HttpApi(funicorn_app=funicorn_app,
                       host=host, port=port,
                       stat=stat, threads=threads,
                       timeout=timeout,
                       debug=debug)
        return http

    def _init_connections(self):
        if self.http is not None:
            self.http.start()

        if self.rpc is not None:
            self.rpc.start()

    def _init_all_workers(self):
        if self.model_cls is None:
            self.logger.warning('Cannot start workers because model class is not provided!')
        else:
            for idx in range(self.num_workers):
                ready_event = mp.Event()
                destroy_event = mp.Event()
                args = (ready_event, destroy_event)

                if self.gpu_devices is not None:
                    gpu_id = self.gpu_devices[idx % len(self.gpu_devices)]
                else:
                    gpu_id = -1

                wrk_queue = mp.Queue()
                args = (idx, gpu_id, ready_event, destroy_event, wrk_queue)
                wrk = mp.Process(target=self._wrk.run, args=args,
                                daemon=True,
                                name=f'funicorn-worker-{idx}')
                wrk.start()
                self.wrk_ps.append(wrk)
                self.wrk_ready_events.append(ready_event)
                self.wrk_destroy_events.append(destroy_event)
                self.queue_ps.append(wrk_queue)

    def _wait_for_worker_and_serve(self, timeout=WORKER_TIMEOUT):
        # wait for all workers finishing init
        for (i, e) in enumerate(self.wrk_ready_events):
            # todo: select all events with timeout
            is_ready = e.wait(timeout)
            self.logger.info("[WORKER-%d] ready state: %s" % (i, is_ready))
            if not is_ready:
                self.logger.error("[WORKER-%d] cannot start. EXIT!" % (i))
                exit()

    def predict(self, data, asynchronous=False):
        request_id = str(uuid.uuid4())
        # Distribute task to wrk_queue
        input_queue = self.queue_ps[randint(0, len(self.queue_ps) - 1)]
        input_queue.put(Task(request_id=request_id, data=data))

        self.logger.info(f'Received data with request_id: {request_id}')
        if asynchronous:
            return request_id
        else:
            return self.get_result(request_id)

    def predict_img_bytes(self, img_bytes):
        start_time = time.time()
        img_arr = img_bytes_to_img_arr(img_bytes)
        self.logger.info(
            f'[img_bytes_to_img_arr] process-time: {time.time() - start_time}')
        json_result = self.predict(img_arr)
        if isinstance(json_result, str) or isinstance(json_result, dict):
            ValueError('The result from rpc must be json string')
        return json.dumps(json_result)

    def get_result(self, request_id):
        ret = None
        while True:
            ret = self._result_dict.pop(request_id, None)
            if ret is not None:
                break
            time.sleep(RESULT_TIMEOUT)
        self.logger.info(f'Sent result with request_id: {request_id}')
        return ret

    def terminate_all_worker(self):
        '''Terminate all workers'''
        for destroy_event in self.wrk_destroy_events:
            destroy_event.set()

    def idle_all_worker(self):
        '''Idle all workers'''
        pass

    def restart_all_worker(self):
        pass

    def check_all_worker(self):
        '''Check status of all workers. Restart them if necessary'''
        pass

    def ping(self):
        self.logger.info("Ping!")
        return

    def _recheck_all_modules(self):
        if not self.rpc and not self.http and not self.model_cls:
            self.logger.error("Nothing is running. STOP!")
            exit()

    def serve(self):
        self._init_all_workers()
        self._wait_for_worker_and_serve()
        self._init_connections()
        self._recheck_all_modules()
        while True:
            time.sleep(300)
