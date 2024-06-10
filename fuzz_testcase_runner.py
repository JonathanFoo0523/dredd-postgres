from multiprocessing import Pool, cpu_count
import subprocess
import time
import os


def f(x):
    with open(os.path.join('fuzz_runner_output', f'{x}.out'), 'w') as fout, open(os.path.join('fuzz_runner_output', f'{x}.error'), 'w') as ferror:
        proc = subprocess.run(['python3', '-u', 'fuzz_testcase.py'], stdout=fout, stderr=ferror)

with Pool(cpu_count() // 2) as p:
    try:
        p.map(f, range(1000000))
    except KeyboardInterrupt:
        pass


