''' Notes on multiprocessing in python 
'''
import os
import multiprocessing
import threading
from collections import namedtuple
import uuid
import time

from queue import Empty
from .api import Api
from .exceptions import LengthEqualtyError
from .logger import get_logger
from .stat import Statistic

RESULT_TIMEOUT = 0.001
DEFAULT_TIMEOUT = 500
WORKER_TIMEOUT = 20
DEFAULT_BATCH_TIMEOUT = 0.01

mp = multiprocessing.get_context("spawn")

Task = namedtuple('Task', ['request_id', 'data'])


class FunicornModel():
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
                 ready_event=None, destroy_event=None, model_init_args=None, model_init_kwargs=None):
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
        self._logger = get_logger()

    def _recv_request(self):
        raise NotImplementedError

    def _send_response(self, request_id, result):
        raise NotImplementedError

    def run_once(self):
        # Get data from queue
        batch = []
        for i in range(self.batch_size):
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

        assert len(results) == len(batch), LengthEqualtyError(
            'Length of result and batch must be equal')
        for (task, result) in zip(batch, results):
            self._send_response(task.request_id, result)

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
            task = self._input_queue.get(timeout=self.batch_timeout)
        except Empty:
            raise TimeoutError
        else:
            return task

    def _send_response(self, request_id, result):
        self._result_dict[request_id] = result

    def run(self, gpu_id=None, ready_event=None, destroy_event=None):
        ''' Init process parameters
            Every param initialized here are seperable among processes
        '''
        self._pid = os.getpid()
        self._model = self._model_cls(
            gpu_id, self._model_init_args, self._model_init_kwargs)
        if ready_event:
            ready_event.set()  # tell father process that init is finished
        if destroy_event:
            self._destroy_event = destroy_event

        # Run in loop
        super().run()


class Funicorn():
    def __init__(self, model_cls, num_workers=1, batch_size=1,
                 http_host='localhost', http_port=5000, gpu_devices=None,
                 model_init_args=None, model_init_kwargs=None):
        self._model_init_args = model_init_args or []
        self._model_init_kwargs = model_init_kwargs or {}
        self.http_host = http_host
        self.http_port = http_port
        self.gpu_devices = gpu_devices  # TODO
        self.num_workers = num_workers
        
        self._input_queue = mp.Queue()
        self._result_dict = mp.Manager().dict()
        self._wrk = Worker(model_cls, self._input_queue, self._result_dict,
                           batch_size=batch_size,
                           model_init_args=model_init_args, model_init_kwargs=model_init_kwargs)
        self.pid = os.getpid()
        self._init_stat()
        self._init_http_server()

        self.wrk_ps = []
        self.wrk_ready_events = []
        self.wrk_destroy_events = []
        self._init_all_workers()
        self._wait_for_worker_ready()

    def _init_stat(self):
        self.stat = Statistic(num_workers=self.num_workers)
        self.stat.update({'parent_pid': self.pid})

    def _init_http_server(self):
        self._restful = Api(funicorn=self, host=self.http_host,
                            port=self.http_port, stat=self.stat)
        self._restful.daemon = True
        self._restful.start()

    def _init_all_workers(self):
        for i in range(self.num_workers):
            ready_event = mp.Event()
            destroy_event = mp.Event()
            args = (ready_event, destroy_event)

            if self.gpu_devices is not None:
                gpu_id = self.gpu_devices[i % len(self.gpu_devices)]
            else:
                gpu_id = None
            args = (gpu_id, ready_event, destroy_event)
            wrk = mp.Process(target=self._wrk.run, args=args,
                             daemon=True,
                             name='funicorn-worker')
            wrk.start()
            # wrk.join()
            self.wrk_ps.append(wrk)
            self.wrk_ready_events.append(ready_event)
            self.wrk_destroy_events.append(destroy_event)

    def _wait_for_worker_ready(self, timeout=WORKER_TIMEOUT):
        # wait for all workers finishing init
        for (i, e) in enumerate(self.wrk_ready_events):
            # todo: select all events with timeout
            is_ready = e.wait(timeout)
            print("gpu worker:%d ready state: %s" % (i, is_ready))

    def predict(self, data, timeout=DEFAULT_TIMEOUT, asynchronous=False):
        request_id = str(uuid.uuid4())
        self._input_queue.put(Task(request_id=request_id, data=data))
        if asynchronous:
            return request_id
        else:
            return self.get_result(request_id, timeout=timeout)

    def get_result(self, request_id, timeout=DEFAULT_TIMEOUT):
        ret = None
        start_time = time.time()
        while True:
            ret = self._result_dict.get(request_id, None)
            if ret is not None:
                break
            if time.time() - start_time > timeout:
                break
            time.sleep(RESULT_TIMEOUT)
        return ret

    def destroy_all_worker(self):
        '''Destroy all workers'''
        for destroy_event in self.wrk_destroy_events:
            destroy_event.set()

    def check_all_worker(self):
        '''Check status of all workers. Restart them if necessary'''
        pass

    def serve(self):
        while True:
            time.sleep(300)
        # for wrk in self.wrk_ps:
        #     wrk.join()


if __name__ == "__main__":
    binding = Funicorn(FunicornModel, num_workers=3,
                       batch_size=2, model_init_args=['model_path'])
    binding.serve()
