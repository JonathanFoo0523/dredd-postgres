from multiprocessing import Pool, cpu_count
import subprocess
import time
import os


def f(x):
    with open(os.path.join('reduce_runner_output', f'{x}.out'), 'w') as fout:
        proc = subprocess.run(['python3', '-u', 'reduce_test.py'], stdout=fout)

with Pool(cpu_count()) as p:
    try:
        p.map(f, range(1000))
    except KeyboardInterrupt:
        pass


