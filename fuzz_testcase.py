import os
import tempfile
from distutils.dir_util import copy_tree
import subprocess
from filelock import Timeout, FileLock
import random
import shutil
import glob

postgres_src = '/home/ubuntu/postgresql-16.3'
coverage_output_directory = 'sample_coverage_output'
path_to_dredd = '/home/ubuntu/postgresql-16.3/src/backend/'
dredd_bin = '/home/ubuntu/dredd/third_party/clang+llvm/bin/dredd'
dredd_coverage_output_directory = 'sample_dredd_output/tracking'
dredd_mutation_output_directory = 'sample_dredd_output/mutation'
sqlancer_path = '/home/ubuntu/temp/sqlancer/target/sqlancer-2.0.0.jar'
output_directory = 'sample_fuzz_output'

# Pick a random source
ready_srcs = [src.replace('.txt', '') for src in os.listdir(coverage_output_directory)]
random_source = random.choice(ready_srcs)
# random_source = 'rewrite'
print("Source:", random_source)

# Make directory if necessary
os.makedirs(os.path.join(output_directory, random_source), exist_ok=True)
killing_testcases_dir = os.path.join(output_directory, random_source, 'killing_testcases')
os.makedirs(killing_testcases_dir, exist_ok=True)

# Copy Killed(AKA Covered File)
killed_file = os.path.join(output_directory, random_source, 'killed.txt')
killed_file_lock = FileLock(killed_file + '.lock', blocking=True)
with killed_file_lock:
    if not os.path.isfile(killed_file):
        shutil.copy(os.path.join(coverage_output_directory, random_source+'.txt'), killed_file)

# sqlancer_seed = 27963700

# Pick a random number and create file
while True:
    sqlancer_seed = random.randint(0, 2 ** 32 - 1) // 100 * 100 
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

# Pick an unused port between 4000 to 4100
while True:
    try:
        port = random.randint(4000, 4100)
        portlock = FileLock(os.path.join(output_directory, f'port-{port}.lock'), blocking=False).acquire()
    except Timeout:
        print(f"Another runner using port {port}")
        continue
    else:
        print(f"Using port {port}")
        break

# TEMPORARY TO MAKE A SQLANCER KILL: REMOVE THIS
# random_source = 'rewrite'
# sqlancer_seed = 27963700


# relative_path = os.path.join(path_to_dredd.replace(postgres_src + '/', ''), random_source)
# print(relative_path)
directory = random_source.replace('-', '/') 
print(random_source)
coverage_installation = os.path.join(dredd_coverage_output_directory, random_source)
mutation_installation = os.path.join(dredd_mutation_output_directory, random_source)


# if mutation_instalation doesn't exist, make one
if not os.path.isdir(mutation_installation):
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


# Generate Test Case and find coverage
env_copy = os.environ.copy()
env_copy["PGPORT"] = str(port)
env_copy['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'lib'))

with tempfile.TemporaryDirectory() as temp_data_dir:
    # Create new postgres database cluster
    initdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initdb_proc.returncode != 0:
        print('InitDB Fail:', random_source)
        print(initdb_proc.stderr.decode())
        exit()

    with tempfile.NamedTemporaryFile(prefix='dredd-postgress-dredd-coverage') as temp_coverage_file:
        coverage_filepath = temp_coverage_file.name
        env_copy["DREDD_MUTANT_TRACKING_FILE"] = coverage_filepath

        # Start postgres server process
        pg_ctl_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if pg_ctl_proc.returncode != 0:
            print('PG_CTL Fail:', random_source)
            print(pg_ctl_proc.stderr.decode())
            exit()
        else:
            print(pg_ctl_proc.stdout.decode())

        # Create `test` database, whcih is expected by SQLancer
        createdb_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if createdb_proc.returncode != 0:
            print('Createdb Fail:', random_source)
            print(createdb_proc.stderr.decode())
            exit()

        # Fuzz with random seed
        with tempfile.TemporaryDirectory() as sqlancer_data_dir:
            sqlancer_proc = subprocess.run(['java', '-jar', sqlancer_path, '--random-seed', str(sqlancer_seed), '--max-generated-databases', '1', '--num-threads', '16', '--num-queries', '2000', '--username', 'ubuntu', '--port', str(port), 'postgres'], cwd=sqlancer_data_dir)
            if sqlancer_proc.returncode != 0:
                print('Sqlancer Fail', random_source)
                exit()

        # Get Covered Mutants
        temp_coverage_file.seek(0)
        covered_mutants = set(sorted([int(line.rstrip()) for line in temp_coverage_file]))
        print("Covered Mutants:", len(covered_mutants))
    
    # Stop postgres server process
    pg_ctl_stop_proc = subprocess.run([os.path.join(coverage_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(pg_ctl_stop_proc.stdout.decode())


# Load Covered Mutants
# with killed_file_lock:
#     with open(killed_file, 'r') as f:
#         killed_mutants = set([int(line.rstrip()) for line in f])
# candidate_mutant = covered_mutants - killed_mutants
# print('Mutants To Try:', len(candidate_mutant))


# Use Test Case to fuzz covered mutants
env_copy = os.environ.copy()
env_copy["PGPORT"] = str(port)
env_copy['LD_LIBRARY_PATH'] = os.path.abspath(os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'lib'))

for mutant in sorted(covered_mutants):
    # Load Covered and Killed Mutants
    with killed_file_lock:
        with open(killed_file, 'r') as f:
            killed_mutants = set([int(line.rstrip()) for line in f])

    if mutant in killed_mutants:
        continue

    print("Checking mutants:", mutant)
    env_copy['DREDD_ENABLED_MUTATION'] = str(mutant)

    # Generate Test Case and Check for Kill
    with tempfile.TemporaryDirectory() as temp_data_dir:
        # Create new postgres database cluster
        initdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', temp_data_dir], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if initdb_proc.returncode != 0:
            print('InitDB Fail:', random_source, 'with', mutant)
            print(initdb_proc.stderr.decode())
            with open(csv_path, 'a') as f:
                f.write(f'{mutant}, INIT_DB_FAIL\n')
            with killed_file_lock:
                with open(killed_file, 'a') as f:
                    f.write(f'{mutant}\n')
            continue

        try:
            # Start postgres server process
            pg_ctl_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, '-l', f'{temp_data_dir}/logfile', 'start'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if pg_ctl_proc.returncode != 0:
                print('PG_CTL Fail:', random_source, 'with', mutant)
                print(pg_ctl_proc.stderr.decode())
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, PG_CTL_FAIL\n')
                continue
            else:
                print(pg_ctl_proc.stdout.decode())

            # Create `test` database, whcih is expected by SQLancer
            createdb_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if createdb_proc.returncode != 0:
                print('Createdb Fail:', random_source, 'with', mutant)
                print(createdb_proc.stderr.decode())
                with open(csv_path, 'a') as f:
                    f.write(f'{mutant}, CREATE_DB_FAIL\n')
                with killed_file_lock:
                    with open(killed_file, 'a') as f:
                        f.write(f'{mutant}\n')
                continue

            # Fuzz with random seed
            with tempfile.TemporaryDirectory() as sqlancer_data_dir:
                sqlancer_proc = subprocess.run(['java', '-jar', sqlancer_path, '--random-seed', str(sqlancer_seed), '--max-generated-databases', '1', '--num-threads', '16', '--num-queries', '2000', '--username', 'ubuntu',  '--port', str(port), 'postgres'], cwd=sqlancer_data_dir, stderr=subprocess.DEVNULL)
                if sqlancer_proc.returncode != 0:
                    print("FUZZ KILL:", random_source, 'with', mutant)
                    with open(csv_path, 'a') as f:
                        f.write(f'{mutant}, FUZZ_KILLED\n')
                    with killed_file_lock:
                        with open(killed_file, 'a') as f:
                            f.write(f'{mutant}\n')
                    # Pattern for failed file
                    for file in sorted(glob.glob(os.path.join(sqlancer_data_dir, 'logs', 'postgres') + '/database*-cur.log'), key=lambda x: int(x.split('/')[-1].replace('database', '').replace('-cur.log', ''))):
                        if not os.path.isfile(os.path.join(sqlancer_data_dir, 'logs', 'postgres', file.replace('-cur.log', '.log'))):
                            continue
                        testfile = os.path.join(sqlancer_data_dir, 'logs', 'postgres', file)
                        shutil.copy(testfile, os.path.join(killing_testcases_dir, f'{mutant}.log'))
                        break
                    else:
                        print("CAN'T FIND FAILED TEST CASE")
                    continue

            with open(csv_path, 'a') as f:
                f.write(f'{mutant}, SURVIVED\n')

        finally:
            # Stop postgres server process
            pg_ctl_stop_proc = subprocess.run([os.path.join(mutation_installation, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_data_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(pg_ctl_stop_proc.stdout.decode())








        


        