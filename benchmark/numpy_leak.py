import numpy as np
import pickle
import os
import itertools
import psutil
import gc
import sys

print('NumPy version:', np.__version__, 'Python version:', sys.version)
for i in itertools.count():
    pickle.dumps(np.zeros(1024*1024))
    gc.collect()
    if i % 100 == 0:
        info = psutil.Process(os.getpid()).memory_info()
        print(f'vms={info.vms/1024/1024}MB rss={info.rss/1024/1024}MB')
