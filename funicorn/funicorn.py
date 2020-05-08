''' Notes on multiprocessing in python 
'''
import os
import multiprocessing as mp
import threading
from collections import namedtuple
import uuid
import time
import json
from queue import Empty

from .exceptions import LengthEqualtyError
from .utils import get_logger, img_bytes_to_img_arr
from .stat import Statistic

from .flaskorn import HttpApi
from .thriftcorn import ThriftAPI

MAX_QUEUE_SIZE = 1000
RESULT_TIMEOUT = 0.001
DEFAULT_TIMEOUT = 500
WORKER_TIMEOUT = 20
DEFAULT_BATCH_TIMEOUT = 0.01

# mp = multiprocessing.get_context("spawn") # Error on Server

__all__ = ['FunicornModel', 'Funicorn']
Task = namedtuple('Task', ['request_id', 'data'])


class FunicornModel():
    '''Experimental'''

    def __init__(self, gpu_id, *args, **kwargs):
        self._gpu_id = gpu_id
        self.init_gpu_devices()
        self.init_model(gpu_id, *args, **kwargs)

    def get_logger(self):
        return get_logger()

    def init_gpu_devices(self):
        if self._gpu_id is not None:
            os.environ['CUDA_VISIBLE_DEVICES'] = str(self._gpu_id)
        else:
            # -1 means no cuda device to use
            os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

    def init_model(self, gpu_id, *args, **kwargs):
        raise NotImplementedError('`init_model` must be implemented')

    def predict(self, data):
        raise NotImplementedError('`predict` must be implemented')


class BaseWorker():
    def __init__(self, model_cls, input_queue=None, result_dict=None,
                 batch_size=1, batch_timeout=DEFAULT_BATCH_TIMEOUT,
                 ready_event=None, destroy_event=None,
                 model_init_args=None, model_init_kwargs=None,
                 debug=False):
        self._model_init_args = model_init_args or []
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
        self._logger = get_logger(mode='debug' if debug else 'info')

    def _recv_request(self):
        raise NotImplementedError

    def _send_response(self, request_id, result):
        raise NotImplementedError

    def run_once(self):
        # Get data from queue
        batch = []
        start_time = time.time()
        for idx in range(self.batch_size):
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
        results = self._model.predict(model_input)
        assert isinstance(results, list), ValueError(
            '`results` must be a list')
        assert len(results) == len(batch), LengthEqualtyError(
            'Length of result and batch must be equal')
        for (task, result) in zip(batch, results):
            self._send_response(task.request_id, result)
        self._logger.info(
            f'[Worker-{self._worker_id}] Inference with batch_size: {batch_size} - inference-time: {time.time() - start_time}')
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
                self._logger.error(e)


class Worker(BaseWorker):
    def _recv_request(self):
        try:
            start_time = time.time()
            task = self._input_queue.get(timeout=self.batch_timeout)
            self._logger.info(
                f'[_recv_request] get from queue {time.time() - start_time}')
        except Empty:
            raise TimeoutError
        else:
            return task

    def _send_response(self, request_id, result):
        self._result_dict[request_id] = result

    def run(self, worker_id=None, gpu_id=None, ready_event=None, destroy_event=None):
        ''' Init process parameters
            Every param initialized here are seperable among processes
        '''
        self._worker_id = worker_id
        self._pid = os.getpid()
        self._model_init_kwargs.update({'gpu_id': gpu_id})
        self._logger.info(f'[Worker-{self._worker_id}] Init Model...')
        self._model = self._model_cls(**self._model_init_kwargs)

        if ready_event:
            ready_event.set()  # tell father process that init is finished
        if destroy_event:
            self._destroy_event = destroy_event

        # Run in loop
        super().run()


class Funicorn():
    def __init__(self, model_cls, num_workers=1, batch_size=1, batch_timeout=10,
                 max_queue_size=1000,
                 http_host=None, http_port=5000, http_threads=30,
                 rpc_host=None, rpc_port=5001, rpc_threads=30,
                 gpu_devices=None,
                 model_init_args=None, model_init_kwargs=None, debug=False):

        self._logger = get_logger(mode='debug' if debug else 'info')
        self._model_init_args = model_init_args or []
        self._model_init_kwargs = model_init_kwargs or {}

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
        # self._input_queue = mp.Queue(maxsize=max_queue_size)
        self._input_queue = mp.Manager().Queue(maxsize=max_queue_size)
        self._result_dict = mp.Manager().dict()
        self._wrk = Worker(model_cls, self._input_queue, self._result_dict,
                           batch_size=batch_size, batch_timeout=batch_timeout/1000,
                           model_init_args=model_init_args, model_init_kwargs=model_init_kwargs)
        self.pid = os.getpid()
        self._init_stat()

        self.wrk_ps = []
        self.wrk_ready_events = []
        self.wrk_destroy_events = []

    def get_worker_pids(self):
        return [wrk.pid for wrk in self.wrk_ps]

    def _init_stat(self):
        self.stat = Statistic(num_workers=self.num_workers)
        self.stat.update({'parent_pid': self.pid})

    def _init_rpc_server(self):
        self._rpc = ThriftAPI(funicorn=self,
                              host=self.rpc_host, port=self.rpc_port,
                              stat=self.stat,
                              threads=self.rpc_threads)
        self._rpc.start()

    def _init_http_server(self):
        self._http = HttpApi(funicorn=self, host=self.http_host,
                             port=self.http_port, stat=self.stat,
                             threads=self.http_threads)
        self._http.start()

    def _init_all_workers(self):
        for idx in range(self.num_workers):
            ready_event = mp.Event()
            destroy_event = mp.Event()
            args = (ready_event, destroy_event)

            if self.gpu_devices is not None:
                gpu_id = self.gpu_devices[idx % len(self.gpu_devices)]
            else:
                gpu_id = -1
            args = (idx, gpu_id, ready_event, destroy_event)
            wrk = mp.Process(target=self._wrk.run, args=args,
                             daemon=True,
                             name=f'funicorn-worker-{idx}')
            wrk.start()
            self.wrk_ps.append(wrk)
            self.wrk_ready_events.append(ready_event)
            self.wrk_destroy_events.append(destroy_event)

    def _wait_for_worker_ready(self, timeout=WORKER_TIMEOUT):
        # wait for all workers finishing init
        for (i, e) in enumerate(self.wrk_ready_events):
            # todo: select all events with timeout
            is_ready = e.wait(timeout)
            self._logger.info("[Worker-%d] ready state: %s" % (i, is_ready))

    def predict(self, data, asynchronous=False):
        request_id = str(uuid.uuid4())
        self._input_queue.put(Task(request_id=request_id, data=data))
        self._logger.info(
            f'[Funicorn] Request data with request_id: {request_id}')
        if asynchronous:
            return request_id
        else:
            return self.get_result(request_id)

    def predict_img_bytes(self, img_bytes):
        start_time = time.time()
        img_arr = img_bytes_to_img_arr(img_bytes)
        self._logger.info(
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
        self._logger.info(f'[Funicorn] Received with request_id: {request_id}')
        return ret

    def destroy_all_worker(self):
        '''Destroy all workers'''
        for destroy_event in self.wrk_destroy_events:
            destroy_event.set()

    def check_all_worker(self):
        '''Check status of all workers. Restart them if necessary'''
        pass

    def ping(self):
        self._logger.info("[Funicorn] Ping!")
        return

    def serve(self):
        self._init_all_workers()
        self._wait_for_worker_ready()

        if self.http_host:
            self._init_http_server()
        if self.rpc_host:
            self._init_rpc_server()

        while True:
            time.sleep(300)
