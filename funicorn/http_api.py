from flask import Flask, request, abort, jsonify
from waitress import serve
import threading
from PIL import Image
import numpy as np
import time
from collections import namedtuple
from http import HTTPStatus
import traceback

from funicorn.exceptions import NotSupportedInputFile, MaxFileSizeExeeded, InitializationError
from funicorn.utils import colored_network_name, check_all_ps_status
from funicorn.logger import get_logger


class HttpAPI(threading.Thread):
    def __init__(self, funicorn_app, host='0.0.0.0', port=5001, stat=None, threads=40, name='HTTP', timeout=1000, debug=False):
        threading.Thread.__init__(self, daemon=True)
        self.name = name
        self.host = host
        self.port = port
        self.threads = threads
        self.timeout = timeout
        self.flask_app = self.create_app()
        self.funicorn_app = funicorn_app
        self.stat = stat
        self.logger = get_logger(colored_network_name(
            'HTTP'), mode='debug' if debug else 'info')
        self.funicorn_app.register_connection(self)

    def init_exception(self, app):
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
        def not_found(error):
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
        return app

    def create_app(self):
        app = Flask(__name__)
        app = self.init_exception(app)

        def check_request_size(request, max_size=5 * 1024 * 1024):
            if request.content_length > max_size:
                raise MaxFileSizeExeeded(
                    "Input file size too large, limit is {:0.2f}MB".format(max_size/(1024**2)))

        def convert_bytes_to_img_arr(img_bytes):
            try:
                img = Image.open(img_bytes).convert("RGB")
                img = np.array(img, np.uint8)
                return img
            except:
                raise NotSupportedInputFile(
                    "Wrong input file type, only accept image")

        @app.route("/api/predict_img_bytes", methods=['POST'])
        def predict_img_bytes():
            final_res = []
            try:
                check_request_size(request)
                if 'img_bytes' in request.files:
                    img_bytes = request.files['img_bytes']
                    img = convert_bytes_to_img_arr(img_bytes)
                    results = self.funicorn_app.predict_img_bytes(img)
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

        @app.route('/api/predict_json', methods=['POST'])
        def predict_json():
            self.stat.increment('num_req')
            try:
                json = request.json
                result = self.funicorn_app.predict(json)
                self.stat.increment('num_res')
                self.logger.info(f'result is: {result}')
            except Exception as e:
                return jsonify({'result': e})
            else:
                return jsonify({'result': result})

        @app.route('/api/status', methods=['GET'])
        def status():
            try:
                resp = jsonify(self.stat.info)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/api/cli_status', methods=['GET'])
        def cli_status():
            try:
                resp = jsonify(self.stat.cli_info)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp


        @app.route('/api/resume', methods=['GET'])
        def resume_all_workers():
            try:
                ps_stt = self.funicorn_app.resume_all_workers()
                resp = jsonify(ps_stt)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/api/idle', methods=['GET'])
        def idle_all_workers():
            try:
                ps_stt = self.funicorn_app.idle_all_workers()
                resp = jsonify(ps_stt)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/api/terminate', methods=['GET'])
        def terminate_all_workers():
            try:
                ps_stt = self.funicorn_app.terminate_all_workers()
                resp = jsonify(ps_stt)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/api/restart', methods=['GET'])
        def restart_all_workers():
            try:
                ps_stt = self.funicorn_app.restart_all_workers()
                resp = jsonify(ps_stt)
                resp.status_code = HTTPStatus.OK
            except Exception as e:
                self.logger.error(traceback.format_exc())
                abort(HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return resp

        @app.route('/api/add_workers', methods=['GET'])
        def add_workers():
            try:
                num_workers = request.args.get('num_workers')
                gpu_devices = request.args.get('gpu_devices')
                gpu_devices = gpu_devices.split(',') \
                    if gpu_devices is not None else None
                ps_stt = self.funicorn_app.add_more_workers(
                    num_workers, gpu_devices)
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
        if self.funicorn_app is None:
            raise InitializationError(
                'Cannot start HTTP service. Funicorn app is required when start http service!')
        self.logger.info(
            f'Service is running on http://{self.host}:{self.port}')
        serve(app=self.flask_app,
              host=self.host, port=self.port,
              threads=self.threads, _quiet=True, backlog=1024)
