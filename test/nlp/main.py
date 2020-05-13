from funicorn import Funicorn
from funicorn.thriftcorn.rpc_api import ThriftAPI
from funicorn.utils import coloring_funicorn_name, coloring_network_name, get_logger
import random
from nlpservice.nlpservice import NLPService
from thrift.transport import TTransport, TSocket, TSSLSocket
from thrift.protocol.TBinaryProtocol import TBinaryProtocol


class NLPThriftApi(ThriftAPI):
    def __init__(self, *args, **kwargs):
        ThriftAPI.__init__(self, name='NLPThriftApi', *args, **kwargs)
        self.logger.name = coloring_network_name('NLPThriftApi')

    def init_processor(self, handler):
        processor = NLPService.Processor(handler)
        return processor


class HandlerA():
    def __init__(self):
        # Init Hanlder
        self.logger = get_logger('HandlerA')

    def nlp_encode(self, text):
        # encode data
        text = text[0]
        # self.logger.info('Encode: %s' % text)
        return [text + "-a"]

    def ping(self):
        pass


class HandlerB():
    def __init__(self):
        # Init Hanlder
        self.logger = get_logger('HandlerB')

    def nlp_encode(self, text):
        # encode data
        text = text[0]
        # self.logger.info('Encode: %s' % text)
        return [text + "-b"]

    def ping(self):
        pass


class WGHandler():
    def __init__(self, server_host, server_port, set_return=False):
        socket = TSocket.TSocket(server_host, server_port)
        self.transport = TTransport.TFramedTransport(socket)
        self.protocol = TBinaryProtocol(self.transport)
        self.client = NLPService.Client(self.protocol)
        self.set_return = set_return

    def nlp_encode(self, text):
        text = text[0]
        self.transport.open()
        try:
            ret = self.client.nlp_encode(text)
            if self.set_return:
                return [ret]
            else:
                return None
        except Exception as e:
            print(e)
        finally:
            self.transport.close()

    def ping(self):
        self.transport.open()
        try:
            self.client.ping()
        except Exception as e:
            print(e)
        finally:
            self.transport.close()


class NLP_A(Funicorn):
    '''Customize Funicorn Service to work as waygate'''

    def __init__(self, *args, **kwargs):
        Funicorn.__init__(self, *args, **kwargs)
        self.logger.name = coloring_funicorn_name('NLP_A')

    def nlp_encode(self, text):
        '''Distribute text to other entries'''
        result = self.put_task(text, func_name='nlp_encode')
        return result


class NLP_B(Funicorn):
    '''Customize Funicorn Service to work as waygate'''

    def __init__(self, *args, **kwargs):
        Funicorn.__init__(self, *args, **kwargs)
        self.logger.name = coloring_funicorn_name('NLP_B')

    def nlp_encode(self, text):
        result = self.put_task(text, func_name='nlp_encode')
        return result


class NLPGateWay(Funicorn):
    '''Customize Funicorn Service to work as waygate'''

    def __init__(self, *args, **kwargs):
        Funicorn.__init__(self, *args, **kwargs)
        self.logger.name = coloring_funicorn_name('NLPGateWay')

    def nlp_encode(self, text):
        '''Distribute text to other entries'''
        result = self.put_task(text, func_name='nlp_encode')
        return result
