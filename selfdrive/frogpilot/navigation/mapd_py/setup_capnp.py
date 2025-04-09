#!/usr/bin/env python
from distutils.core import setup
from Cython.Build import cythonize
from shutil import copyfile
import os
import re


files = ["offline.capnp", ]

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

# Cythonize the .pyx file
ext_modules = cythonize('*_capnp_cython.pyx', language="c++")

# Add the current directory to include_dirs for each extension
# This ensures the compiler finds the generated .capnp.h file
for ext in ext_modules:
    if not hasattr(ext, 'include_dirs'):
        ext.include_dirs = []
    ext.include_dirs.append('.')
    # Add libraries to link against (Cap'n Proto C++ libs)
    if not hasattr(ext, 'libraries'):
        ext.libraries = []
    ext.libraries.extend(['kj', 'capnp'])
    # Add directory where to find the libraries
    if not hasattr(ext, 'library_dirs'):
        ext.library_dirs = []
    ext.library_dirs.append('/usr/local/lib')

setup(
    name="{'id': 15724895971861741615, 'filename': 'offline_capnp', 'imports': []}",
    ext_modules=ext_modules
)