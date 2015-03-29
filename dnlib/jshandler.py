import PyV8
import os
import traceback
try:
    import cPickle as pickle
except:
    import pickle
import threading
import logging
import select
import tempfile
import struct



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

class NpWriter:
    def __init__(self,fn):
        self.fn = fn 
        self.f = open(fn,'w')
        self.lock = threading.RLock()

    def send(self, obj): 
        data = pickle.dumps(obj)
        hdr = struct.pack('>i', len(data))
        self.lock.acquire()
        self.f.write(hdr+data)
        self.f.flush()
        self.lock.release()



class NpReader:
    def __init__(self, fn):
        self.f = open(fn,'r')
        self.fn = fn

    def fileno(self):
        return self.f.fileno()

    def _read_bytes(self, n):
        buf = ''
        while len(buf) < n:
            t = n - len(buf)
            buf += self.f.read(t)
            return buf

    def __del__(self):
        self.f.close()
        os.remove( self.fn )

    def recv(self):
        hdr = self._read_bytes(struct.calcsize('i'))
        size = struct.unpack(">i",hdr)[0]
        data = self._read_bytes(size)
        return pickle.loads(data)


class NamedPipeFactory:
    def __init__(self):
        fd, self.filename = tempfile.mkstemp()
        os.close(fd)
        if os.access(self.filename,os.F_OK):
            os.remove(self.filename)
        os.mkfifo(self.filename)

    def getWriter(self):
        return NpWriter( self.filename ) 

    def getReader(self):
        return NpReader(self.filename)

        


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

    def read(self, n=0xffff):
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

    def __init__(self, api, np_channels=None, set_context=True):
        if set_context:
            self.context = PyV8.JSContext( api )

        if not np_channels: 
            self.req_chan = IOChannel()
            self.res_chan = IOChannel()
        else:
            self.req_chan, self.res_chan = np_channels
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

    def transaction(self, req):
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

    # identify a special type of http handler
    OVERFLOW_HANDLER_IDX = -1

    def _overflow_handler_controller(self, api):
        """
        This process handles incoming http requests if no preforked processes are
        available. It uses named pipes and forks on demand which is less efficient  
        """  
        p = select.poll()
        p.register( self.overflow_chan.fileno(), select.POLLIN )
        hangup = False
        while not hangup:
            for (fd,evt) in p.poll(-1):
                if evt & select.POLLIN:
                    npf_pair = self.overflow_chan.recv()
                    if os.fork() == 0:
                        if os.fork() == 0:
                            # block until http handler creates the writer 
                            req_chan = npf_pair[0].getReader()
                            # block until the http handler creates the reader
                            res_chan = npf_pair[1].getWriter()
                            npipes = (req_chan,res_chan)
                            try:
                                # service http request using named pipes
                                # for transit instead of anonymous pipes.
                                JSHandler( api, npipes ).run()
                            except:
                                res_chan.send({
                                    'exc': traceback.format_exc()
                                })                               
                        os._exit(0)
                else:
                    hangup = True  

    def _overflow_iface(self):
        idx = self.OVERFLOW_HANDLER_IDX
        npf_pair = [ NamedPipeFactory(), NamedPipeFactory() ]
                 
        # send message to overflow control process, create a child process
        # based on this named pipe pair, the child process will create the
        # reader/writer compliments of the named pipes on the other end. 
        self.overflow_chan.send( npf_pair )
 
        # block until child opens reader
        req_chan = npf_pair[0].getWriter()

        # block until child opens writer
        res_chan = npf_pair[1].getReader()

        jsh = JSHandler( self.api, (req_chan,res_chan), set_context=False )

        return (jsh,idx)         

    def __init__(self):
        self.handlers = []
        self.idx = 0
        self.lock = threading.RLock()
        self.overflow_chan = IOChannel()
        self.api = None

    def setup(self, api, cache_size):
        """
        Setup an array of pre-forked processes to handle incoming requests
        along with a process to handle overflow conditions were we have to
        fork on demand.
        """  

        self.api = api
        for i in range(0,cache_size):
            jsh = JSHandler(api)

            # (handler, in_use)
            self.handlers.append( (jsh,False) )

            # start cheild process to service requests in javascript.
            jsh.start()

        # launch child process to handle overflow conditions when we
        # have no spare processes to service a request
        if os.fork() == 0:
            if os.fork() == 0:
                self._overflow_handler_controller(api)
            os._exit(0)  


    def checkout(self):
        """
        Return a preallocated javascript handler to service an incoming request. The js 
        handler contains a child process which routes the request to a javascript
        interpreter.

        If no preforked processes are available then pass to the overflow handler which
        will fork a handler on demand.
        """

        self.lock.acquire()
        result = None
        count = 0
        while not result:
            if count == len(self.handlers):
                result = self._overflow_iface()
            else:
                (jsh,inuse) = self.handlers[self.idx]
                if not inuse:
                    result = (jsh,self.idx)
                    self.handlers[self.idx] = (jsh,True)
                 
                self.idx = (self.idx + 1) % len(self.handlers) 
                count += 1
        self.lock.release()

        return result

    def checkin(self, jsh, idx):
        if idx != self.OVERFLOW_HANDLER_IDX:
            # check handler back into cache
            self.lock.acquire()
            self.handlers[self.idx] = (jsh,False)
            self.lock.release()















