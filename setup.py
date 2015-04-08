#!/usr/bin/env python

from distutils.core import setup
import sys
import os



setup(
    name="dreadnought-js",   
    description = 'Dreadnought is a synthesis of cherrypy and JavaScript to create a full featured web server for JavaScript applications', 
    version="0.1.1",
    author="dschere",
    author_email="dave.avantgarde@gmail.com",
    url="https://github.com/dschere/dreadnought-js",
    download_url = "https://github.com/dschere/dreadnought -js/tarball/0.1",
    packages =["dnlib","dnlib/PyInline"] ,
    py_modules=['dnshell','dreadnought'],
    package_data={'': ['CHANGES.txt','LICENSE.txt','dn-env.sh','install.sh','favicon.ico','dn']},
    keywords = ['webserver', 'JavaScript','cherrypy']
)

