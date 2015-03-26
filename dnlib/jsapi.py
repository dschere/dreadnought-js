"""
Defines the api used by the javascript program to tie in directly 
into python.
"""

import PyV8
import require
import jshandler
import cherrypy
import jsroute
import logging
import traceback
import os
import types
import json 
import sys

Version = "Version %(major)d.%(minor)d [%(name)s]" % {
    'major': 0,
    'minor': 1,
    'name' : 'Ironclad'
}
 
class HandlerAPI(PyV8.JSClass):
    """
    API used by HTTP handlers. 
    """

    def __init__(self):
        PyV8.JSClass.__init__(self)

        for k,v in __builtins__.items():
            if k not in ("chr","ord","map","filter","reduce","open","close","sum","getattr",
                "hasattr"):
                continue     

            class pyfuncobj:
                def __init__(self, v):
                    self.__doc__ = v.__doc__
                    self.v = v
                def __call__(self, *args ):
                    return self.v( *args )
            f = pyfuncobj(v)
            setattr(self,k,f) 

    def isObject(self, obj):    return str(type(obj)).find('PyV8.JSObject') != -1
    def isNULL(self, obj):      return str(type(obj)).find('PyV8.JSNULL') != -1
    def isUndefined(self, obj): return str(type(obj)).find('PyV8.JSUndefined') != -1
    def isArray(self, obj):     return str(type(obj)).find('PyV8.JSArray') != -1
    def isFunction(self, obj):  return str(type(obj)).find('PyV8.JSFunction') != -1
    def isInt(self, obj):       return type(obj) == type(0)
    def isFloat(self, obj):     return type(obj) == type(0.0)

    def sprintf(self, fmt, *args):
        """
        Return a formatted string like the C style sprintf

        :Parameters:
        - `fmt`: string containing format information. This format has two
                 types. The first type is normal C style format string containing
                 %d,%f,%s ect. The second type is used if a javascript object is
                 passed in as an argument. In this type the format string is mapped
                 to key value pairs like this:
                     sprintf("%(name)s is awake.", {name:'Bob'}) -> "Bob is awake."
        - `args`: Variable length arguments, or a single javascript object as an   
                  argument.                 
        """ 
        if len(args) == 1 and self.isObject(args[0]):
            return fmt % dict(args[0])
        else:
            return fmt % args

    def addRequirePath(self, path):
        """
        Add a specified path to the RequirePath array used by the require function.

        :Parameters:
        - `path`: A valid directory to be added to the RequirePath internal variable.  
        """ 
        require.addPath( path )        

    def removeRequirePath(self, path):
        """
        Remove the specified path to the RequirePath array used by the require function.

        :Parameters:
        - `path`: A valid directory to be removed from the RequirePath internal variable.  
        """
        require.removePath( path )        
   
    def require(self, spec, options={'language':'javascript'} ):
        "%s" % require.DocString
        return require.require( spec, options )

    def vardump(self, obj, display=True):
        def expand(obj):
            if self.isObject(obj) or type(obj) == types.DictType:
                n = dict(obj)
                for k, v in n.items():
                    n[k] = expand(v)
            elif self.isArray(obj) or type(obj) in (types.ListType,types.TupleType):
                n = list(obj)
                n = map(expand, n)
            else:
                n = repr(obj)
            return n

        n = expand(obj)
        text = json.dumps(n,sort_keys=True,indent=4)+"\n" 
        if display:
            sys.stdout.write(text)
            sys.stdout.flush()
        return text

    def showApi(self):
        names = dir(self)
        names.sort()  
        for k in names:
             
            if not k or (len(k) > 2 and k[:2] == "__"):
                continue

            v = getattr(self,k)
            if not v:
                continue

            if callable(v) and type(k) == type("") and v.__doc__:
                print "%-32s" % k
                print "    ",v.__doc__
                print "-" * 32


class RootLogger():
    def __init__(self):
        self.fmt = logging.Formatter(
            fmt='%(asctime)s %(name)s [%(levelname)s] %(message)s')

    def _log(self, level, message):
        msg = self.fmt.format(logging.LogRecord(\
            "root",level,"/",1,"%s",message,None,None))
        # no format for the global logger so we can use info 
        logging.info( msg )
  
    def debug(self, msg):  
        self._log(logging.DEBUG, msg)
    def info(self, msg):  
        self._log(logging.INFO, msg)
    def warning(self, msg):  
        self._log(logging.WARING, msg)
    def error(self, msg):  
        self._log(logging.ERROR, msg)
    def critical(self, msg):  
        self._log(logging.CRITICAL, msg)


class RootAPI(HandlerAPI):
    "Used by the root script, to setup handlers and system settings"

    def __init__(self): 
        HandlerAPI.__init__(self)

        self.logger = RootLogger()
        self.registry = jsroute.RouteRegistry( HandlerAPI() )
        

        self._settings = {
            'host'        :"0.0.0.0",
            'port'        : 8080,
            'thread_pool' : 20,
            'js_pool'     : 20,
            'favicon'     : os.environ['HOME']+"/.dreadnought-js/favicon.ico"
        }

        self._config = {
            '/': {
                'request.dispatch': self.registry.dispatch 
            }
        }

    def register(self, path, jscb, options ):
        self.logger.debug("register('%s',%s,%s)" % (path, jscb, options ))
        try:  
            self.registry.register( path, jscb, options )
        except:
            self.logger.error( traceback.format_exc() )
            raise

    def getLogger(self):
        return self.logger

            

    def mainloop(self):
        "Interface to cherrypy's mainloop"
                 
        # launch a set of child processes to handle each request
        # within a child process. 
        self.registry.start_processes( self._settings.get('js_pool',20) )

        self._config['global'] = {
            'server.socket_host' : self._settings.get('host',"0.0.0.0"),
            'server.socket_port' : self._settings.get('port',8080),
            'server.thread_pool' : self._settings.get('thread_pool',20)
        }

        sdir = self._settings.get('static_dir',None)
        if sdir:
            self.logger.debug("adding static content directory %s" % sdir)
            self._config["/"]['tools.staticdir.on'] = True
            self._config["/"]['tools.staticdir.dir'] = sdir

        self._config['/favicon.ico']={
            'tools.staticfile.on': len(self._settings.get('favicon','')) > 0,
            'tools.staticfile.filename': self._settings.get('favicon','') 
        }
            

        cherrypy.tree.mount(root=None, config=self._config )

        # block forever servicing requests.
        cherrypy.quickstart( script_name="/", config=self._config )



    def getSettings(self):
        return self._settings

    def setSettings(self, s):        
        self._settings = dict(s)
    



def run( scriptfile, opts  ):
    """ Execute javascript, setup cherrypy and route url paths to
        registered callbacks.
    """
    levelname = opts.get('loglevel','DEBUG')
    if not hasattr(logging,levelname):
        raise RuntimeError, "Unknown log level %s, must be DEBUG|INFO|WARNING" % levelname

    logging.basicConfig(flename=opts.get('logfile','/dev/stdout'),
        level=getattr(logging,levelname), format="%(message)s" )
         
    basedir = os.path.dirname(os.path.abspath(scriptfile))
    require.RequirePath = [basedir+"/", basedir+"/.d-mods/"] + require.RequirePath  

    code = open(scriptfile).read()
    api = RootAPI() 
    root_context = PyV8.JSContext( api )
    root_context.enter()
    try:
        root_context.eval( code )
    except KeyboardInterrupt:
        pass 
    root_context.leave()   
    
    

