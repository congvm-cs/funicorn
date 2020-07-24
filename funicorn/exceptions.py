class LengthEqualtyError(Exception):
    pass

class DownloadURLError(Exception):
    status_code = 400
    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

class ImageEncodeError(Exception):
    pass


class MaxFileSizeExeeded(Exception):
    pass


class NotSupportedInputFile(Exception):
    pass

class InitializationError(Exception):
    pass

class CommandError(Exception):
    pass