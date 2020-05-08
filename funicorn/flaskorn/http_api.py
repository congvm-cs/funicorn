from flask import Flask, request, abort, jsonify
from waitress import serve
import threading
from PIL import Image
import numpy as np
import time
from collections import namedtuple
from http import HTTPStatus
import traceback


from ..exceptions import NotSupportedInputFile, MaxFileSizeExeeded
from ..utils import get_logger
from ..utils import check_all_ps_status

class HttpApi(threading.Thread):
    def __init__(self, funicorn, host, port, stat=None, threads=40, timeout=1000, debug=False, daemon=True):
        threading.Thread.__init__(self, daemon=daemon)
        self.host = host
        self.port = port
        self.threads = threads
        self.timeout = timeout
        self.app = self.create_app()
        self.funicorn = funicorn
        self.stat = stat
        self.logger = get_logger(mode='debug' if debug else 'info')

    def create_app(self):
        app = Flask(__name__)

        def check_request_size(request, max_size=5 * 1024 * 1024):
            if request.content_length > max_size:
                raise MaxFileSizeExeeded(
                    "Input file size too large, limit is {:0.2f}MB".format(max_size/(1024**2)))

        def convert_bytes_to_img_arr(img_bytes):
            try:
                img = Image.open(img_bytes).convert("RGB")
                img = np.array(img)
                return img
            except:
                raise NotSupportedInputFile(
                    "Wrong input file type, only accept image")

        @app.errorhandler(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        def max_file_size_exeeded(error):
            resp = jsonify({
                "error_code": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "error_message": 'Request Size Exeeded',
                "data": []
            })
            resp.status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            return resp

        @app.errorhandler(HTTPStatus.NOT_FOUND)
        def wrong_request_params(error):
            resp = jsonify({
                "error_code": HTTPStatus.NOT_FOUND,
                "error_message": "Api Not Found",
                "data": []
            })
            resp.status_code = HTTPStatus.NOT_FOUND
            return resp

        @app.errorhandler(HTTPStatus.BAD_REQUEST)
        def wrong_request_params(error):
            resp = jsonify({
                "error_code": HTTPStatus.BAD_REQUEST,
                "error_message": "Wrong request parameter",
                "data": []
            })
            resp.status_code = HTTPStatus.BAD_REQUEST
            return resp

        @app.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR)
        def internal_server_error(error):
            resp = jsonify({
                "error_code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "error_message": "Internal server error",
                "data": []
            })
            resp.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            return resp

        @app.route("/predict_img_bytes", methods=['POST'])
        def predict_img_bytes():
            final_res = []
            try:
                check_request_size(request)
                if 'img_bytes' in request.files:
                    img_bytes = request.files['img_bytes']
                    img = convert_bytes_to_img_arr(img_bytes)
                    results = self.funicorn.predict_img_bytes(img)
                    if results is not None:
                        final_res = results
                    else:
                        abort(HTTPStatus.INTERNAL_SERVER_ERROR)
                    final_res = final_res if len(final_res) != 0 else []
                    resp = jsonify({
                        "error_code": 0,
                        "error_message": "Successful.",
                        "data": final_res
                    })
                    resp.status_code = HTTPStatus.OK
                    return resp
                else:
                    abort(HTTPStatus.BAD_REQUEST)
            except NotSupportedInputFile as e:
                abort(HTTPStatus.BAD_REQUEST)
            except MaxFileSizeExeeded as e:
                abort(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)

        @app.route('/predict_json', methods=['POST'])
        def predict_json():
            self.stat.increment('num_req')
            try:
                json = request.json
                result = self.funicorn.predict(json)
                self.stat.increment('num_res')
                self.logger.info(f'result is: {result}')
            except Exception as e:
                return jsonify({'result': e})
            else:
                return jsonify({'result': result})

        @app.route('/statistics', methods=['GET', 'POST'])
        def statistics():
            try:
                resp = jsonify(self.stat.info)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/status', methods=['GET'])
        def check_process_status():
            try:
                worker_pids = self.funicorn.get_worker_pids()
                ps_stt = check_all_ps_status(worker_pids)
                resp = jsonify(ps_stt)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        # End of API
        return app

    # https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html#arguments
    def run(self):
        self.logger.info(
            f'HTTP Service is running on http://{self.host}:{self.port}')
        serve(app=self.app,
              host=self.host, port=self.port,
              threads=self.threads, _quiet=True, backlog=1024)
