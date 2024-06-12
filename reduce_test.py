import os
from filelock import Timeout, FileLock
import random
import glob
import tempfile
import jinja2
import stat
import shutil
import subprocess

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

    if source not in ['optimizer-plan']:
        continue

    if os.path.isfile(os.path.join(output_directory, f'{source}-{mutant}.sql')):
        continue

    reduce_file_lock = FileLock(os.path.join(output_directory, f'{source}-{mutant}.lock'), blocking=False)

    print('reducing:', source, mutant)

    try:
        with reduce_file_lock:

            interestingness_test_template = jinja2.Environment(
                 loader=jinja2.FileSystemLoader(
                     searchpath=os.path.dirname(os.path.realpath(__file__)))).get_template("interesting.py.jinja")


            with tempfile.TemporaryDirectory() as tempdir:
                print(tempdir)
                open(os.path.join(tempdir, 'interesting.py'), 'w').write(interestingness_test_template.render(
                    mutation_installation_path=os.path.abspath(os.path.join(dredd_mutation_output, source)),
                    mutation_id = mutant,
                    source = source,
                    port = port
                ))

                # Make the interestingness test executable
                st = os.stat(os.path.join(tempdir, 'interesting.py'))
                os.chmod(os.path.join(tempdir, 'interesting.py'), st.st_mode | stat.S_IEXEC)
                shutil.copy(filepath, os.path.join(tempdir, 'testcase.log'))


                shutil.copy(os.path.join(tempdir, 'interesting.py'), 'temp/interesting.py')
                shutil.copy(os.path.join(tempdir, 'testcase.log'), 'temp/testcase.log')

                # Execute 
                proc = subprocess.run(['creduce', 'interesting.py', 'testcase.log', '--not-c', '--n', '16'], cwd=tempdir)
                if proc.returncode != 0:
                    exit()

                shutil.copy(os.path.join(tempdir, 'testcase.log'), os.path.join(output_directory, f'{source}-{mutant}.sql'))

    except TimeoutError:
        continue

    print(source, mutant)
