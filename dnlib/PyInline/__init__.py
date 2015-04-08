"""PyInline

The main package for the Inline for Python distribution.

The PyInline module allows you to put source code from other
programming languages directly "inline" in a Python script or
module. The code is automatically compiled as needed, and then loaded
for immediate access from Python. PyInline is the Python equivalent of
Brian Ingerson's Inline module for Perl (http://inline.perl.org);
indeed, this README file plagerizes Brian's documentation almost
verbatim.
"""

__revision__ = "$Id: __init__.py,v 1.3 2001/08/29 18:27:25 ttul Exp $"
__version__ = "0.03"

import C

def build(**args):
    """
    Build a chunk of code, returning an object which contains
    the code's methods and/or classes.
    """


    
    # Create a Builder object to build the chunk of code.
    b = C.Builder(**args)

    # Build the code and return an object which contains whatever
    # resulted from the build.
    return b.build()

    


