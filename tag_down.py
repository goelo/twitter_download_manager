import runpy
import sys


if __name__ == '__main__':
    runpy.run_module('back.crawler.tag_down', run_name='__main__')
else:
    from back.crawler import tag_down as _module

    sys.modules[__name__] = _module
