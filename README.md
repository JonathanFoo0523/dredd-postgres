
```

sudo apt install build-essential libghc-terminfo-dev libzstd-dev zlib1g-dev cmake ninja-build

# Clone dredd
git clone --recursive https://github.com/mc-imperial/dredd.git
cd dredd

# Install Clang/LLVM
cd third_party
curl -Lo clang+llvm.tar.xz https://github.com/llvm/llvm-project/releases/download/llvmorg-16.0.4/clang+llvm-16.0.4-x86_64-linux-gnu-ubuntu-22.04.tar.xz
tar xf clang+llvm.tar.xz
rm -r clang+llvm
mv clang+llvm-16.0.4-x86_64-linux-gnu-ubuntu-22.04 clang+llvm
rm clang+llvm.tar.xz
cd ..

# Build
mkdir build && cd build
cmake -G Ninja .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
cp src/dredd/dredd ../third_party/clang+llvm/bin
```


```
# install
tar -Lo postgresql-16.3.tar.gz https://ftp.postgresql.org/pub/source/v16.3/postgresql-16.3.tar.gz
tar xf  postgresql-16.3.tar.gz 
rm postgresql-16.3.tar.gz 
cd postgresql-16.3

sudo apt install libreadline-dev
./configure --without-icu

sudo apt install bear
bear -- make
# make all
```

```
sudo apt install bear
bear -- make
```

```
# APPLY DREDD HERE
make
DREDD_ENABLED_MUTATION=2 make check
```

```
LD_LIBRARY_PATH=/home/ubuntu/postgresql-16.3/tmp_install/usr/local/pgsql/lib ./tmp_install/usr/local/pgsql/bin/initdb -D /home/ubuntu/postgres_data
tmp_install/usr/local/pgsql/bin/pg_ctl -D /home/ubuntu/postgres_data -l logfile -o "-F -p 4000" start
LD_LIBRARY_PATH=/home/ubuntu/postgresql-16.3/tmp_install/usr/local/pgsql/lib ./tmp_install/usr/local/pgsql/bin/createdb test
```

## Usage
```
python3 dredd_coverage_runner.py

rm **/*.lock
```

