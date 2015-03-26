#!/usr/bin/env bash

mkdir -p  egg-cache
chmod 744 egg-cache/

export PYTHON_EGG_CACHE=$PWD/egg-cache
export PYTHON_PATH=$PWD:$PYTHONPATH:.

