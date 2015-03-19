
import PyV8
import require
import jshandler
import cherrypy
import jsroute
import logging

class HandlerAPI(PyV8.JSClass):

    def isObject(self, obj):    return str(type(obj)).find('PyV8.JSObject') != -1
    def isNULL(self, obj):      return str(type(obj)).find('PyV8.JSNULL') != -1
    def isUndefined(self, obj): return str(type(obj)).find('PyV8.JSUndefined') != -1
    def isArray(self, obj):     return str(type(obj)).find('PyV8.JSArray') != -1
    def isFunction(self, obj):  return str(type(obj)).find('PyV8.JSFunction') != -1
    def isInt(self, obj):       return type(obj) == type(0)
    def isFloat(self, obj):     return type(obj) == type(0.0)
    def str(self, obj):         return str(obj)
    def int(self, obj):         return int(obj)
    def repr(self, obj):        return repr(obj)


    def require(self, spec, options ):
        return require.require( spec, options )


    def __getattr__(self, name):
        if hasattr(__builtins__,name):
            return getattr(__builtins__,name)

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
            'js_pool'     : 20
        }

        self._config = {
            '/': {
                'request.dispatch': self.registry.dispatch 
            }
        }

    def register(self, path, jscb, options ):
        self.registry.register( path, jscb, options )


    def getLogger(self):
        return self.logger

    def mainloop(self):
         
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
            self._config['/static'] = {
               'tools.staticdir.on'  : True,
               'tools.staticdir.dir' : sdir
            }

        cherrypy.tree.mount(root=None, config=self._config )

        # block forever servicing requests.
        cherrypy.quickstart( config=self._config )


    def settings(self):
        return self._settings

    



def run( scriptfile, opts  ):
    """ Execute javascript, setup cherrypy and route url paths to
        registered callbacks.
    """

    logging.basicConfig(flename=opts.get('filename','/dev/stdout'),
        level=logging.DEBUG, format="%(message)s" )
          
    code = open(scriptfile).read()
    api = RootAPI() 
    root_context = PyV8.JSContext( api )
    root_context.enter()
    root_context.eval( code )
    root_context.leave()   
    
    

