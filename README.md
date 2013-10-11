Static-Python
=============

This is a fork of the official Python hg repository with additional tools to 
enable building Python for static linking.

You may be wondering, "why would you want to do that? After all, [static linking 
is evil](http://www.akkadia.org/drepper/no_static_linking.html)." Here are a few 
possible reasons:

  * To run Python programs on other machines without requiring that they install
    Python.

  * To run Python programs on other machines without requiring that they have
    the same versions of the same libraries installed that you do.

  * Because the major binary distribution tools for Python (cx_Freeze, bbfreeze, 
    py2exe, and py2app) ship in a way that the Python source code can be 
    trivially derived (unzip the archive of .pyc files and decompile them.) For
    proprietary or security-conscious applications, this is unacceptable.


Usage
=====

Building Static Python
----------------------

To build a static Python executable and library, check out the appropriate branch
(either 2.7, 3.3, or master) and run the following command:

    make -f Static.make

This will create an executable called `python` in the working directory, and a 
static library, `libpythonX.X.a`, in the install/lib directory. You can confirm 
that this executable is not dependent on any shared libraries using `ldd python` 
which should report that python is not a dynamic executable. However, by default 
this executable's functionality will be very limited - it won't even be able to 
access most modules from the Python standard library.

In order to make this Python interpreter truly standalone (not dependent on 
installed Python modules), you can designate Python modules to be compiled as 
builtins, which will be statically linked into the Python interpreter. 
Static.make generates a file in Modules/Setup which needs to be edited to 
specify these new builtin modules.

You can automatically add builtins when building Static Python by passing 
BUILTINS and/or SCRIPT variables to Static.make, e.g.:

    make -f Static.make BUILTINS="math zipfile zlib" SCRIPT="/path/to/script.py"

Each module listed in the BUILTINS variable will be added, if possible. SCRIPT 
can be used to specify the path to a Python script. This script will be scanned 
for dependencies using modulefinder, and all dependencies will be added as 
builtins if possible (not the script itself - it should be compiled using 
static_freeze.py and linked to the resulting static library.) Finally, if the 
DFLAG variable is set to "-d", all dependencies of all modules will be 
automatically added as well (this will usually include many modules, and you may 
not really need them all.)

(If you previously built Static Python, you should `make -f Static.make clean` 
first. Also, this step requires an existing Python installation, preferably of 
the same version you're building, so you may need to build and install Python 
the normal way first before building it statically..)

Adding builtins can also be done manually by editing Modules/Setup. Add lines to
the end of the file in the format:

    module_name module.c ...

These .c files can be generated from .py files using Cython:

    cython module.py

(This is done automatically using add_builtins.py, the script called by 
Static.make when BUILTINS or SCRIPT are supplied.)

Packages are not currently supported. I'm working on an automatic solution for 
compiling and including packages. Stay tuned.


Compile a standalone executable
-------------------------------

Once you've compiled a static Python library, you can turn a Python script into 
a standalone executable using the static_freeze.py script.

    Tools/static_freeze/static_freeze.py test.py libpython2.7.a

This will generate an executable called "test" in the working directory, which 
is not dependant on any shared libraries, Python modules, or the Python 
interpreter!


Acknowledgements
================

Major thanks to Gabriel Jacobo who pioneered this method: 
<http://mdqinc.com/blog/2011/08/statically-linking-python-with-cython-generated-modules-and-packages/>
