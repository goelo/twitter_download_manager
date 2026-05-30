import runpy
import sys


if __name__ == '__main__':
    runpy.run_module('back.crawler.web_runner', run_name='__main__')
else:
    from back.crawler import web_runner as _module

    sys.modules[__name__] = _module
