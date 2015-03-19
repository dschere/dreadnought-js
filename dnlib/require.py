"""
Implements dreadnought's version of require to load modules that
can be written in javascript, python or C.


"""
import sys
import requests
import urlparse
import os
import PyInline
import traceback
import PyV8



RequirePath = ['./','./d-mods/','%s/.d-mods/' % os.environ['HOME'],\
    '/usr/local/dreadnought/d-mods']
sys.path += RequirePath 


class RequireError( RuntimeError ):
    pass

def addPath( path ):
    global RequirePath
    if path not in RequirePath:
        RequirePath.append( path )
        if path not in sys.path:
            sys.path.append( path )

def removePath( path ):
    global RequirePath
    if path in RequirePath:
        RequirePath.remove(path)
        if path in sys.path:
            sys.path.remove( path )
 

def require( spec, options ):
    lang = "javascript"
    if hasattr(options,"language"):
        lang = options.language

    if lang == 'javascript':
        return _require_js( spec, options )
    elif lang == 'python':
        return _require_py( spec, options )
    elif lang == 'c':
        return _require_c( spec, options )
    else:
        raise RequireError, "options.language must be one of [javascript,python,c]"

JsCode = {}
def _file_data( filename ):
    global JsCode
    if os.access( filename, os.R_OK ):
        modtime = os.stat(filename).st_mtime
        if filename in JsCode:
            (mt, code) = JsCode[filename]
            if mt == modtime: 
                return code      
        code = open(filename).read()
        JsCode[filename] = (modtime,code)
        return code
            


def _require_c( filename, options ):
    mod = PyV8.JSClass()
    data = _file_data( filename )
    if data:
        PyInline.build(code=data, targetmodule=mod, language="C")
        return mod
    else:
        raise RequireError, "Unable to locate or read %s" % filename


def _require_py( filename, options ):
    # behavior is the same as python import only we are using the RequiredPath 
    # in conjuncture with sys.path
    if filename[-3:] == ".py":
        filename = filename[:-3]
    
    if len(filename.split(os.sep)) > 1:

        oldpath = sys.path
        p = filename.split(os.sep)
        sys.path = [os.sep.join(p[:-1])] + sys.path
        m = __import__( p[-1] )
        sys.path = oldpath

        return m
    else:
        return __import__( filename )


def _require_js( filename, options ):
    # check search path for 
    global RequirePath  
    
    if filename[-3:] != ".js":
        filename += ".js"

  
    if len(filename.split(os.sep)) > 1:
        # Then this is an absolute path ..
        pathname = filename
        data = _file_data( pathname )
        if not data:
            raise RequireError, "Path %s either does not exist or not readable" % pathname 
    else: 
        data = None
        # search for filename within predefined search path 
        for path in RequirePath:
            pathname = path + filename
            data = _file_data( pathname )
            if data:
                break # terminate search  

    if data:
        # evaluate module and move variables/functions to a 
        # object named the same as the file without the extension.
        # So if fubar.js contains foo(), then we define
        # a global object fubar and add foo as a member
        # like this: fubar.foo 

        # local context used as a sandbox for evaluating modules.
        with PyV8.JSContext() as context:
            modname = filename.split('/')[-1].split('.')[0]
            prev_namespace = set(dir(context.locals))
            try:
                context.eval( data )
            except:
                et, ev, e_tb = sys.exc_info()
                msg = "[%s]\n\t %s" % ( pathname, ev )
                raise RequireError, msg
 
            curr_namespace = set(dir(context.locals))
            mod = PyV8.JSClass()
            for n in list(curr_namespace - prev_namespace):
                v = getattr(context.locals,n)
                setattr(mod,n,v)
                delattr(context.locals,n)

            return mod 
    else:
        msgfmt = "Unable to find %s or was not readable in any search path %s"
        msg = msgfmt % (filename,str(RequirePath))
        raise RequireError, msg           




def unittest():
    options =  PyV8.JSClass()

    try:
        m = require( "../../test/data/bad" , options )
    except:
        print "got expected error", sys.exc_info()

    options.language = "python"
    m = require("../../test/data/junk.py", options )
    assert 11 == m.pyfunc(10)

    m = require("os", options)
    assert '.' == m.curdir

    options.language = "c"
    m = require("../../test/data/test.c",options)
    print m.my_add( 10, 20.0 )     
 
    print "JsCode:",
    print JsCode
    
if __name__ == '__main__':
    unittest()

