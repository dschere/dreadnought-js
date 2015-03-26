import PyV8
import os
import sys
import traceback
import cherrypy
try:
    import cPickle as pickle
except:
    import pickle
import threading
import time
import logging
import select

class IOChannel(object):
    """ Interprocess communication using a pipe to exchange serialized python objects
        between a child process and the main process running cherrypy.
    """


    def __init__(self):
        self.r, self.w = os.pipe()

        self.reader = os.fdopen( self.r, "r" )
        self.writer = os.fdopen( self.w, "w" )

    def fileno(self):
        return self.r

    def recv(self):
        "un-serialize an incoming object"
        return pickle.load(self.reader)

    def send(self, obj):
        "serialize and send an object"
        pickle.dump(obj, self.writer)
        self.writer.flush()


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

    def fileno(self):
        return self.r

    def read(self, n=4096):
        return os.read( self.r, n )

    def close(self):
        self.rr.close()
        self.ww.close()


# global lookup table that maps an numeric identfier
# to tuple containing:
#    (javascript callback, callback argument, logger, options )
JsCbLookup = []

def AddJsCb( path, jscb, options ):

    # create a logger for this callback
    logger = PipeLogger( "[%s]%s" % (options.get('method','http'), path) )

    # get optional callback user arguments
    jsargs = options.get('args',None)

    # Append javascript callbacks to cherrypy routes to this table.
    r = len(JsCbLookup)
    JsCbLookup.append( (jscb, jsargs, logger, options,)  )
    return r


class JSHandler(object):
    """ This object represents the child process that handles incoming 
        web requests and sends responses back to cherrypy. 
    """

    def __init__(self, api):
        self.context = PyV8.JSContext( api )
        self.req_chan = IOChannel()
        self.res_chan = IOChannel()
        self.lock = threading.RLock()


    def start(self):
        pid = os.fork()
        if pid == 0:
            # double fork to prevent potential zombie processes.
            if os.fork() == 0:
                self.run()
                logging.info("child process exiting")

            # both child and grandchild terminate here.  
            os._exit(0)

    def transcation(self, req):
        # Send a request to the javascript callback, return the response along with
        # extra options associated with this callback.

        self.lock.acquire()
        try:
            (jscb, jsargs, logger, options) = JsCbLookup[ req['ident'] ]
            res  = self._transaction(logger, req)
        except:
            res = {'exc': traceback.format_exc() }
        self.lock.release()

        if "exc" in res:
            raise RuntimeError, res['exc']
        return res


    def _transaction(self, logger, req):
        p = select.poll()
        p.register( logger.fileno(), select.POLLIN )
        p.register( self.res_chan.fileno(), select.POLLIN )

        self.req_chan.send( req )
        while True:
            for (fd,evt) in p.poll(-1):
                if logger.fileno() == fd and evt & select.POLLIN:
                    # Note: root logger is configured as a passthrough with no
                    # formatting except %(message)s, this allows it to be a 
                    # collection point for the route loggers.
                    logging.info(logger.read()[:-1])

                elif self.res_chan.fileno() == fd and evt & select.POLLIN:

                    # completed transaction
                    res = self.res_chan.recv()
                    return res

                else:
                    # unexpected error, we should never get this but we
                    # need to handle it anyway.
                    n = {
                        logger.fileno(): 'logger',
                        self.res_chan.fileno(): 'response_pipe'
                    }
                    return {"exc": "%s error event=%x" % ( n[fd], evt )}


    def _handle_streaming(self, req):
        # streaming request controls the context and calls this
        # processes over and over until done.
        if req.get('start-streaming',False):
            self.context.begin()
            self.res_chan.send({
                'success': True
            })
        elif req.get('end-streaming',False):
            self.context.leave()
            self.res_chan.send({
                'success': True
            })
        else:
            return self._jsexec( req )

    def _jsexec( self, req ):
        # execute javascript command
        (jscb, jsargs, pipe_logger, options) = JsCbLookup[ req['ident'] ]

        self.context.locals.jscb = jscb 
        self.context.locals.jsargs = jsargs
        self.context.locals.logger =  pipe_logger.logger
        self.context.locals.req = req
        self.context.eval("var res = jscb(logger,req,jsargs);")
        return dict(self.context.locals.res) 
         

    def run(self):
        p = select.poll()
        p.register(self.req_chan.fileno(), select.POLLIN)
        while True:
            # detect a pipe closure
            for (fd,evt) in p.poll(-1):
                if (evt & select.POLLIN) == 0:
                    # exit run loop, kill process
                    return

            try:
                req = self.req_chan.recv()
                if req.get('streaming',False):
                    res = self._handle_streaming( req )
                else:
                    self.context.enter()
                    res = self._jsexec( req )
                    self.context.leave()
            except:
                res = {"exc": traceback.format_exc() }

            self.res_chan.send( res )



class JsHandlerControl:
    """

    Creates an array of child process handlers for all HTTP requests in the system.
    Each incoming request checks out a handler from the pool and returns it when it
    is done.

    """


    def __init__(self):
        self.handlers = []
        self.idx = 0
        self.lock = threading.RLock()

    def setup(self, api, cache_size):
        for i in range(0,cache_size):
            jsh = JSHandler(api)

            # (handler, in_use)
            self.handlers.append( (jsh,False) )

            # start cheild process to service requests in javascript.
            jsh.start()

    def checkout(self):
        # return handler and index, checkout the handler from the cache
        self.lock.acquire()
        result = None
        count = 0
        while not result:
            (jsh,inuse) = self.handlers[self.idx]
            if not inuse:
                result = (jsh,self.idx)
                self.handlers[self.idx] = (jsh,True)
            else:
                self.idx = (self.idx + 1) % len(self.handlers)
                count += 1
                if count > 0 and count % len(self.handlers):
                    # all handlers in use so we must pause to allow
                    # completion,
                    time.sleep(0.5)
        self.lock.release()
        return result

    def checkin(self, jsh, idx):
        # check handker back into cache
        self.lock.acquire()
        self.handlers[self.idx] = (jsh,False)
        self.lock.release()



