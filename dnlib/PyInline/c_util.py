# Utility Functions and Classes for the PyInline.C module.

import re
c_directive = '\s*#.*'
c_cppcomment = '//.*'
c_simplecomment = '/\*[^*]*\*+([^/*][^*]*\*+)*/'
c_doublequote = r'(?:"(?:\\.|[^"\\])*")'
c_singlequote = r'(?:\'(?:\\.|[^\'\\])*\')'
c_comment = re.compile("(%s|%s)|(?:%s|%s|%s)" % (c_doublequote,
                                                 c_singlequote,
                                                 c_cppcomment,
                                                 c_simplecomment,
                                                 c_directive))

const = re.compile('\s*const\s*')
star = re.compile('\s*\*\s*')
_c_pandn = "((?:(?:[\w*]+)\s+)+\**)(\w+)"
c_pandm = re.compile(_c_pandn)
_c_function = _c_pandn + "\s*\(([^\)]*)\)"
c_function_def = re.compile("(?:%s|%s)|(%s)" % (c_doublequote,
                                                c_singlequote,
                                                _c_function + "\s*(?:\{|;)"))
c_function_decl = re.compile(_c_function + "\s*;")

trimwhite = re.compile("\s*(.*)\s*")

def preProcess(code):
    return c_comment.sub(lambda(match): match.group(1) or "", code)

def findFunctionDefs(code):
    functionDefs = []
    for match in c_function_def.findall(code):
        if match[0]:
            functionDefs.append({'return_type': trimWhite(match[1]),
                                 'name': trimWhite(match[2]),
                                 'rawparams': trimWhite(match[3])})
    return functionDefs


_wsLeft = re.compile("^\s*")
_wsRight = re.compile("\s*$")
def trimWhite(str):
    str = _wsLeft.sub("", str)
    str = _wsRight.sub("", str)
    return str
    
if __name__ == '__main__':
    x = """#include <stdio.h>
const char* foo = "long int x(int a) {";
long int barf(int a, char *b) {
  int x, y;
  int x[24];
}

long int *** fkfkfk(char * sdfkj, int a, char *b) {
  int x, y;
}

"""
    print findFunctionDefs(x)
                                    

