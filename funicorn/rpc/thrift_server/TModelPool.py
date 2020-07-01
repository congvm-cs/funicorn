
import asyncio
from threading import Thread
import logging
import select
import socket
import struct
import threading

from collections import deque
from six.moves import queue

from thrift.transport import TTransport
from thrift.protocol.TBinaryProtocol import TBinaryProtocolFactory
from multiprocessing import Process, Queue
import traceback
from thrift.protocol import TBinaryProtocol
from thrift.transport.TTransport import TTransportException
import random

__all__ = ['TModelPoolServer']

logger = logging.getLogger(__name__)


WAIT_LEN = 0
WAIT_MESSAGE = 1
WAIT_PROCESS = 2
SEND_ANSWER = 3
CLOSED = 4


class ThreadWkr(Thread):
    def __init__(self, *args, **kwargs):
        super(ThreadWkr, self).__init__()
        self._handler_cls = kwargs.get('handler_cls')
        self._processor_cls = kwargs.get('processor_cls')
        self._tasks_queue = kwargs.get('tasks_queue')
        self._callback_queue = kwargs.get('callback_queue')
        self._model_config = kwargs.get('model_config')
        self._worker_id = kwargs.get('worker_id')
        print("Start Thread Worker:", self._worker_id)

    def run(self):
        """Loop getting clients from the shared queue and process them"""
        # Init Handler and Processor
        if len(self._model_config) == 0:
            self._handler = self._handler_cls()
        else:
            self._handler = self._handler_cls(**self._model_config)
        self._processor = self._processor_cls(self._handler)

        while True:
            try:
                iprot, oprot, otrans, rsocket_fileno = self._tasks_queue.get()
                self._processor.process(iprot, oprot)
                self._callback_queue.put({"ok_all": True,
                                          "message": otrans.getvalue(),
                                          "rsocket_fileno": rsocket_fileno})
            except Exception as e:
                print(traceback.format_exc())
                self._callback_queue.put({"ok_all": False,
                                          "message": b"",
                                          "rsocket_fileno": rsocket_fileno})


class ProcessWrk(Process):
    def __init__(self, *args, **kwargs):
        super(ProcessWrk, self).__init__()
        self._handler_cls = kwargs.get('handler_cls')
        self._processor_cls = kwargs.get('processor_cls')
        self._tasks_queue = kwargs.get('tasks_queue')
        self._callback_queue = kwargs.get('callback_queue')
        self._model_config = kwargs.get('model_config')
        self._worker_id = kwargs.get('worker_id')
        # print("Start Process Worker:", self._worker_id)

    def run(self):
        """Loop getting clients from the shared queue and process them"""
        # Init Handler and Processor
        if len(self._model_config) == 0:
            self._handler = self._handler_cls()
        else:
            self._handler = self._handler_cls(**self._model_config)
        self._processor = self._processor_cls(self._handler)

        while True:
            try:
                iprot, oprot, otrans, rsocket_fileno = self._tasks_queue.get()
                self._processor.process(iprot, oprot)
                self._callback_queue.put({"ok_all": True,
                                          "message": otrans.getvalue(),
                                          "rsocket_fileno": rsocket_fileno})
            except Exception as e:
                print(traceback.format_exc())
                self._callback_queue.put({"ok_all": False,
                                          "message": b"",
                                          "rsocket_fileno": rsocket_fileno})


def locked(func):
    """Decorator which locks self.lock."""

    def nested(self, *args, **kwargs):
        self.lock.acquire()
        try:
            return func(self, *args, **kwargs)
        finally:
            self.lock.release()
    return nested


def socket_exception(func):
    """Decorator close object on socket.error."""

    def read(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except socket.error:
            logger.debug('ignoring socket exception', exc_info=True)
            self.close()
    return read


class Message(object):
    def __init__(self, offset, len_, header):
        self.offset = offset
        self.len = len_
        self.buffer = None
        self.is_header = header

    @property
    def end(self):
        return self.offset + self.len


class ConnectionStateChanger(threading.Thread):
    def __init__(self, queue, clients):
        threading.Thread.__init__(self)
        self.callback_queue = queue
        self.clients = clients

    def run(self):
        while True:
            callback_state = self.callback_queue.get()
            connection = self.clients[callback_state['rsocket_fileno']]
            connection.ready(
                callback_state['ok_all'], callback_state['message'])


class ConnectionStateChangerAsyncIo():
    def __init__(self, queue, clients):
        self.callback_queue = queue
        self.clients = clients

    def _asyncio_start(self):
        while True:
            callback_state = self.callback_queue.get()
            connection = self.clients[callback_state['rsocket_fileno']]
            connection.ready(
                callback_state['ok_all'], callback_state['message'])

    def start(self):
        self.loop = asyncio.get_event_loop()
        self.loop.run_in_executor(executor=None, func=self._asyncio_start)


class Connection(object):
    """Basic class is represented connection.

    It can be in state:
        WAIT_LEN --- connection is reading request len.
        WAIT_MESSAGE --- connection is reading request.
        WAIT_PROCESS --- connection has just read whole request and
                         waits for call ready routine.
        SEND_ANSWER --- connection is sending answer string (including length
                        of answer).
        CLOSED --- socket was closed and connection should be deleted.
    """

    def __init__(self, new_socket, wake_up):
        self.socket = new_socket
        self.socket.setblocking(False)
        self.status = WAIT_LEN
        self.len = 0
        self.received = deque()
        self._reading = Message(0, 4, True)
        self._rbuf = b''
        self._wbuf = b''
        self.lock = threading.Lock()
        self.wake_up = wake_up
        self.remaining = False

    @socket_exception
    def read(self):
        """Reads data from stream and switch state."""
        assert self.status in (WAIT_LEN, WAIT_MESSAGE)
        assert not self.received
        buf_size = 8192
        first = True
        done = False
        while not done:
            read = self.socket.recv(buf_size)
            rlen = len(read)
            done = rlen < buf_size
            self._rbuf += read
            if first and rlen == 0:
                if self.status != WAIT_LEN or self._rbuf:
                    logger.error('could not read frame from socket')
                else:
                    logger.debug(
                        'read zero length. client might have disconnected')
                self.close()
            while len(self._rbuf) >= self._reading.end:
                if self._reading.is_header:
                    mlen, = struct.unpack('!i', self._rbuf[:4])
                    self._reading = Message(self._reading.end, mlen, False)
                    self.status = WAIT_MESSAGE
                else:
                    self._reading.buffer = self._rbuf
                    self.received.append(self._reading)
                    self._rbuf = self._rbuf[self._reading.end:]
                    self._reading = Message(0, 4, True)
                    done = True
            first = False
            if self.received:
                self.status = WAIT_PROCESS
                break
        self.remaining = not done

    @socket_exception
    def write(self):
        """Writes data from socket and switch state."""
        assert self.status == SEND_ANSWER
        sent = self.socket.send(self._wbuf)
        if sent == len(self._wbuf):
            self.status = WAIT_LEN
            self._wbuf = b''
            self.len = 0
        else:
            self._wbuf = self._wbuf[sent:]

    @locked
    def ready(self, all_ok, message):
        """Callback function for switching state and waking up main thread.
        This function is the only function witch can be called asynchronous.
        The ready can switch Connection to three states:
            WAIT_LEN if request was oneway.
            SEND_ANSWER if request was processed in normal way.
            CLOSED if request throws unexpected exception.

        The one wakes up main thread.
        """
        assert self.status == WAIT_PROCESS
        if not all_ok:
            self.close()
            self.wake_up()
            return
        self.len = 0
        if len(message) == 0:
            # it was a oneway request, do not write answer
            self._wbuf = b''
            self.status = WAIT_LEN
        else:
            self._wbuf = struct.pack('!i', len(message)) + message
            self.status = SEND_ANSWER
        self.wake_up()

    @locked
    def is_writeable(self):
        """Return True if connection should be added to write list of select"""
        return self.status == SEND_ANSWER

    @locked
    def is_readable(self):
        """Return True if connection should be added to read list of select"""
        return self.status in (WAIT_LEN, WAIT_MESSAGE)

    @locked
    def is_closed(self):
        """Returns True if connection is closed."""
        return self.status == CLOSED

    def fileno(self):
        """Returns the file descriptor of the associated socket."""
        return self.socket.fileno()

    def close(self):
        """Closes connection"""
        self.status = CLOSED
        self.socket.close()


class TModelPoolServer(object):
    """TModelPoolServer is based on Non-blocking server."""

    def __init__(self, handler_cls, processor_cls, tsocket, protocol_factory, worker_type='process', *args, **kwargs):
        assert worker_type in ['process', 'thread']
        self.worker_type = worker_type
        self.handler_cls = handler_cls
        self.processor_cls = processor_cls
        self.tsocket = tsocket
        self.transport_factory = kwargs.get(
            'transport_factory')  # The default is FrameTransport
        self.protocol_factory = protocol_factory
        self.list_model_config = kwargs.get("list_model_config", [])
        self.clients = {}  # Store client connection
        self.callback_queue = Queue()
        self._read, self._write = socket.socketpair()
        self.list_task_queue = []  # Distribute task to Worker
        self.workers = []

        self.prepared = False
        self._stop = False

    def prepare(self):
        """Prepares server for serve requests."""
        if self.prepared:
            return
        self.tsocket.listen()

        if self.worker_type == 'process':
            self.worker_cls = ProcessWrk
        else:
            self.worker_cls = ThreadWkr

        for wrk_id, model_config in enumerate(self.list_model_config):
            tasks_queue = Queue()
            self.list_task_queue.append(tasks_queue)
            try:
                wrk = self.worker_cls(handler_cls=self.handler_cls,
                                      processor_cls=self.processor_cls,
                                      connection_queue=tasks_queue,
                                      model_config=model_config,
                                      callback_queue=self.callback_queue,
                                      tasks_queue=tasks_queue,
                                      worker_id=wrk_id)
                wrk.daemon = True
                wrk.start()
                self.workers.append(wrk)
            except Exception as x:
                print(traceback.format_exc())

        result_dist = ConnectionStateChanger(self.callback_queue, self.clients)
        result_dist.setDaemon(True)
        result_dist.start()
        self.prepared = True

    def wake_up(self):
        """Wake up main thread.

        The server usually waits in select call in we should terminate one.
        The simplest way is using socketpair.

        Select always wait to read from the first socket of socketpair.

        In this case, we can just write anything to the second socket from
        socketpair.
        """
        self._write.send(b'1')

    def stop(self):
        """Stop the server.

        This method causes the serve() method to return.  stop() may be invoked
        from within your handler, or from another thread.

        After stop() is called, serve() will return but the server will still
        be listening on the socket.  serve() may then be called again to resume
        processing requests.  Alternatively, close() may be called after
        serve() returns to close the server socket and shutdown all worker
        threads.
        """
        self._stop = True
        self.wake_up()

    def _select(self):
        """Does select on open connections."""
        readable = [self.tsocket.handle.fileno(), self._read.fileno()]
        writable = []
        remaining = []
        for i, connection in list(self.clients.items()):
            if connection.is_readable():
                readable.append(connection.fileno())
                if connection.remaining or connection.received:
                    remaining.append(connection.fileno())
            if connection.is_writeable():
                writable.append(connection.fileno())
            if connection.is_closed():
                del self.clients[i]
        if remaining:
            return remaining, [], [], False
        else:
            return select.select(readable, writable, readable) + (True,)

    def handle(self):
        """Handle requests.

        WARNING! You must call prepare() BEFORE calling handle()
        """
        assert self.prepared, "You have to call prepare before handle"
        rset, wset, xset, selected = self._select()
        for readable in rset:
            if readable == self._read.fileno():
                # don't care i just need to clean readable flag
                self._read.recv(1024)
            elif readable == self.tsocket.handle.fileno():
                try:
                    client = self.tsocket.accept()
                    if client:
                        self.clients[client.handle.fileno()] = Connection(client.handle,
                                                                          self.wake_up)
                except socket.error:
                    logger.debug('error while accepting', exc_info=True)
            else:
                connection = self.clients[readable]
                if selected:
                    connection.read()
                if connection.received:
                    connection.status = WAIT_PROCESS
                    msg = connection.received.popleft()
                    itransport = TTransport.TMemoryBuffer(
                        msg.buffer, msg.offset)
                    otransport = TTransport.TMemoryBuffer()
                    iprot = self.protocol_factory.getProtocol(itransport)
                    oprot = self.protocol_factory.getProtocol(otransport)

                    rand_idx = random.randint(0, len(self.list_task_queue) - 1)
                    self.list_task_queue[rand_idx].put(
                        [iprot, oprot, otransport, readable])

        for writeable in wset:
            self.clients[writeable].write()
        for oob in xset:
            self.clients[oob].close()
            del self.clients[oob]

    def serve(self):
        """Serve requests.
        Serve requests forever, or until stop() is called.
        """
        self._stop = False
        self.prepare()
        while not self._stop:
            self.handle()
