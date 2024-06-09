import os
import sys
import glob
import subprocess
import tempfile
import re
from distutils.dir_util import copy_tree
import shutil
from filelock import Timeout, FileLock


postgres_src = '/home/ubuntu/postgresql-16.3'
path_to_dredd = '/home/ubuntu/postgresql-16.3/src/backend/'
dredd_bin = '/home/ubuntu/dredd/third_party/clang+llvm/bin/dredd'
mutant_info_query_path = '/home/ubuntu/dredd/scripts/query_mutant_info.py'
coverage_output_directory = 'sample_coverage_output'
dredd_coverage_output_directory = 'sample_dredd_output/tracking'

for root, dirs, files in os.walk(path_to_dredd):
    c_files = [file for file in files if file.endswith('.c')]
    if len(c_files) == 0:
        continue

    directory = root.replace(path_to_dredd, '')
    output_path = os.path.join(coverage_output_directory, directory.replace('/', '-') + '.txt')

    # checked
    if os.path.isfile(output_path):
        continue

    # FAILED
    if directory in ['parser', 'nodes', 'regex', 'jit/llvm', 'libpq', 'utils/adt', 'utils/mb', 'port/win32', 'port']:
        continue

    directory_lock = FileLock(os.path.join(coverage_output_directory, directory.replace('/', '-') + '.lock'), blocking=False)
    try:
        with directory_lock:    

            relative_path = os.path.join(path_to_dredd.replace(postgres_src + '/', ''), directory)

            with tempfile.TemporaryDirectory() as temp_src_dir:
                copy_tree(postgres_src, temp_src_dir)
                
                # Apply dredd with mutant-tracking To file
                dredd_proc = subprocess.run(' '.join([dredd_bin, os.path.join(temp_src_dir, relative_path) + '/*.c', '--mutation-info-file', 'mutant-info.json', '--only-track-mutant-coverage']), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir, shell=True)
                if dredd_proc.returncode != 0:
                    print('Dredd Fail:', directory)
                    print(dredd_proc.stderr.decode())
                    continue

                # Get Total Mutants Produced
                query_mutant_proc = subprocess.run(['python3', mutant_info_query_path, 'mutant-info.json', '--largest-mutant-id'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp_src_dir)
                if query_mutant_proc.returncode != 0:
                    print('Mutant Query Fail:', directory)
                    print(query_mutant_proc.stderr.decode())
                    total_mutants = 0
                else:
                    total_mutants = int(query_mutant_proc.stdout) + 1

                # Compile the mutated file
                # cov_proc = subprocess.run(['make'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir)
                # if cov_proc.returncode != 0:
                #     print('Build Fail:', directory)
                #     print(cov_proc.stderr.decode())
                #     continue
                # else:
                #     copy_tree(os.path.join(temp_src_dir, 'tmp_install'), os.path.join(dredd_coverage_output_directory, directory.replace('/', '_') ))
                    # exit(2)
                # Reconfigure, as MAKE made use of cached postgres_root_path
                conf_proc = subprocess.run(['./configure', '-without-icu'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir)
                if conf_proc.returncode != 0:
                    print('Configure Fail:', directory)
                    print(conf_proc.stderr.decode())
                    exit()

                # Recompile, Run regression test and record covered mutants
                with tempfile.NamedTemporaryFile(prefix='dredd-postgress-dredd-coverage') as temp_coverage_file:
                    coverage_filepath = temp_coverage_file.name
                    env_copy = os.environ.copy()
                    env_copy["DREDD_MUTANT_TRACKING_FILE"] = coverage_filepath
                    check_proc = subprocess.run(['make', 'check'], env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir)
                    if check_proc.returncode != 0:
                        print('Make Check Fail:', directory)
                        print(check_proc.stderr.decode())
                        continue
                    else:
                        copy_tree(os.path.join(temp_src_dir, 'tmp_install'), os.path.join(dredd_coverage_output_directory, directory.replace('/', '-') ))
                        # exit(3) 

                    temp_coverage_file.seek(0)
                    covered_mutants = set(sorted([int(line.rstrip()) for line in temp_coverage_file]))
                    shutil.copy(temp_coverage_file.name, output_path)
                

                print(directory, ':', len(covered_mutants), '/', total_mutants)

    except TimeoutError:
        continue       
            




            
            

            


        

