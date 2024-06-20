from multiprocessing import Pool, cpu_count
import subprocess
import time
import os


def f(x):
    with open(os.path.join('fuzz_runner_output', f'{x}.out'), 'w') as fout:
        proc = subprocess.run(['python3', '-u', 'fuzz_testcase.py'], stdout=fout)

with Pool(cpu_count() * 2 // 3) as p:
    try:
        p.map(f, range(2000000,3000000))
    except KeyboardInterrupt:
        pass


