#!/usr/bin/env python

from distutils.core import setup
import sys
import os





setup(
    name="dreadnought-js",
    version="0.1",
    author="cloudslicer",
    author_email="dave.avantgarde@gmail.com",
    url="https://github.com/dschere/dreadnought-js",
    packages =["dnlib"] ,
    py_modules=['dnshell']
)

if __name__ == '__main__':
    if "build" in sys.argv:
        os.system("./post_build.sh")       
    elif "install" in sys.argv:
        os.system("./post_install.sh")       
 



