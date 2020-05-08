import importlib
from funicorn import Funicorn

# hello = importlib.import_module('hello')
# hello.hello()

# importlib.import_module()

model_cls = getattr(importlib.import_module('test'), 'TestModel')
model = model_cls()
model.call()