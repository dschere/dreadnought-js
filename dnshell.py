import PyV8
import sys
from dnlib.jsapi import RootAPI
import os
import readline

histfile = os.path.join(os.path.expanduser("~"), ".dn_shell_hist")
try:
    readline.read_history_file(histfile)
except IOError:
    pass
import atexit
atexit.register(readline.write_history_file, histfile)
del os, histfile

Version = "0.1"

class Shell(object):
    def __init__(self):
        self.ctxt = PyV8.JSContext( RootAPI() )
        self.ctxt.enter()

    def evaluate(self, line):
        return self.ctxt.eval( line )
        
    def __del__(self):
        self.ctxt.leave()  

def run():
    sh = Shell()
    print """
Welcome to the Interactive dreadnought-js shell version %s"

This is a simple javascript shell that lets you explore the dreadnought 
API.

 
To enter multiline statements end the line with '\\', so 
   var x = \\
     {\\
        a: 10\\
     };
   gets evaluated as 'var x = { a: 10 };'


To exit the shell press Control-D:


""" % Version

    buf = ""
    while True:
        try:
            if len(buf) == 0: 
                prompt = ">"
            else:
                prompt = " "

            line = raw_input( prompt )
        except EOFError:
            break

        if len(line) == 0:
            continue

        elif line[-1] == '\\':
            buf += line[:-1]
        elif len(buf) > 0:
            buf += line
            sh.evaluate(buf)
            buf = ""
        else:
            try: 
                sh.evaluate(line)
            except:
                print sys.exc_info()[1] 

if __name__ == '__main__':
    run()

    


