import os
import tempfile
from distutils.dir_util import copy_tree
import subprocess
from filelock import Timeout, FileLock
import random
import shutil
import glob
import time
import pickle

SQLANCER_GENERATION_TIMEOUT_SECONDS = 30
DIFFFERENTIAL_TEST_TIMEOUT_MULTIPLIER = 5
MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS = 30

postgres_src = '/home/ubuntu/postgresql-16.3'
coverage_output_directory = 'sample_coverage_output'
path_to_dredd = '/home/ubuntu/postgresql-16.3/src/backend/'
dredd_bin = '/home/ubuntu/dredd/third_party/clang+llvm/bin/dredd'
dredd_coverage_output_directory = 'sample_dredd_output/tracking'
dredd_mutation_output_directory = 'sample_dredd_output/mutation'
sqlancer_path = '/home/ubuntu/sqlancer/target/sqlancer-2.0.0.jar'
output_directory = 'sample_fuzz_output'

# Pick a random source
ready_srcs = [src.replace('.txt', '') for src in os.listdir(coverage_output_directory)]
random_source = random.choice(ready_srcs)
# random_source = 'optimizer-path'
print("Source:", random_source)

# Make directory if necessary
os.makedirs(os.path.join(output_directory, random_source), exist_ok=True)
killing_testcases_dir = os.path.join(output_directory, random_source, 'killing_testcases')
os.makedirs(killing_testcases_dir, exist_ok=True)

# Copy Killed(AKA Covered File)
print("Creating kill checkpoint file...")
killed_file = os.path.join(output_directory, random_source, 'killed.pkl')
killed_file_lock = FileLock(killed_file + '.lock', blocking=True)
with killed_file_lock:
    if not os.path.isfile(killed_file):
        with open(killed_file, 'wb') as p:
            with open(os.path.join(coverage_output_directory, random_source+'.txt'), 'r') as f:
                pickle.dump(set([int(line.rstrip()) for line in f]), p)
        # shutil.copy(os.path.join(coverage_output_directory, random_source+'.txt'), killed_file)

# sqlancer_seed = 3988215300

# Pick a random number and create file
while True:
    sqlancer_seed = random.randint(0, 2 ** 32 - 1)
    print(sqlancer_seed)
    csv_path = os.path.join(output_directory, random_source, f'{sqlancer_seed}.csv')
    try:
        with open(csv_path, 'x') as f:
            f.write('mutant, status\n')
        print("Seed:", sqlancer_seed)
        break
    except FileExistError:
        print("Seed used, regenerating...")
        continue

# sqlancer_seed = 27963700

import socket
from contextlib import closing

def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

port = find_free_port()
print("Using Port:", port)


# relative_path = os.path.join(path_to_dredd.replace(postgres_src + '/', ''), random_source)
# print(relative_path)
directory = random_source.replace('-', '/') 
print(random_source)
coverage_installation = os.path.join(dredd_coverage_output_directory, random_source)
mutation_installation = os.path.join(dredd_mutation_output_directory, random_source)


# if mutation_instalation doesn't exist, make one
if not os.path.isdir(mutation_installation):
    print("Applying dredd to source and recompile...")
    relative_path = os.path.join(path_to_dredd.replace(postgres_src + '/', ''), directory)

    with tempfile.TemporaryDirectory() as temp_src_dir:
        copy_tree(postgres_src, temp_src_dir)

        # Reconfigure, as MAKE made use of cached postgres_root_path
        conf_proc = subprocess.run(['./configure', '-without-icu'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir)
        if conf_proc.returncode != 0:
            print('Configure Fail:', directory)
            print(conf_proc.stderr.decode())
            exit()
        
        # Apply dredd with mutant-tracking To file
        dredd_proc = subprocess.run(' '.join([dredd_bin, os.path.join(temp_src_dir, relative_path) + '/*.c', '--mutation-info-file', 'mutant-info.json']), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir, shell=True)
        if dredd_proc.returncode != 0:
            print('Dredd Fail:', directory)
            print(dredd_proc.stderr.decode())
            exit()

        # Compile the mutated file
        build_proc = subprocess.run(['make', 'temp-install'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir)
        if build_proc.returncode != 0:
            print('Build Fail:', directory)
            print(build_proc.stderr.decode())
            exit()
        else:
            copy_tree(os.path.join(temp_src_dir, 'tmp_install'), mutation_installation)


# Generate Test Case
env_copy = os.environ.copy()
env_copy["PGPORT"] = str(port)
env_copy['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'lib'))

with tempfile.TemporaryDirectory() as temp_data_dir:
    # Create new postgres database cluster
    print("Starting postgres database cluster...")
    initdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB(Fuzz) Fail:', random_source)
        print(initdb_proc.stderr.decode())
        exit()

    # Start postgres server process
    print("Staring postgres server process...")
    pg_ctl_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Fuzz) Fail:', random_source)
        print(pg_ctl_proc.stderr.decode())
        exit()
    else:
        print(pg_ctl_proc.stdout.decode())

    try:
        # Create `test` database, whcih is expected by SQLancer
        print("Creating `test` database....")
        createdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if createdb_proc.returncode != 0:
            print('Createdb(Fuzz) Fail:', random_source)
            print(createdb_proc.stderr.decode())
            exit()

        # Fuzz with random seed
        print("Running sqlancer...")
        generated = False
        while not generated:
            with tempfile.TemporaryDirectory() as sqlancer_data_dir:
                try:
                    sqlancer_proc = subprocess.run(['java', '-jar', sqlancer_path, '--random-seed', str(sqlancer_seed), '--max-generated-databases', '1', '--num-threads', '2', '--num-queries', '2000', '--username', 'ubuntu', '--port', str(port), '--num-tries', '1', 'postgres'], cwd=sqlancer_data_dir, timeout=SQLANCER_GENERATION_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    print("Generation timeout ")
                    exit()
                if sqlancer_proc.returncode != 0:
                    print('Sqlancer Fail', random_source)
                    exit()
                generated = True
                # Get the file
                print("Reading generatin file...")
                with open(os.path.join(sqlancer_data_dir, 'logs', 'postgres', 'database0-cur.log'), 'rb') as f:
                    statements = f.read()
    finally:
        # Stop postgres server process
        pg_ctl_stop_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(pg_ctl_stop_proc.stdout.decode())

# statements = b'DROP DATABASE IF EXISTS database46;\n'

# Use Test Case to find covered mutants
env_copy = os.environ.copy()
env_copy["PGPORT"] = str(port)
env_copy['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'lib'))

# Finding coverage
print("Finding coverage with generated testcase...")
with tempfile.TemporaryDirectory() as temp_data_dir:
    with tempfile.NamedTemporaryFile(prefix='dredd-postgress-dredd-coverage') as temp_coverage_file:
        coverage_filepath = temp_coverage_file.name
        # env_copy["DREDD_MUTANT_TRACKING_FILE"] = coverage_filepath

        # Create new postgres database cluster
        initdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if initdb_proc.returncode != 0:
            print('InitDB(Cov) Fail:', random_source)
            print(initdb_proc.stderr.decode())
            exit()

        # Start postgres server process
        env_copy["DREDD_MUTANT_TRACKING_FILE"] = coverage_filepath
        pg_ctl_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if pg_ctl_proc.returncode != 0:
            print('PG_CTL(Cov) Fail:', random_source)
            print(pg_ctl_proc.stderr.decode())
            exit()
        else:
            print(pg_ctl_proc.stdout.decode())

        try:
            # Create `test` database
            env_copy["DREDD_MUTANT_TRACKING_FILE"] = "" # This is just a frontend which we aren't interested
            createdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if createdb_proc.returncode != 0:
                print('Createdb(Cov) Fail:', random_source)
                print(createdb_proc.stderr.decode())
                exit()

            # Running
            env_copy["DREDD_MUTANT_TRACKING_FILE"] = ""
            time_start = time.time()
            psql_proc_cov = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)        
            time_end = time.time()
            base_time_cov = time_end - time_start

            # Get Covered Mutants
            temp_coverage_file.seek(0)
            covered_mutants = set(sorted([int(line.rstrip()) for line in temp_coverage_file]))
            print("Covered Mutants:", len(covered_mutants))

        finally:
            # Stop postgres server process
            pg_ctl_stop_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(pg_ctl_stop_proc.stdout.decode())
            if pg_ctl_stop_proc.returncode != 0:
                print('Stop(Cov) Fail:', random_source)
                exit()

if len(covered_mutants) == 0:
    print('No Covered Mutants: Exiting...')
    exit()

# Check with unmutated postgres
print("Checking testcase with unmutated postgres installation...")
with tempfile.TemporaryDirectory() as temp_data_dir:
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB(Ref) Fail:', random_source)
        print(initdb_proc.stderr.decode())
        exit()

    # Start postgres server process
    pg_ctl_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pg_ctl_proc.returncode != 0:
        print('PG_CTL(Ref) Fail:', random_source)
        print(pg_ctl_proc.stderr.decode())
        exit()
    else:
        print(pg_ctl_proc.stdout.decode())

    try:
        # Create `test` database
        createdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if createdb_proc.returncode != 0:
            print('Createdb(Ref) Fail:', random_source)
            print(createdb_proc.stderr.decode())
            exit()

        # Launch PSQL
        time_start = time.time()
        psql_proc_ref = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time_end = time.time()
        base_time = time_end - time_start
    finally:
        # Stop postgres server process
        pg_ctl_stop_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(pg_ctl_stop_proc.stdout.decode())
        if pg_ctl_stop_proc.returncode != 0:
            print('Stop(Ref) Fail:', random_source)
            exit()


if psql_proc_cov.returncode != psql_proc_ref.returncode:
    print("Indeterministic test result(returncode)")
    exit()

if psql_proc_ref.stdout != psql_proc_cov.stdout:
    with open('ref_stdout', 'wb') as f:
        f.write(psql_proc_ref.stdout)
    with open('cov_stdout', 'wb') as f:
        f.write(psql_proc_cov.stdout)
    print("Indeterministic test result(stdout)")
    exit()

if psql_proc_ref.stderr != psql_proc_cov.stderr:
    print("Indeterministic test result(stderr)")
    exit()

with killed_file_lock:
    with open(killed_file, 'rb') as f:
        killed_mutants = pickle.load(f)


for mutant in sorted(covered_mutants):
    # Load Covered and Killed Mutants

    if mutant in killed_mutants:
        continue

    killed = False
    interesting_kill = False

    print("Checking mutants:", mutant)
    env_copy['DREDD_ENABLED_MUTATION'] = str(mutant)

    # Generate Test Case and Check for Kill
    with tempfile.TemporaryDirectory() as temp_data_dir:
        # Create new postgres database cluster
        initdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
        if initdb_proc.returncode != 0:
            print('InitDB(Mut) Fail:', random_source, 'with', mutant)
            print(initdb_proc.stderr.decode())
            with open(csv_path, 'a') as f:
                f.write(f'{mutant}, INIT_DB_FAIL\n')
            killed = True
            continue

    
        # Start postgres server process
        pg_ctl_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
        if pg_ctl_proc.returncode != 0:
            print('PG_CTL(Mut) Fail:', random_source, 'with', mutant)
            print(pg_ctl_proc.stderr.decode())
            killed = True
            continue
        else:
            print(pg_ctl_proc.stdout.decode())

        
        try:
            # Create `test` database, whcih is expected by SQLancer
            createdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
            if createdb_proc.returncode != 0:
                print('Createdb(Mut) Fail:', random_source, 'with', mutant)
                print(createdb_proc.stderr.decode())
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, CREATE_DB_FAIL\n')
                killed = True
                continue

            # Launch PSQL
            try:
                psql_proc_mut = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'psql'), 'test'], input=statements, env=env_copy,stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=DIFFFERENTIAL_TEST_TIMEOUT_MULTIPLIER*base_time)
            except subprocess.TimeoutExpired:
                print('TIMEOUT_KILL', mutant, random_source)
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, TIMEOUT_KILL\n')
                killed = True
                continue


            # Checking output and stderr difference
            if psql_proc_ref.returncode != psql_proc_mut.returncode:
                print('RETURNCODE_DIFF_KILL', mutant, random_source)
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, RETURNCODE_DIFF_KILL\n')
                killed = True
                interesting_kill = True
                continue
            if psql_proc_ref.stdout != psql_proc_mut.stdout:
                print('STDOUT_DIFF_KILL', mutant, random_source)
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, STDOUT_DIFF_KILL\n')
                killed = True
                interesting_kill = True
                continue
            if psql_proc_ref.stderr != psql_proc_mut.stderr:
                print('STDERR_DIFF_KILL', mutant, random_source)
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, STDERR_DIFF_KILL\n')
                killed = True
                interesting_kill = True
                continue
            

            with open(csv_path, 'a') as f:
                f.write(f'{mutant}, SURVIVED\n')
            print('SURVIVED', mutant, random_source)

        finally:
            # Stop postgres server process
            pg_ctl_stop_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MUTATATED_BIN_DEFAULT_TIMEOUT_SECONDS)
            print(pg_ctl_stop_proc.stdout.decode())

            # Update killed mutants
            with killed_file_lock:
                with open(killed_file, 'rb') as f:
                    killed_mutants = pickle.load(f)
                if killed:
                    killed_mutants.add(mutant)
                    with open(killed_file, 'wb') as f:
                        pickle.dump(killed_mutants, f)

            if interesting_kill:
                with open(os.path.join(killing_testcases_dir, f'{mutant}.log'), 'wb') as f:
                    f.write(statements)

print("Done")








        


        