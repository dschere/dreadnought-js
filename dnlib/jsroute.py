import jshandler
import json


JsPool = jshandler.JsHandlerControl()



class RouteController:
    """
    Cherrpy mixes the post and get parameters into a single
    dictionary as a result there could be collissions, this
    class separates the two.
    """
    def __init__(self, ident, options):
        self.ident = ident
        self.options = options

    def _format_response(self, res):
        if self.optons.get('json',False):
            res = json.dumps(res)
        if res.get('error',False):
            raise RuntimeError,  res['error']
        return res


    # generator used for streaming.
    def generator(self, jsh, idx, req, options):
        global JsPool

        error = None

        # explicitly enter javascript context
        jsh.transcation({
            'start-streaming':True,
            'streaming': True
        })

        # set the streaming flag so we follow a different
        # control path in the js handler.
        req['streaming'] = True
        while True:
            res = jsh.transcation(req)
            if 'error' in res:
                error = res['error']
                break

            # fetch streaming data
            data = res.get('data',None)
            if not data:
                # no more data we're done.
                break

            # return a generator to cherrypy, have it call
            # the next method until there is no more data.
            yield data

        # explicitly leave javascript context
        jsh.transcation({
            'stop-streaming':True,
            'streaming': True
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
            "path": self.js_handler.ident,
            "method": method,
            "qs_params": qs_params,
            "post_data": post_data,
            "ident": self.ident
        }

        # checkout a javascript sub process from the pool
        # to use.
        jsh, idx = JsPool.checkout()
        if 'stream' in self.options and self.options['stream']:
            return self._stream_generator(jsh,idx,req,self.options)
        else:
            # not-streaming, ajax request or a dynamic web page.
            res = jsh.transcation(req)
            JsPool.checkin(jsh, idx)
            return self._format_response(res)




    def __call__(self, **params):
        return self.__handler("unknown", params )


    def GET(self, **params):
        return self.__handler("GET", params )
    def POST(self, **params):
        return self.__handler("POST", params )
    def PUT(self, **params):
        return self.__handler("PUT", params )
    def DELETE(self, **params):
        return self.__handler("DELETE", params )


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
        control = RouteController( ident )

        # are we filtering for a particular url method ?
        method = opt.get('method',None)

        if method:
            method = method.upper()
            methods = ['GET','POST','PUT','DELETE']
            if method not in methods:
                raise ValueError, \
                    "options.method must be one of %s" % ",".join(methods)
            self.dispatch.connect(
                 name=path,
                 route=path,
                 controller=control,
                 conditions=method
            )
        else:
            self.dispatch.connect(name=path,
                 route=path, controller=control )



