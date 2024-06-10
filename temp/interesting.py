#!/usr/bin/python3

import sys
import os
import subprocess
import tempfile
import time
import socket
from contextlib import closing

def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

port = find_free_port()
print(port)

mutant = 2754
source = 'statistics'

with open('testcase.log', 'rb') as f:
    statements = f.read()

env_copy = os.environ.copy()
env_copy["PGPORT"] = str(port)
env_copy['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'lib'))

with tempfile.TemporaryDirectory() as temp_data_dir:
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB(Ref) Fail:', source)
        print(initdb_proc.stderr.decode())
        exit(7)

    # Start postgres server process
    pg_ctl_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Ref) Fail:', source)
        print(pg_ctl_proc.stderr.decode())
        exit(6)
    else:
        print(pg_ctl_proc.stdout.decode())

    # Create `test` database
    createdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if createdb_proc.returncode != 0:
        print('Createdb(Ref) Fail:', source)
        print(createdb_proc.stderr.decode())
        exit(5)

    # Launch PSQL
    psql_proc_ref = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Stop postgres server process
    pg_ctl_stop_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pg_ctl_stop_proc.stdout.decode())
    if pg_ctl_stop_proc.returncode != 0:
        print('Stop(Ref) Fail:', source)
        exit(8)

env_copy['DREDD_ENABLED_MUTATION'] = str(mutant)
env_copy["PGPORT"] = str(port)

with tempfile.TemporaryDirectory() as temp_data_dir:
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB(Mut) Fail:', source)
        print(initdb_proc.stderr.decode())
        exit(4)

    # Start postgres server process
    pg_ctl_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Mut) Fail:', source)
        print(pg_ctl_proc.stderr.decode())
        exit(3)
    else:
        print(pg_ctl_proc.stdout.decode())

    # Create `test` database
    createdb_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if createdb_proc.returncode != 0:
        print('Createdb(Mut) Fail:', source)
        print(createdb_proc.stderr.decode())
        exit(2)

    # Launch PSQL
    psql_proc_mut = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Stop postgres server process
    pg_ctl_stop_proc = subprocess.run([os.path.join('/home/ubuntu/dredd-postgres/sample_dredd_output/mutation/statistics', 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # print(pg_ctl_stop_proc.stdout.decode())


if psql_proc_ref.returncode == psql_proc_mut.returncode and psql_proc_ref.stdout == psql_proc_mut.stdout and psql_proc_ref.stderr == psql_proc_mut.stderr:
    exit(1)


exit(0)