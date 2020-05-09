from funicorn import Funicorn
from funicorn.thriftcorn.rpc_api import ThriftAPI
from funicorn.utils import coloring_funicorn_name, coloring_network_name
import random
from nlpservice.nlpservice import NLPService


class NLPThriftApi(ThriftAPI):
    def __init__(self, *args, **kwargs):
        ThriftAPI.__init__(self, *args, **kwargs)
        self.logger.name = coloring_network_name('NLPThriftApi')

    def init_processor(self, handler):
        self.logger.info('Initialize NLPThriftApi')
        processor = NLPService.Processor(handler)
        return processor


class NLPGateWay(Funicorn):
    '''Customize Funicorn Service to work as waygate'''

    def __init__(self, *args, **kwargs):
        Funicorn.__init__(self, *args, **kwargs)
        self.entries = [
            'Kiki-Handler-V1', 
            'Kiki-Handler-V2'
        ]
        self.logger.name = coloring_funicorn_name('NLPGateWay')

    def get_entries(self, idx):
        return self.entries[idx]

    # Override init_rpc_server to use NLPApi-Thrift
    def init_rpc_server(self, funicorn_app, host, port,
                        stat=None, threads=40,
                        timeout=1000, debug=False):
        return NLPThriftApi(funicorn_app, host, port, stat,
                            threads, timeout, debug)

    def nlp_encode(self, text):
        '''Distribute text to other entries'''

        # Logic to distribute
        entry = self.get_entries(random.randint(0, len(self.entries) - 1))
        self.logger.info(f'Send {text} to {entry} and wait the result')
        # Maybe send to other Funicorn Service Entry

        # Then wait for the result
        # In this case we return a dummy result
        self.logger.info(f'Receive {text} from {entry}')
        result = text
        return result
