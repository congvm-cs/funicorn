import os
import multiprocessing as mp
from random import randint
import threading
from collections import namedtuple
import uuid
import time
import json
import traceback
from queue import Empty
from queue import Queue
from .exceptions import LengthEqualtyError
from .utils import img_bytes_to_img_arr, get_args_from_class
from .logger import get_logger
from .utils import colored_worker_name, colored_funicorn_name, colored_network_name
from .mqueue import Queue as MQueue
import pickle

MAX_QUEUE_SIZE = 1000
RESULT_TIMEOUT = 0.0001
DEFAULT_TIMEOUT = 500
WORKER_TIMEOUT = 5
DEFAULT_BATCH_TIMEOUT = 0.01


__all__ = ['Funicorn']
Task = namedtuple('Task', ['request_id', 'data'])
WorkerInfo = namedtuple('WorkerInfo', ['wrk', 'wrk_id', 'pid', 'gpu_id',
                                       'ps_status', 'queue',
                                       'ready_event',
                                       'terminate_event'])


class BaseWorker():
    def __init__(self, model_cls, result_dict=None,
                 batch_size=1, batch_timeout=DEFAULT_BATCH_TIMEOUT,
                 ready_event=None, terminate_event=None, model_init_kwargs=None,
                 debug=False):

        self._worker_id = None
        self._model_init_kwargs = model_init_kwargs or {}
        self._model_cls = model_cls
        self._wrk_queue = None
        self._result_dict = result_dict
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._ready_event = ready_event
        self._terminate_event = terminate_event
        self._pid = os.getpid()
        self._model = None
        self._debug = debug
        self.logger = get_logger(colored_worker_name(
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
            '`results` must be a list but receive `{}` which is not valid'.format(results))
        assert len(results) == len(batch), LengthEqualtyError(
            'Length of result and batch must be equal')
        for (task, result) in zip(batch, results):
            self._send_response(task.request_id, result)
        self.logger.debug(
            f'Inference with batch_size: {batch_size} - inference-time: {time.time() - start_time} - model-time: {end_model_time - start_model_time}')
        # Return None or something to notify number of data in queue
        return batch_size

    def run(self):
        '''Loop into a queue'''
        while True:
            try:
                self.logger.debug('Process new data!')
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
            task = self._wrk_queue.get(timeout=self.batch_timeout)
        except Empty:
            raise TimeoutError
        else:
            return task

    def _send_response(self, request_id, result):
        self._result_dict[request_id] = result

    def run(self, worker_id=None, gpu_id=None, ready_event=None, terminate_event=None, wrk_queue=None):
        ''' Init process parameters
            Every param initialized here are seperable among processes
        '''
        self.logger = get_logger(
            colored_worker_name(f'WORKER-{worker_id}'), mode='debug' if self._debug else 'info')
        self._init_environ()
        self._wrk_queue = wrk_queue
        self._worker_id = worker_id
        self._pid = os.getpid()
        worker_args = get_args_from_class(self._model_cls)
        if 'gpu_id' in worker_args:
            self._model_init_kwargs.update({'gpu_id': gpu_id})
        device = f'GPU-{gpu_id}' if gpu_id else 'CPU'
        self.logger.info(f'Initializing Worker in {device}')
        self._model = self._model_cls(**self._model_init_kwargs)

        if ready_event:
            self._ready_event = ready_event
            self._ready_event.set()  # tell father process that init is finished

        if terminate_event:
            self._terminate_event = terminate_event

        super().run()


class Funicorn():
    '''Lightweight Deep Learning Inference Framework'''

    def __init__(self, model_cls, num_workers=1, batch_size=1, batch_timeout=10,
                 max_queue_size=1000,
                 gpu_devices=None,
                 model_init_kwargs=None, debug=False, timeout=5000):
        self.model_cls = model_cls
        self.logger = get_logger(
            colored_funicorn_name(), mode='debug' if debug else 'info')
        self._model_init_kwargs = model_init_kwargs or {}
        self.timeout = timeout
        self.debug = debug
        self._lock = threading.Lock()
        self.gpu_devices = gpu_devices
        self.num_workers = num_workers

        self._input_queue = MQueue()
        self._result_dict = mp.Manager().dict()
        if batch_size == 1:
            batch_timeout = None
        elif batch_timeout is not None:
            batch_timeout = batch_timeout/1000
        self._wrk = Worker(self.model_cls, self._result_dict,
                           batch_size=batch_size, batch_timeout=batch_timeout,
                           model_init_kwargs=model_init_kwargs, debug=self.debug)

        self.pid = os.getpid()
        # self._init_stat()
        self.idle_event = mp.Event()
        self.wrk_ps = []
        self.connection_apps = {}

    def register_connection(self, connection):
        self.logger.info(
            f'Register {colored_network_name(connection.name)} connection')
        self.connection_apps[connection.name] = connection

    def get_worker_pids(self):
        return [wrk.pid for wrk in self.wrk_ps]

    def _init_connections(self):
        for conn_name, conn in self.connection_apps.items():
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
                self.add_worker(self.num_workers, self.gpu_devices)

    def _wait_for_worker(self, timeout=WORKER_TIMEOUT):
        # wait for all workers finishing init
        for (i, worker_info) in enumerate(self.wrk_ps):
            # todo: select all events with timeout
            is_ready = worker_info.ready_event.wait(timeout)
            self.logger.info(
                f"{colored_worker_name(f'WORKER-{worker_info.wrk_id}')} ready state: {is_ready}")
            if not is_ready:
                self.logger.error(
                    f"{colored_worker_name(f'WORKER-{worker_info.wrk_id}')} cannot start.")
                # exit()

    def _start_task_distributations(self):
        '''Distribute task to wrk_queue'''
        while True:
            task = self._input_queue.get()
            self.logger.debug(
                f'Get data from input queue: {self._input_queue}')
            with self._lock:
                input_queue = self.wrk_ps[randint(
                    0, len(self.wrk_ps) - 1)].queue
            input_queue.put(task)

    def predict(self, data, asynchronous=False):
        '''Main function to predict data'''
        request_id = str(uuid.uuid4())
        self._input_queue.put(Task(request_id=request_id, data=data))
        self.logger.info(
            f'Received data with request_id: {request_id}')
        if asynchronous:
            return request_id
        else:
            return self.get_result(request_id)

    @property
    def input_queue(self):
        self.logger.info(f'Get input queue: {self._input_queue}')
        return self._input_queue

    @property
    def result_dict(self):
        return self._result_dict

    def get_result(self, request_id):
        ret = None
        while True:
            ret = self._result_dict.pop(request_id, None)
            if ret is not None:
                break
            time.sleep(RESULT_TIMEOUT)
        self.logger.debug(f'Sent result of request_id to client: {request_id}')
        return ret

    def add_more_workers(self, num_workers, gpu_devices):
        num_workers = int(num_workers)
        device = 'CPU' if gpu_devices is None else gpu_devices
        self.logger.info(f'Add {num_workers} workers in {device}')
        self.num_workers += num_workers
        self.add_worker(num_workers, gpu_devices)
        return 'Added more workers!'

    def add_worker(self, num_workers, gpu_devices):
        for idx in range(num_workers):
            ready_event = mp.Event()
            terminate_event = mp.Event()
            args = (ready_event, terminate_event)
            if gpu_devices is not None:
                gpu_id = gpu_devices[idx % len(gpu_devices)]
            else:
                gpu_id = None
            wrk_queue = MQueue()  # mp.Queue()
            worker_id = randint(0, 999999)
            args = (worker_id, gpu_id, ready_event,
                    terminate_event, wrk_queue)
            wrk = mp.Process(target=self._wrk.run, args=args,
                             daemon=True,
                             name=f'funicorn-worker-{worker_id}')
            wrk.start()
            worker_info = WorkerInfo(wrk=wrk,
                                     wrk_id=worker_id,
                                     pid=wrk.pid,
                                     gpu_id=gpu_id,
                                     ps_status='unknown',
                                     queue=wrk_queue,
                                     ready_event=ready_event,
                                     terminate_event=terminate_event)
            with self._lock:
                self.wrk_ps.append(worker_info)

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

    def _recheck_all_modules(self):
        if len(self.connection_apps) == 0 and not self.model_cls:
            self.logger.error("Nothing is running. STOP!")
            exit()

    def _serve(self):
        try:
            self._init_all_workers()
            self._wait_for_worker()
            self._init_connections()
            self._recheck_all_modules()
            self._start_task_distributations()
        except KeyboardInterrupt:
            exit()
        except Exception as e:
            self.logger.error(traceback.format_exc())

    def serve(self, run_in_background=False):
        if run_in_background:
            t = threading.Thread(target=self._serve, daemon=True)
            t.start()
        else:
            self._serve()
