import multiprocessing as mp
import numpy as np
from time import time
import sys
import fmq

q1 = mp.Queue(10)
q2 = fmq.Queue(10)

# a = np.zeros((100, 256, 256, 3))
a = np.zeros((1024, 720, 3), dtype=np.uint8)
a_size = sys.getsizeof(a)
print('%d bytes, %dKB, %dMB' % (a_size, a_size/1024, a_size/1024/1024))


def get_and_print(q, name):
    # mp queue get
    for i in range(5):
        st = time()
        print('Get item')
        b = q.get()
        print(f'{name} get() a time', time() - st)


# def get_and_print_fmq(q):
#     # fmq queue get
#     for i in range(5):
#         st = time()
#         b = q.get()
#         print('fmq get() a time', time() - st)


# for i in range(5):
# mp.Process(target=get_and_print, args=(q1, 'mq'), daemon=True).start()

# for i in range(5):
mp.Process(target=get_and_print, args=(q2, 'fmq'), daemon=True).start()


for i in range(5):
    print('Put item')
    # q1.put(np.array(a))
    q2.put(np.array(a))
print(q2)
while True:
    pass