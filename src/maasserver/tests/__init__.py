import os
import unittest

_test_suite = unittest.TestSuite()
for module in os.listdir(os.path.dirname(__file__)):
    if module == '__init__.py' or module[-3:] != '.py':
        continue
    mod = __import__(module[:-3], locals(), globals())
    _test_suite.addTests(unittest.TestLoader().loadTestsFromModule(mod))

def suite():
    return _test_suite
