import logging
import jsapi
import os


def format_args( args ):
    "Support formatting log messages" 

    def _stringify( msg):
        if type(msg) == type(""):
            return msg
        return jsapi.expand(msg)

    np = len(args)
    if np == 0:
        return ""
    elif np == 1:
        return _stringify(args[0]) 
    else:
        if np == 2 and type(args[0]) == type("") and \
          str(type(args[1])).find('PyV8.JSObject') != -1:
            # func("%(param1)s ..." % {param1:'hello'})
            return args[0] % dict(args[1]) 
        else:
            return args[0] % tuple(args[1:]) 


class jslogger(object):
    def __init__(self, logger):
        self.logger = logger

    def wrap(self, func ):
        class _func_wrapper:
            def __init__(self, f):
                self.func = f
            def __call__(self, *args):
                self.func( format_args( args ) )  
        return _func_wrapper( func )

    def setLevel(self, n):
        if n not in ('debug','info','warn','error','critical'):
            raise RuntimeError, "log level must be either debug,info,warn,error,critical"
        v = getattr(logging,n.upper())
        self.logger.setLevel( v )

    def __getattr__(self, n):
        "wrap the traditional log functions to support formatted logging and object introspection "
        if n in ('debug','info','warn','error','critical'):
            return self.wrap( getattr(self.logger,n) )
        elif hasattr(self.logger,n):
            return getattr(self.logger,n)




class RootLogger():
    def __init__(self):
        self.fmt = logging.Formatter(
            fmt='%(asctime)s %(name)s [%(levelname)s] %(message)s')

    def _log(self, level, args):
        message = format_args( args )

        msg = self.fmt.format(logging.LogRecord(\
            "root",level,"/",1,"%s",message,None,None))
        # no format for the global logger so the log level doesn't matter
        # its just a way to get to the log file
        logging.info( msg )

    def debug(self, *args):
        self._log(logging.DEBUG, args)
    def info(self, *args):
        self._log(logging.INFO, args)
    def warning(self, *args):
        self._log(logging.WARING, args )
    def error(self, *args):
        self._log(logging.ERROR, args)
    def critical(self, *args):
        self._log(logging.CRITICAL, args)



class PipeLogger():
    """ Private logger for the javascript callbacks, this object routes log
        messages back to the parent process (cherrypy) for logging.
    """
    def __init__(self, logger_name, logLevel=logging.DEBUG):

        self.r,self.w = os.pipe()
        self.rr = os.fdopen(self.r,"r")
        self.ww = os.fdopen(self.w,"w")

        # create logger
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logLevel)

        # create console handler and set level to debug
        ch = logging.StreamHandler(self.ww)
        ch.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter(\
           '%(asctime)s %(name)s [%(levelname)s] %(message)s')

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        self.logger.addHandler(ch)

    def getLogger(self):
        return jslogger( self.logger )


    def fileno(self):
        return self.r

    def read(self, n=0xffff):
        return os.read( self.r, n )

    def close(self):
        self.rr.close()
        self.ww.close()


