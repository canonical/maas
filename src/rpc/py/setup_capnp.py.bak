#!/usr/bin/env python
from distutils.core import setup
from Cython.Build import cythonize
from shutil import copyfile
import os
import re


files = ["network.capnp", "handshake.capnp", "region.capnp", "rack.capnp", "controller.capnp"]

for f in files:
  cpp_file = f + '.cpp'
  cplus_file = f + '.c++'
  cpp_mod = 0
  try:
    cpp_mod = os.path.getmtime(cpp_file)
  except:
    pass
  cplus_mod = 0
  try:
    cplus_mod = os.path.getmtime(cplus_file)
  except:
    pass
  if not os.path.exists(cpp_file) or cpp_mod < cplus_mod:
    if not os.path.exists(cplus_file):
      raise RuntimeError("You need to run `capnp compile -oc++` in addition to `-ocython` first.")
    copyfile(cplus_file, cpp_file)

    with open(f + '.h', "r") as file:
        lines = file.readlines()
    with open(f + '.h', "w") as file:
        for line in lines:
            file.write(re.sub(r'Builder\(\)\s*=\s*delete;', 'Builder() = default;', line))

setup(
    name="{'id': 13146874709407289632, 'filename': 'controller_capnp', 'imports': []}",
    ext_modules=cythonize('*_capnp_cython.pyx', language="c++", compiler_directives={'language_level': '3'})
)

