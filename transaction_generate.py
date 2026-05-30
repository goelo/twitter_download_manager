import sys

from back.shared import transaction_generate as _module

sys.modules[__name__] = _module
