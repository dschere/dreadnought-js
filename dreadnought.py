#!/usr/bin/env python

from dnlib import jsapi
import dnshell
import argparse
import logging

DnDescription = \
"""
Dreadnought is a synthesis of Python, Cherrypy, and the V8 javascript engine
allowing javascript developers to built web applications that can incorporate 
the 1000's of mature libraries written in Python and C over the decades in 
a seamless fashion.
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=DnDescription,
        epilog="Version %s" % jsapi.Version 
    )
    parser.add_argument("--logfile", 
        help="the pathname of the log file; the default is stdout",
        default="/dev/stdout"
    )
    parser.add_argument("--loglevel", 
        help="logfilename, default is stdout",
        default="DEBUG"
    )
    parser.add_argument("--execute", 
        help="file to be executed, if not provided then it invokes an interactive shell",
        default=None
    )


    args = vars(parser.parse_args())
    if args['execute']:
        jsapi.run( args['execute'], args )
    else: 
        dnshell.run()
  



