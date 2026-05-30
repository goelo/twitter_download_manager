import sys

from back.crawler.output import cache_gen as _module

sys.modules[__name__] = _module
