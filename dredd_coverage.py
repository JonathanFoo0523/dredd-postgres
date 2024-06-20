import os
import sys
import glob
import subprocess
import tempfile
import re
from distutils.dir_util import copy_tree
import shutil
from filelock import Timeout, FileLock
import json


postgres_src = '/home/ubuntu/postgresql-16.3'
path_to_dredd = '/home/ubuntu/postgresql-16.3/src/backend/'
dredd_bin = '/home/ubuntu/dredd/third_party/clang+llvm/bin/dredd'
mutant_info_query_path = '/home/ubuntu/dredd/scripts/query_mutant_info.py'
coverage_output_directory = 'sample_coverage_output3'
dredd_coverage_output_directory = 'sample_dredd_output3/tracking'
with open(os.path.join(postgres_src, 'compile_commands.json'), 'r') as f:
    compile_command_database = json.load(f)

compiled_file = set()
for entry in compile_command_database:
    compiled_file.add(entry["file"])



for root, dirs, files in os.walk(path_to_dredd):
    c_files = [file for file in files if file.endswith('.c')]
    if len(c_files) == 0:
        continue


    directory = root.replace(path_to_dredd, '')
    output_path = os.path.join(coverage_output_directory, directory.replace('/', '-') + '.txt')

    
    if directory != 'utils/hash':
        continue

    # checked
    if os.path.isfile(output_path):
        continue

    # FAILED
    if directory in ['parser']:
        continue

    build_files = [file for file in c_files if os.path.join(root, file) in compiled_file]
    # print(build_files)
    if len(build_files) == 0:
        continue

    directory_lock = FileLock(os.path.join(coverage_output_directory, directory.replace('/', '-') + '.lock'), blocking=False)
    try:
        with directory_lock:    

            relative_path = os.path.join(path_to_dredd.replace(postgres_src + '/', ''), directory)

            with tempfile.TemporaryDirectory() as temp_src_dir:
                copy_tree(postgres_src, temp_src_dir)
                
                # Apply dredd with mutant-tracking To file
                dredd_proc = subprocess.run(' '.join([dredd_bin, ' '.join([os.path.join(temp_src_dir, relative_path) + f'/{f}' for f in build_files]), '--mutation-info-file', 'mutant-info.json', '--only-track-mutant-coverage', '--extra-arg="-Wno-everything"']), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=temp_src_dir, shell=True)
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

                shutil.copy(os.path.join(temp_src_dir, 'mutant-info.json'), f'sample_dredd_output2/mutation_info/{directory.replace('/', '-')}.json')

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
                        shutil.copy(os.path.join(temp_src_dir, 'src/test/regress/regression.diffs'), 'debug/regression.diffs')
                        shutil.copy(os.path.join(temp_src_dir, 'src/test/regress/regression.out'), 'debug/regression.out')
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
            




            
            

            


        

