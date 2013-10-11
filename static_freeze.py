#!/usr/bin/env python
'''This script generates, runs, and then deletes a Makefile which will compile a 
Python script into a standalone executable which is statically linked to the 
Python runtime.

To use this script, first generate a static Python library (see the parent 
directory's README.md).

Usage:

    python static_freeze.py test_file.py /path/to/static/libpythonX.X.a

Any additional arguments will be passed to the generated Makefile,
e.g. PYTHON=python3
'''

import sys
import os
from subprocess import call
major_version = sys.version_info[0]


make_template = '''# Makefile for creating our standalone Cython program
PYTHON=./python
CYTHON=cython
PYVERSION=$(shell $(PYTHON) -c "import sys; print(sys.version[:3])")

#INCDIR=$(shell $(PYTHON) -c "from distutils import sysconfig; print(sysconfig.get_python_inc())")
INCDIR=Include/
PLATINCDIR=$(shell $(PYTHON) -c "from distutils import sysconfig; print(sysconfig.get_python_inc(plat_specific=True))")
LIBDIR1=$(shell $(PYTHON) -c "from distutils import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
LIBDIR2=%library_dir%
PYLIB=%library_name%

CC=$(shell $(PYTHON) -c "import distutils.sysconfig; print(distutils.sysconfig.get_config_var('CC'))")
LINKCC=$(shell $(PYTHON) -c "import distutils.sysconfig; print(distutils.sysconfig.get_config_var('LINKCC'))")
LIBS=$(shell $(PYTHON) -c "import distutils.sysconfig; print(distutils.sysconfig.get_config_var('LIBS'))")
SYSLIBS= $(shell $(PYTHON) -c "import distutils.sysconfig; print(distutils.sysconfig.get_config_var('SYSLIBS'))")

INCLUDE=

%name%: %name%.o %library_dir%/lib%library_name%.a
	$(LINKCC) -o $@ $^ -L$() -L$(LIBDIR1) -L$(LIBDIR2) -l$(PYLIB) $(LIBS) $(SYSLIBS) $(INCLUDE)

%name%.o: %name%.c
	$(CC) -c $^ -I$(INCDIR) -I$(PLATINCDIR) $(INCLUDE)

%name%.c: %filename%
	@$(CYTHON) -%major% --embed %filename%

all: %name%

clean:
	rm -f %name% %name%.c %name%.o
'''

def freeze(filename, library, make_args=None):
    if make_args is None: make_args = []
    
    name = '.'.join(filename.split('.')[:-1])
    library_dir, library_name = os.path.split(os.path.abspath(library))
    library_name = '.'.join((library.split('/')[-1][3:]).split('.')[:-1])

    template = make_template
    # generate makefile
    for a, b in (
                 ('%name%', name),
                 ('%filename%', filename),
                 ('%library_dir%', library_dir),
                 ('%library_name%', library_name),
                 ('%major%', str(major_version)),
                 ):
        template = template.replace(a, b)

    with open(filename + '.make', 'wb') as make_file:
        make_file.write(bytes(template, 'utf8'))

    # call make
    call(['make', '-f', '%s.make' % filename] + make_args)
    
    # delete makefile
    os.remove(filename + '.make')


if __name__ == '__main__':
    import sys
    
    try: script_file = sys.argv[1]
    except: raise Exception('No script specified')

    try: lib_path = sys.argv[2]
    except: raise Exception('Path to Python runtime not specified')

    try: make_args = sys.argv[3:]
    except: make_args = []

    freeze(script_file, lib_path, make_args=make_args)