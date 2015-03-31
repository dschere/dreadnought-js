#!/usr/bin/env bash

# install dependancies
sudo pip install -r ./requirements.txt 

# setup directory structures
mkdir -p       $HOME/.dreadnought-js/modules
mkdir -p       $HOME/.dreadnought-js/.python-ctypes-modules
cp favicon.ico $HOME/.dreadnought-js

# build app
python ./setup.py build

# install 
sudo python ./setup.py install && sudo cp dn-env.sh dn dreadnought.py /usr/local/bin

