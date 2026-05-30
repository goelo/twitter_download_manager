import runpy
import sys


if __name__ == '__main__':
    runpy.run_module('back.crawler.runtime.anti_detection', run_name='__main__')
else:
    from back.crawler.runtime import anti_detection as _module

    sys.modules[__name__] = _module
