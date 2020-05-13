import zmq
import threading
from ..utils import get_logger, coloring_network_name


class ZMQAPI(threading.Thread):
    def __init__(self, funicorn_app, host, port_in, port_out, name='ZMQ', stat=None, threads=40,
                 timeout=1000, debug=False):
        threading.Thread.__init__(self, daemon=True)
        self.name = name
        self.funicorn_app = funicorn_app
        self.host = host
        self.port_in = port_in
        self.port_out = port_out
        self.stat = stat
        self.threads = threads
        self.debug = debug
        self.logger = get_logger(coloring_network_name(
            'RPC'), mode='debug' if debug else 'info')
        self.funicorn_app.register_connection(self)

    def init_connection(self, processor):
        server_in = self.init_input_connection(processor)
        server_out = self.init_output_connection(processor)
        return server_in, server_out

    def init_input_connection(self, processor):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(f"tcp://{self.host}:{self.port_in}")
        return socket

    def init_output_connection(self, processor):
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.bind(f"tcp://*:{self.port_out}")
        return socket

    def init_processor(self, handler):
        return handler

    def run(self):
        server_in, server_out = self.init_connection(self.funicorn_app)
        self.logger.info(
            f'Server is running at http://{self.host}:{self.port}')
        server.serve()
