from multiprocessing import Pool
import subprocess
import time
import os


def f(x):
    proc = subprocess.run(['python3', '-u', 'dredd_coverage.py'])

with Pool() as p:
    try:
        # Total of 100-ish mutation task, the rest are no ops
        p.map(f, range(200))
    except KeyboardInterrupt:
        pass


