import PyV8
import sys
from dnlib2.jsapi import HandlerAPI
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

class shell_commands:
    def __init__(self, shell):
        self.shell = shell
        self.display_vars = set()
        self.dispatch = {
            "%display": {
                "check": lambda args: len(args) == 1,
                "usage": "Usage: %display <varname>",
                "cb": self.display,
                "help": "register variables to be shown continuously" 
            },
            "%undisplay": {
                "check": lambda args: len(args) == 1,
                "usage": "Usage: %undisplay <varname>",
                "help": "unregister display variables",
                "cb": self.undisplay 
            },
            "%show": {
                "check": lambda args: len(args) == 1,
                "usage": "Usage: %show <varname>",
                "help": "show the value of a variable",
                "cb": self.show 
            }
        }

    def help(self):
        s  = "    %-16s | %-32s\n" % ('Command','Description')
        s += "----%16s-+-%32s\n" % ("-" * 16, "-" * 32)
        klist = self.dispatch.keys()
        klist.sort()
        for cmd in klist:
            desc = self.dispatch[cmd]['help']
            s  += "    %-16s | %-32s\n" % (cmd,desc) 
        return s        

    def show(self, args):
        var = args[0]
        if hasattr(self.shell.ctxt.locals,var):
            v = getattr(self.shell.ctxt.locals,var)
            try:
                dict(v)
                print "%12s" % var,":", dict(v)
            except:
                try:
                    list(v)
                    print "%12s" % var,":", list(v)
                except:
                    print "%12s" % var,":", str(v)
        else:
            print "Undefined variable", var       

    def _display_set(self):
        for var in self.display_vars:
            self.show([var])

    def display(self, args):
        self.display_vars.add( args[0] ) 

    def undisplay(self, args):
        self.display_vars.remove( args[0] ) 
     

    def proc(self, line):
        t = line.split()
        if len(t) > 0 and t[0] in self.dispatch:
            args = t[1:]
            if not self.dispatch[ t[0] ]['check'](args):
                print  "<error>", self.dispatch[ t[0] ]['usage']
            else:
                self.dispatch[ t[0] ]['cb'](args) 
            return True
        return False    

class Shell(object):
    def __init__(self):
        self.ctxt = PyV8.JSContext( HandlerAPI() )
        self.ctxt.enter()
        self.cmd = shell_commands(self)

    def evaluate(self, line):
        if not self.cmd.proc(line):
            r = self.ctxt.eval( line )
            if r:
                print r
        self.cmd._display_set()

    def __del__(self):
        self.ctxt.leave()  

def run():
    sh = Shell()
    print """
Welcome to the Interactive dreadnought-js shell version 0.1"

Builtin shell commands:
%s

For multiline commands such as functions enter '\\' at the end of 
each line and it will be concatonated to the previous line. The
multiline command will be executed if the shell doesn't see the
'\\' at the end of line.

Press Control-D to exit:


""" % sh.cmd.help()

    buf = ""
    while True:
        try:
            line = raw_input(">")
        except EOFError:
            break
        if line[-1] == '\\':
            buf += line[:-1]
        elif len(buf) > 0:
            sh.evaluate(buf)
            buf = ""
        else:
            try: 
                sh.evaluate(line)
            except:
                print sys.exc_info()[1] 

if __name__ == '__main__':
    run()

    


