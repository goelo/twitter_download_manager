import runpy
import sys


if __name__ == '__main__':
    runpy.run_module('back.tools.local_login_helper', run_name='__main__')
else:
    from back.tools import local_login_helper as _module

    sys.modules[__name__] = _module
