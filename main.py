import runpy
import sys


if __name__ == '__main__':
    runpy.run_module('back.crawler.main', run_name='__main__')
else:
    from back.crawler import main as _module

    sys.modules[__name__] = _module
