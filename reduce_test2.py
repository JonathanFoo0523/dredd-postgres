import os
from filelock import Timeout, FileLock
import random
import glob
import tempfile
import jinja2
import stat
import shutil
import subprocess
import socket
from contextlib import closing


class PostgresProcess(object):
    def __init__(self, installation_path, port, mutation=None):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.installation_path = installation_path
        self.env = os.environ.copy()
        self.env["PGPORT"] = str(port)
        self.env['LD_LIBRARY_PATH'] = os.abspath(ps.path.join(installation_path, 'usr', 'local', 'pgsql', 'lib'))
        if mutation:
            self.env['DREDD_ENABLED_MUATION'] = str(mutation)

    def __enter__(self):
        initdb_proc = subprocess.run([os.path.join(installation_path, 'usr', 'local', 'pgsql', 'bin', 'initdb'), '-D', self.temp_dir], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if initdb_proc.returncode != 0:
            print('InitDB(Mut) Fail:', source)
            print(initdb_proc.stderr.decode())
            exit()

        # Start postgres server process
        pg_ctl_proc = subprocess.run([os.path.join(installation_path, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', self.temp_dir, '-l', f'{temp_dir}/logfile', 'start'], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if pg_ctl_proc.returncode != 0:
            print('PG_CTL(Mut) Fail:', source)
            print(pg_ctl_proc.stderr.decode())
            exit()
        return self.env
        
    def __exit__(self):
        pg_ctl_stop_proc = subprocess.run([os.path.join(installation_path, 'usr', 'local', 'pgsql', 'bin', 'pg_ctl'), '-D', temp_dir, 'stop'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.installation_path.cleanup()


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

port_ref = find_free_port()
port_mut = find_free_port()
print(port_ref, port_mut)


fuzz_output_directory = 'sample_fuzz_output'
output_directory = 'sample_reduction_output'
dredd_mutation_output = 'sample_dredd_output/mutation'

# Pick an unused port between 5000 to 5100
while True:
    try:
        port = random.randint(4000, 4100)
        if port % 2 == 1:
            continue
        portlock = FileLock(os.path.join(output_directory, f'port-{port}.lock'), blocking=False).acquire()
    except Timeout:
        print(f"Another runner using port {port}")
        continue
    else:
        print(f"Using port {port}")
        break


# Pick a file to reduce
for filepath in glob.glob(f'{fuzz_output_directory}/*/killing_testcases/*.log'):
    _, source, _, logfile = filepath.split('/')
    mutant = logfile.replace('.log', '')

    if os.path.isfile(os.path.join(output_directory, f'{source}-{mutant}.sql')):
        continue

    reduce_file_lock = FileLock(os.path.join(output_directory, f'{source}-{mutant}.lock'), blocking=False)

    print('reducing:', source, mutant)

    try:
        with reduce_file_lock:

            interestingness_test_template = jinja2.Environment(
                 loader=jinja2.FileSystemLoader(
                     searchpath=os.path.dirname(os.path.realpath(__file__)))).get_template("interesting2.py.jinja")
        

            # Create Ref Postgres Process and DB
            with PostgresProcess(os.path.join(dredd_mutation_output, source), port_ref) as pg_env:
                # Create `test` database
                createdb_proc = subprocess.run([os.path.join(os.path.join(dredd_mutation_output, source), 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=pg_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if createdb_proc.returncode != 0:
                    print('Createdb(Ref) Fail:', source)
                    print(createdb_proc.stderr.decode())
                    exit()


                # Create Mutated Postgres and DB
                with PostgresProcess(os.path.join(dredd_mutation_output, source), port_mut) as pg_env_mut:
                    # Create `test` database
                    createdb_proc = subprocess.run([os.path.join(os.path.join(dredd_mutation_output, source), 'usr', 'local', 'pgsql', 'bin', 'createdb'), 'test'], env=env_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if createdb_proc.returncode != 0:
                        print('Createdb(Mut) Fail:', source)
                        print(createdb_proc.stderr.decode())
                        exit()


                    with tempfile.TemporaryDirectory() as tempdir:
                        print(tempdir)
                        open(os.path.join(tempdir, 'interesting.py'), 'w').write(interestingness_test_template.render(
                            mutation_installation_path=os.path.abspath(os.path.join(dredd_mutation_output, source)),
                            mutation_id = mutant,
                            source = source,
                            port_ref = port_ref,
                            port_mut = port_mut
                        ))

                        # Make the interestingness test executable
                        st = os.stat(os.path.join(tempdir, 'interesting.py'))
                        os.chmod(os.path.join(tempdir, 'interesting.py'), st.st_mode | stat.S_IEXEC)
                        shutil.copy(filepath, os.path.join(tempdir, 'testcase.log'))


                        shutil.copy(os.path.join(tempdir, 'interesting.py'), 'temp/interesting.py')
                        shutil.copy(os.path.join(tempdir, 'testcase.log'), 'temp/testcase.log')

                        # Execute 
                        proc = subprocess.run(['creduce', 'interesting.py', 'testcase.log'], cwd=tempdir)
                        if proc.returncode != 0:
                            exit()

                        shutil.copy(os.path.join(tempdir, 'testcase.log'), os.path.join(output_directory, f'{source}-{mutant}.sql'))

    except TimeoutError:
        continue

    print(source, mutant)
