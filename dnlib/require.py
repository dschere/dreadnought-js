"""
Implements dreadnought's version of require to load modules that
can be written in javascript, python or C. In the case of C it
uses either PyInline to compile/link a C file and expose its methods to
javascript or ctypesgen which generates a python file using a C header
file along with a set of libraries. 

"""
import sys
import requests
import urlparse
import os
import PyInline
import traceback
import PyV8




RequirePath = ['%s/.dreadnought-js/modules/' % os.environ['HOME'],\
    '/usr/local/share/dreadnought-js/modules']
sys.path += RequirePath

CTYPES_MODULES_PATH = "%s/.dreadnought-js/.python-ctypes-modules" % os.environ['HOME']
os.system("mkdir -p %s" % CTYPES_MODULES_PATH)
sys.path.append( CTYPES_MODULES_PATH )


DocString = \
"""
This is a multipurpose function for importing code into a module. It
can work as like the require function in nodejs when passed in a javascript
module or it can import a python module, or compile/link/import a C module.

:Parameters:
- `spec`: This is a string containing the path of a file. If javascript it
          may contain the .js extension but it is not manditory. For python
          it is the module name to be passed into the python __import__ function
          containing the name of the module without the .py suffix. For a C
          module it is the path of the C module to be compiled/linked/imported 
          into this module.

- `options`:  
              +--------------+--------------------------------------------------+
              | Name         | Description                                      |
              +==============+==================================================+
              | language     | Maybe one of: javascript (default), python, c    |
              +--------------+--------------------------------------------------+
              | c_tool       | Used only for language=c, defaults to PyInline   |
              |              | for simple C optimizations, for more full        |
              |              | featured C integrations use tool='ctypesgen'.    |
              |              |                                                  | 
              |              | tool='PyInline' compiles/links code so spec      |
              |              |   should be a *.c file                           | 
              |              | tool='ctypesgen' is for existing libraries so    |
              |              |   spec should be a *.h file                      | 
              +--------------+--------------------------------------------------+
              | libs         | Used only for language=c, set this to an array   |
              |              | of dependancy libraries such as libs=['c','m']   |
              |              | for -libc -libm ect.                             |
              +--------------+--------------------------------------------------+
              | libdirs      | Used only for language=c, set this to an array   |
              |              | of dependancy library directories such as        |
              |              | libdirs=['/usr/local/lib']                       |
              +--------------+--------------------------------------------------+
              | includes     | Used only for language=c, set this to an array   |
              |              | of dependancy include directory files such as    |
              |              | includes=['/usr/local/include']                  |
              +--------------+--------------------------------------------------+
              



"""


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
        lang = options.language.lower()

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

    def _get(opt,k,defval):
        if hasattr(opt,k):
            return getattr(opt,k)
        return defval

    tool = _get(options, 'c_tool','PyInline')    
    library_dirs = _get(options, 'libdirs',None)
    libraries = _get(options,'libs',None)  
    includes = _get(options, 'includes',None)

    if tool == 'PyInline':
        extras = {} 
        if library_dirs:
            extras['library_dirs'] = library_dirs
        if libraries:
            extras['libraries'] = libraries  
        if includes:
            if os.name == 'posix':
                os.environ['GCC_INCLUDE_DIR'] = ':'.join(includes)
            else:
                os.environ['GCC_INCLUDE_DIR'] = ';'.join(includes)
        mod = PyV8.JSClass()
        data = _file_data( filename )
        if data:
            
            PyInline.build(code=data, targetmodule=mod, language="C", **extras)
            return mod
        else:
            raise RequireError, "Unable to locate or read %s" % filename

    elif tool == 'ctypesgen':  
        cmd = "ctypesgen.py %s " % filename
        if library_dirs:
            for x in library_dirs: 
                cmd += " --libdir=%s " % x
        if libraries:
            for x in libraries:
                cmd += " --library=%s " % x
        if includes:
            for x in includes:
                cmd += " --includedir=%s " % x
      
        modname = filename.split(os.sep)[-1].split('.')[0]
        modfile = CTYPES_MODULES_PATH+"/%s.py" % modname

        cmd += " -o %s.py " % modname
        print cmd
        os.system(cmd)

        m = __import__(modname)
        return m
 


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


    if filename[0] == '/':
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
            #modname = filename.split('/')[-1].split('.')[0]
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

    """
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
    """

    """
    options.language = "c"
    options.c_tool = "ctypesgen"
    options.libs = ["/usr/lib/x86_64-linux-gnu/libglib-2.0.so"]
    
    m = require("/usr/include/stdio.h", options)
    m.printf("--- hello from libc")
    """

    


if __name__ == '__main__':
    unittest()
