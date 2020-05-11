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
from collections import namedtuple
from .exceptions import LengthEqualtyError
from .utils import get_logger, img_bytes_to_img_arr
from .utils import coloring_worker_name, coloring_funicorn_name, coloring_network_name
from .stat import Statistic
from .mqueue import Queue as MQueue
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
WorkerInfo = namedtuple('WorkerInfo', ['wrk', 'pid', 'gpu_id',
                                       'ps_status', 'queue',
                                       'ready_event', 'idle_event', 'terminate_event'])


class BaseWorker():
    def __init__(self, model_cls, result_dict=None,
                 batch_size=1, batch_timeout=DEFAULT_BATCH_TIMEOUT,
                 ready_event=None, idle_event=None, terminate_event=None, model_init_kwargs=None,
                 debug=False):
        self._model_init_kwargs = model_init_kwargs or {}
        self._model_cls = model_cls
        self._wrk_queue = None
        self._result_dict = result_dict
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._ready_event = ready_event
        self._idle_event = idle_event
        self._terminate_event = terminate_event
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
                if self._ready_event and not self._ready_event.is_set() and (self._wrk_queue.qsize() == 0):
                    self.logger.info('All jobs have been done. Terminated')
                    self._terminate_event.set()
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

    def run(self, worker_id=None, gpu_id=None, ready_event=None, idle_event=None, terminate_event=None, wrk_queue=None):
        ''' Init process parameters
            Every param initialized here are seperable among processes
        '''
        self.logger = get_logger(
            coloring_worker_name(f'WORKER-{worker_id}'), mode='debug' if self._debug else 'info')
        self._init_environ()
        self._wrk_queue = wrk_queue
        self._worker_id = worker_id
        self._pid = os.getpid()
        self._model_init_kwargs.update({'gpu_id': gpu_id})

        device = f'GPU-{gpu_id}' if gpu_id else 'CPU'
        self.logger.info(f'Initializing Worker in {device}')
        self._model = self._model_cls(**self._model_init_kwargs)

        if ready_event:
            self._ready_event = ready_event
            self._ready_event.set()  # tell father process that init is finished

        if terminate_event:
            self._terminate_event = terminate_event

        if idle_event:
            self._idle_event = idle_event
        # Run in loop
        super().run()


class Funicorn():
    def __init__(self, model_cls=None, num_workers=0, batch_size=1, batch_timeout=10,
                 max_queue_size=1000,
                 gpu_devices=None,
                 model_init_kwargs=None, debug=False, timeout=5000):
        self.model_cls = model_cls
        self.logger = get_logger(
            coloring_funicorn_name(), mode='debug' if debug else 'info')
        self._model_init_kwargs = model_init_kwargs or {}
        self.timeout = timeout
        self.debug = debug

        self.gpu_devices = gpu_devices
        self.num_workers = num_workers

        self._input_queue = Queue()
        self._result_dict = mp.Manager().dict()

        self._wrk = Worker(self.model_cls, self._result_dict,
                           batch_size=batch_size, batch_timeout=batch_timeout/1000,
                           model_init_kwargs=model_init_kwargs)

        self.pid = os.getpid()
        self._init_stat()
        self.idle_event = mp.Event()
        self.wrk_ps = []

        self.connection_apps = []

    def register_connection(self, connection):
        self.logger.info(f'Register {coloring_network_name(connection.name)} connection')
        self.connection_apps.append(connection)

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
        for conn in self.connection_apps:
            conn.start()
     
    def _init_all_workers(self):
        if self.model_cls is None:
            self.logger.warning(
                    'Cannot start workers because model class is not provided!')
        else:
            if self.num_workers <= 0:
                self.logger.warning(
                    'Cannot start workers because num workers is set to 0!')
            else:
                for idx in range(self.num_workers):
                    ready_event = mp.Event()
                    idle_event = mp.Event()
                    terminate_event = mp.Event()
                    args = (ready_event, terminate_event)

                    if self.gpu_devices is not None:
                        gpu_id = self.gpu_devices[idx % len(self.gpu_devices)]
                    else:
                        gpu_id = None

                    wrk_queue = MQueue()  # mp.Queue()
                    args = (idx, gpu_id, ready_event, idle_event,
                            terminate_event, wrk_queue)
                    wrk = mp.Process(target=self._wrk.run, args=args,
                                    daemon=True,
                                    name=f'funicorn-worker-{idx}')
                    wrk.start()
                    worker_info = WorkerInfo(wrk=wrk,
                                            pid=wrk.pid,
                                            gpu_id=gpu_id,
                                            ps_status='unknown',
                                            queue=wrk_queue,
                                            ready_event=ready_event,
                                            idle_event=idle_event,
                                            terminate_event=terminate_event)
                    self.wrk_ps.append(worker_info)

    def _wait_for_worker(self, timeout=WORKER_TIMEOUT):
        # wait for all workers finishing init
        for (i, worker_info) in enumerate(self.wrk_ps):
            # todo: select all events with timeout
            is_ready = worker_info.ready_event.wait(timeout)
            self.logger.info(f"{coloring_worker_name(f'WORKER-{i}')} ready state: {is_ready}")
            if not is_ready:
                self.logger.error(f"coloring_worker_name(f'WORKER-{i}') cannot start. EXIT!")
                exit()

    def _start_task_distributations(self):
        '''Distribute task to wrk_queue'''
        while True:
            task = self._input_queue.get()
            input_queue = self.wrk_ps[randint(0, len(self.wrk_ps) - 1)].queue
            input_queue.put(task)

    def predict(self, data, asynchronous=False):
        request_id = str(uuid.uuid4())
        self._input_queue.put(Task(request_id=request_id, data=data))
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

    def terminate_all_workers(self):
        '''Terminate all workers'''
        if len(self.wrk_ps) == 0:
            self.logger.info('No workers running')
        else:
            self.logger.info(
                'Received TERMINATE signal. All workers will be killed soon when they finish their jobs')

        for worker_info in self.wrk_ps:
            worker_info.ready_event.clear()

        terminate_workers = []
        for (i, worker_info) in enumerate(self.wrk_ps):
            is_terminated = worker_info.terminate_event.wait(20000)
            if is_terminated:
                self.wrk_ps.remove(worker_info)
                terminate_workers.append(worker_info)
        return f'Processes will be killed: {", ".join([str(worker_info.pid) for worker_info in terminate_workers])} and there is/are {len(self.wrk_ps)} left'

    def idle_all_workers(self):
        '''Idle all workers'''
        self.logger.info(
            'Received IDLE signal. All workers will idle until receiving resume signal')
        self.idle_event.set()
        return 'All workers are idling!'

    def resume_all_workers(self):
        self.logger.info(
            'Received RESUME signal. All workers will idle until receiving resume signal')
        self.idle_event.clear()
        return 'All workers are resuming!'

    def restart_all_workers(self):
        self.idle_all_workers()
        self.terminate_all_workers()
        self.logger.info('RESTART all workers')
        self._init_all_workers()
        self._wait_for_worker()
        self.resume_all_workers()
        return 'All workers are restarted!'

    def check_all_worker(self):
        '''Check status of all workers. Restart them if necessary'''
        pass

    def ping(self):
        self.logger.info("Ping!")
        return

    def _recheck_all_modules(self):
        if len(self.connection_apps) == 0 and not self.model_cls:
            self.logger.error("Nothing is running. STOP!")
            exit()

    def serve(self):
        self._init_all_workers()
        self._wait_for_worker()
        self._init_connections()
        self._recheck_all_modules()
        self._start_task_distributations()
