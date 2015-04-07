import jshandler
import json
import cherrypy
import logging


# Pool of child processes running javascript 
JsPool = jshandler.JsHandlerControl()



class RouteController:


 
    """
    Cherrpy mixes the post and get parameters into a single
    dictionary as a result there could be collissions, this
    class separates the two.
    """
    def __init__(self, path, ident, options):
        self.ident = ident
        self.options = options
        self.path = path

    def _process_response(self, res):
        "Process response from child process"

        try:
            dict(res)
        except:
            res = {'data': res}

        if res.get('error',False):
            status = res.get('status',500) 
            raise cherrypy.HTTPError(status,res['error'])

        if res.get('exc',False):
            status = res.get('status',500)
            raise cherrypy.HTTPError(status,res['exc'])
    
        if self.options.get('json',False):
            res['data'] = json.dumps(res['data'])

        if 'permissionLevel' in res:
            pl = int(res['permissionLevel'])
            cherrypy.session[ cherrypy.session.id ] = pl

        logging.debug("res = %s" % str(res))
        return res['data']


    # generator used for streaming.
    def generator(self, jsh, idx, req, options):
        global JsPool

        error = None

        # explicitly enter javascript context
        jsh.transaction({
            'start-streaming':True,
            'streaming': True,
            'ident': req['ident']
        })

        # set the streaming flag so we follow a different
        # control path in the js handler.
        req['streaming'] = True
        req['bytes_read'] = 0
        while True:
            res = jsh.transaction(req)
            if 'success' in res:
                continue 

            if 'error' in res:
                error = res['error']
                break

            # fetch streaming data
            data = res.get('data',None)
            if not data or len(data) == 0:
                # no more data we're done.
                break

            req['bytes_read'] += len(data)

            # return a generator to cherrypy, have it call
            # the next method until there is no more data.
            yield data

        # explicitly leave javascript context
        jsh.transaction({
            'stop-streaming':True,
            'streaming': True,
            'ident': req['ident']
        })

        # free this child process to work on other requests.
        JsPool.checkin(jsh, idx)

        if error:
            raise RuntimeError, error



    def __handler(self, method, qs_params ):
        # see if there is post data.
        try:
            post_data = cherrypy.request.body.params
        except:
            post_data = {}

        # separate the query parameters from the post data
        for k in set(qs_params.keys()).intersection(set(post_data.keys())):
            if type(qs_params[k]) == type([]):
                # remove collision array, the first element is the query string
                # parameter
                qs_params[k] = qs_params[k][0]
            else:
                # this is really post data that was mixed in.
                del qs_params[k]

        req = {
            "path": self.path,
            "method": method,
            "qs_params": qs_params,
            "post_data": post_data,
            "ident": self.ident
        }

        # checkout a javascript sub process from the pool
        # to use.
        jsh, idx = JsPool.checkout()
        if 'stream' in self.options and self.options['stream']:
            return self.generator(jsh,idx,req,self.options)
        else:
            # not-streaming, ajax request or a dynamic web page.
            res = jsh.transaction(req)
            JsPool.checkin(jsh, idx)
            return self._process_response(res)

    __handler._cp_config = {'response.stream': True} 



    def __call__(self, **params):

        # if configured check permissions based on our session id
        if 'permissionLevel' in self.options:
            r_pl = int(self.options['permissionLevel'])
            if cherrypy.session.id in cherrypy.session:
                user_pl = cherrypy.session[cherrypy.session.id]
                if r_pl >= user_pl:
                    raise cherrypy.HTTPError(403,"Unauthorized") 

        return self.__handler("unknown", params )

    """ 
    @cherrypy.expose
    def GET(self, **params):
        print "GET", self.path
        return self.__handler("GET", params )
    @cherrypy.expose
    def POST(self, **params):
        print "POST", self.path
        return self.__handler("POST", params )
    @cherrypy.expose
    def PUT(self, **params):
        return self.__handler("PUT", params )
    @cherrypy.expose
    def DELETE(self, **params):
        return self.__handler("DELETE", params )
    """


class RouteRegistry:
    def __init__(self, api):
        self.api = api
        self.dispatch = cherrypy.dispatch.RoutesDispatcher()

    def start_processes(self, cache_size):
        global JsPool

        JsPool.setup( self.api, cache_size )


    def register(self, path, jscb, options ):
        opt = dict(options)
        ident = jshandler.AddJsCb( path, jscb, opt )
        control = RouteController( path, ident, opt )

        # are we filtering for a particular url method ?
        method = opt.get('method',None)

        if method:
            method = str(method.upper())
            methods = ['GET','POST','PUT','DELETE']
            if method not in methods:
                raise ValueError, \
                    "options.method must be one of %s" % ",".join(methods)
            self.dispatch.connect(
                 name=path,
                 route=path,
                 controller=control,
                 conditions=dict(method=[method])
            )
        else:
            self.dispatch.connect(name=path,
                 route=path, controller=control )



