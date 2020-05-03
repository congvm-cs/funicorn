from flask import Flask, request, abort, jsonify
from waitress import serve
import threading
from exceptions import NotSupportedInputFile, MaxFileSizeExeeded
from PIL import Image
import numpy as np
import time
from collections import namedtuple


class Api(threading.Thread):
    def __init__(self, funicorn, host, port, stat=None, threads=10, timeout=1000):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.threads = threads
        self.timeout = timeout
        self.app = self.create_restful()
        self.funicorn = funicorn
        self.stat = stat

    def create_restful(self):
        app = Flask(__name__)

        def check_request_size(request, max_size=5 * 1024 * 1024):
            if request.content_length > max_size:
                raise MaxFileSizeExeeded(
                    "Input file size too large, limit is {:0.2f}MB".format(max_size/(1024**2)))

        def convert_bytes_to_pil_image(img_bytes):
            try:
                img = Image.open(img_bytes).convert("RGB")
                img = np.array(img)
                return img
            except:
                raise NotSupportedInputFile(
                    "Wrong input file type, only accept image")

        @app.errorhandler(413)
        def max_file_size_exeeded(error):
            resp = jsonify({
                "error_code": 413,
                "error_message": 'Request Size Exeeded',
                "data": []
            })
            resp.status_code = 413
            return resp

        @app.errorhandler(400)
        def wrong_request_params(error):
            resp = jsonify({
                "error_code": 400,
                "error_message": "Wrong request parameter",
                "data": []
            })
            resp.status_code = 400
            return resp

        @app.errorhandler(500)
        def internal_server_error(error):
            resp = jsonify({
                "error_code": 500,
                "error_message": "Internal server error",
                "data": []
            })
            resp.status_code = 500
            return resp

        @app.route("/predict_img_bytes", methods=['POST'])
        def predict_img_bytes():
            final_res = []
            try:
                check_request_size(request)
                if 'img_bytes' in request.files:
                    img_bytes = request.files['img_bytes']  # .read()
                    img = convert_bytes_to_pil_image(img_bytes)
                    results = self.funicorn.predict(img)
                    if results is not None:
                        final_res = results
                    else:
                        abort(500)
                    final_res = final_res if len(final_res) != 0 else []
                    resp = jsonify({
                        "error_code": 0,
                        "error_message": "Successful.",
                        "data": final_res
                    })
                    resp.status_code = 200
                    return resp
                else:
                    abort(400)
            except NotSupportedInputFile as e:
                abort(400)
            except MaxFileSizeExeeded as e:
                abort(403)
            except Exception as e:
                abort(500)

        @app.route('/predict_json', methods=['POST'])
        def predict_json():
            self.stat.increment('num_req')
            try:
                json = request.json
                result = self.funicorn.predict(json)
                self.stat.increment('num_res')
                print('result is', result)
            except Exception as e:
                return jsonify({'result': e})
            else:
                return jsonify({'result': result})

        @app.route('/statistics', methods=['GET', 'POST'])
        def statistics():
            try:
                resp = jsonify(self.stat.info)
                resp.status_code = 200
            except Exception as e:
                print(e)
                abort(500)
            else:
                return resp
        return app

    def run(self):
        print(self.host, self.port)
        serve(app=self.app, host=self.host, port=self.port,
              threads=self.threads)
