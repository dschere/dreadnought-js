#!/usr/bin/env python

from distutils.core import setup
import sys
import os





setup(
    name="dreadnought-js",    
    version="0.1",
    author="dschere",
    author_email="dave.avantgarde@gmail.com",
    url="https://github.com/dschere/dreadnought-js",
    download_url = "https://github.com/dschere/dreadnought -js/tarball/0.1",
    packages =["dnlib"] ,
    py_modules=['dnshell']
)

