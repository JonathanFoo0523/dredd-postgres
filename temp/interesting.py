#!/usr/bin/python3

import sys
import os
import subprocess
import tempfile
import time
import socket
from contextlib import closing
import time
import signal
import re

DIFFERENTIAL_TEST_TIMEOUT_MULTIPLIER = 5
MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS = 30

mutant = 34727
source = 'optimizer-plan'

with open('testcase.log', 'rb') as f:
    statements = f.read()
    # This ensure creduce produced test case alwats end with ';'
    while statements[-1] != 59:
        statements = statements[:-1]

class PostgresProcessWithEnvironAndDirectory:
    def __init__(self, mutant=None):
        self.env = os.environ.copy()
        self.temp_dir = tempfile.TemporaryDirectory(delete=False)
        self.env["PGDATA"] = self.temp_dir.name
        print(self.temp_dir.name)
        self.env['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'lib'))
        self.env["PGPORT"] = str(self.find_free_port())
        if mutant:
            self.env["DREDD_ENABLED_MUTATION"] = str(mutant)

    def stop_pgctl(self):
        pg_ctl_stop_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), 'stop', '-m', 'immediate'], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
        if pg_ctl_stop_proc.returncode == 0:
            print(pg_ctl_stop_proc.stdout.decode())
        else:
            print(pg_ctl_stop_proc.stderr.decode())
    

    def find_free_port(self):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    def __enter__(self):
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGQUIT, self.exit_gracefully)

        return self.env, self.temp_dir.name

    def __exit__(self, exc_type, exc_value, tb):
        print('___exit__')
        self.stop_pgctl()
        self.temp_dir.cleanup()

    def exit_gracefully(self, signum, frame):
        print("gracefullt")
        exit(signum)


with PostgresProcessWithEnvironAndDirectory() as (env_copy, temp_data_dir):
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'initdb')], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB(Ref) Fail:', source)
        print(initdb_proc.stderr.decode())
        exit(7)

    # Start postgres server process
    pg_ctl_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Ref) Fail:', source)
        print(pg_ctl_proc.stderr.decode())
        exit(6)
    else:
        print(pg_ctl_proc.stdout.decode())

    # Create `test` database
    createdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if createdb_proc.returncode != 0:
        print('Createdb(Ref) Fail:', source)
        print(createdb_proc.stderr.decode())
        exit(5)

    time.sleep(100)

    # Launch PSQL
    time_start = time.time()
    psql_proc_ref = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time_end = time.time()
    time_base = time_end - time_start


with PostgresProcessWithEnvironAndDirectory(mutant) as (env_copy, temp_data_dir):
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
    if initdb_proc.returncode != 0:
        print('InitDB(Mut) Fail:', source)
        print(initdb_proc.stderr.decode())
        exit(4)

    # Start postgres server process
    pg_ctl_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Mut) Fail:', source)
        print(pg_ctl_proc.stderr.decode())
        exit(3)
    else:
        print(pg_ctl_proc.stdout.decode())

    # Create `test` database
    createdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
    if createdb_proc.returncode != 0:
        print('Createdb(Mut) Fail:', source)
        print(createdb_proc.stderr.decode())
        exit(2)

    # Launch PSQL
    psql_proc_mut = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/optimizer-plan', 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=time_base*DIFFERENTIAL_TEST_TIMEOUT_MULTIPLIER)


if psql_proc_ref.returncode == psql_proc_mut.returncode and psql_proc_ref.stdout == psql_proc_mut.stdout and psql_proc_ref.stderr == psql_proc_mut.stderr:
    exit(1)


exit(0)