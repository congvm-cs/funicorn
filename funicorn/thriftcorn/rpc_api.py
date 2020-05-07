from thrift.server import TNonblockingServer
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport
from .FunicornService import Processor
import threading
from ..utils import get_logger

class ThriftAPI(threading.Thread):
    def __init__(self, funicorn, host, port, stat=None, threads=40, timeout=1000, debug=False, daemon=True):
        self.funicorn = funicorn
        self.host = host
        self.port = port
        self.stat = stat
        self.threads = threads
        self.debug = debug
        self.logger = get_logger(mode='debug' if debug else 'info')
        threading.Thread.__init__(self, daemon=daemon)
        
    def run(self):
        self.logger.info(f'RPC Server is starting at {self.host}:{self.port}')
        processors = Processor(self.funicorn)
        socket = TSocket.TServerSocket(host=self.host, port=self.port)
        prot_fac = TBinaryProtocol.TBinaryProtocolFactory()
        server = TNonblockingServer.TNonblockingServer(processor=processors, 
                                              lsocket=socket, 
                                              inputProtocolFactory=prot_fac,
                                              threads=self.threads)        
        server.serve()