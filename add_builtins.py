#!/usr/bin/env python
'''Add a set of modules to the list of static Python builtins.

This will modify the Modules/Setup file, which is created by the Static.make 
Makefile. When running `make -f Static.make`, this script will be run 
automatically using any arguments passed to that Makefile. If you want to add 
modules manually, you can run `make -f Static.make setup` which will build 
Modules/Setup and allow you to edit it or run this script one or more times. 
When finished, run `make -f Static.make` to build the static interpreter.

Usage: python add_builtins.py [-s /path/to/script] [module_name] ...
'''
from modulefinder import ModuleFinder
import sys
import os
import os.path as op
import re
import imp
import shutil
import types
import importlib
from Cython.Build import cythonize


# module definition lines in Modules/Setup look like this
module_def = re.compile('^[A-Za-z_\.]+ .+\.c')
# put extra builtins in here
extra_module_dir = op.join('Modules', 'extras')
if not op.exists(extra_module_dir):
    os.makedirs(extra_module_dir)
# file endings that can be cythonized
cythonizeable_exts = ('.py', '.pyx')
# file endings that can be compiled
compileable_exts = ('.c', '.cpp', 'module.c', 'module.cpp')

def add_builtins(names, script=None, exclude=None, path=None, 
                 auto_add_deps=False, src_dirs=None, test=False):
    if path is None:
        paths = ['Lib'] + sys.path
    elif isinstance(path, basestring):
        paths = [path, 'Lib'] + sys.path
    else:
        paths = path
        
    if src_dirs is None: src_dirs = {}

    # if called with a script, find their dependencies and re-run
    to_add = set(names)
    if script:
        module_dir = op.split(script)[0]
        paths = [module_dir] + paths
        finder = ModuleFinder(path=paths)
        finder.run_script(script)
        to_add.update(finder.modules.keys())
        return add_builtins(list(to_add), script=None, exclude=exclude, 
                             path=paths, auto_add_deps=False, src_dirs=None)
        
    if auto_add_deps:
        for name in names:
            try:
                f, module_path, _ = imp.find_module(name, paths)
            except KeyboardInterrupt: raise
            except: continue
            
            if any([module_path.endswith(x) for x in ('.py', '.pyc')]):
                finder = ModuleFinder(path=paths)
                finder.run_script(module_path)
                to_add.update(finder.modules.keys())
                
        
    with open('Modules/Setup', 'r') as setup_file:
        lines = [str(x).rstrip('\n') for x in setup_file.readlines()]
    
    # don't add sys (it's already builtin) or anything explicitly excluded
    added = {'sys'}
    if exclude:
        added.update(exclude)
        
    
    # check each module to see if a commented line is present in Modules/Setup,
    # and uncomment
    for n, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        for name in to_add:
            if line.startswith('#%s ' % name):
                lines[n] = line.lstrip('#')
                to_add.remove(name)
                added.add(name)
                print('** Added %s' % name)
                break
                
        # keep track of uncommented module names in Modules/Setup
        if module_def.match(line):
            module_name = line.split()[0]
            pkg = False
            try: 
                f, module_path, _ = imp.find_module(module_name, paths)
                if f is None: pkg = True
            except: pkg = False
            
            if not pkg:
                added.add(module_name)
                print('** Found existing builtin %s' % module_name)
    
    # don't try to re-add existing builtins
    to_add = set.difference(to_add, added)
    
    for name in list(to_add):
        if name in added: continue
        
        new_lines = []
        
        try:
            f, module_path, _ = imp.find_module(name, paths)
        except ImportError:
            if '.' in name: f = None
            else: 
                raise Exception("** Couldn't find module %s" % name)
                continue
        
        # see if the target file already exists in Modules
        search_paths = [op.join(*(search_dir + (name+x,)))
                        for x in compileable_exts
                        for search_dir in (
                            (),
                            (name,),
                            ('extras', name),
                        )
                        if op.exists(op.join(*(('Modules',) + search_dir + (name+x,))))
                        ] if f else []
        
        if search_paths:
            module_file = search_paths[0]
            print('** Added %s' % module_file)
        else:
            # import the target module using this python installation,
            # and check the corresponding file
            
            if f is None:
                # add package
                pkg = name
                print("*** Scanning package %s..." % pkg)
                
                try:
                    p = importlib.import_module(pkg)
                except:
                    continue
                
                def get_submodules(x, yielded=None):
                    if not yielded: yielded = set()
                    yield x
                    yielded.add(x)
                    for member in dir(x):
                        member = getattr(x, member)
                        if isinstance(member, types.ModuleType) and not member in yielded:
                            for y in get_submodules(member, yielded):
                                yield y
                                yielded.add(y)
                
                submodules = get_submodules(p)
                
                for submodule in submodules:
                    name = submodule.__name__
                    
                    sys.stdout.write("** Adding module %s in package %s..." % (name, pkg))
                    sys.stdout.flush()
                    
                    try:
                        add = add_module(name, added, paths, src_dirs)
                        if add: new_lines += add
                    except Exception as e:
                        print('Failed:', e)
                        #raise
                    
                    print('done.')
                
            else:
                # add standalone module
                sys.stdout.write('** Adding %s...' % name)
                sys.stdout.flush()
                
                try:
                    add = add_module(name, added, paths, src_dirs, module_path=module_path)
                    if add: new_lines += add
                except Exception as e:
                    print(e)
                
                print('done.')
        
        if new_lines: lines += new_lines
    
    with open('Modules/Setup', 'w') as setup_file:
        setup_file.write('\n'.join(lines))
        
        
        
def add_module(name, added, paths, src_dirs, module_path=None):
    if name in added: 
        return
        
    added.add(name)
    pkg = '.' in name
    opts = ''
    
    if not module_path: 
        try: module_path = importlib.import_module(name).__file__
        except: return
    
    if op.basename(module_path).startswith('__init__'):
        pkg = True
        
    # if it's a .pyc file, hope the original python source is right next to it!
    if module_path.endswith('.pyc'):
        if op.exists(module_path[:-1]):
            module_path = module_path[:-1]
        else:
            # TODO: this could possibly be handled by unpyclib, etc.
            raise Exception('Lone .pyc file %s' % module_path)
        
    module_dir, module_file = op.split(module_path)
    
    # copy the file to the Modules/extras directory
    dest_dir = extra_module_dir
    if pkg:
        dest_dir = op.join(dest_dir, name.split('.')[0])
        if not op.exists(dest_dir): os.makedirs(dest_dir)
    
    
    # if it's a shared library, try to find the original C or C++ source file to 
    # compile into a static library; otherwise, there's nothing we can do here
    if module_file.endswith('.so'):
        done = False
        module_dirs = []
        for k, v in src_dirs.items():
            # if user specified a src directory for this package,
            # include it in the module search path
            if name.startswith(k):
                module = name[len(k):].lstrip('.')
                if '.' in module:
                    v = op.join(v, *module.split('.'))
                module_dirs += [v]
        module_dirs += [module_dir]
        for search_dir in module_dirs + paths:
            for compiled_module in ('.'.join(module_file.split('.')[:-1]) + ext
                                     for ext in compileable_exts):
                if op.exists(op.join(search_dir, compiled_module)):
                    dest_file = compiled_module
                    if pkg:
                        dest_file = '__'.join(name.split('.')) + '.' + dest_file.split('.')[-1]
                    
                    dest_path = op.join(dest_dir, dest_file)
                    
                    if not op.exists(dest_path):
                        shutil.copy(op.join(search_dir, compiled_module), dest_path)
                    
                    modile_dir = search_dir
                    module_file = dest_file
                    opts += ' -I%s' % op.abspath(search_dir)
                    done = True; break
            
            if done: break
        
        if not any([module_file.endswith(ext) for ext in compileable_exts]):
            raise Exception("Couldn't find C source file for %s" % module_file)
            #return
            
        module_path = op.join(module_dir, module_file)
        
    else:
        # copy the file to the Modules/extras directory
        dest_file = module_file
        if pkg:
            dest_file = '__'.join(name.split('.')) + '.' + dest_file.split('.')[-1]
            
        dest_path = op.join(dest_dir, dest_file)
        opts = ''
        
        if not op.exists(dest_path):
            shutil.copy(module_path, dest_path)
            
            
    # if the file ends in .py or .pyx, try to compile with Cython
    if any([module_file.endswith(x) for x in cythonizeable_exts]):
        dest_file = '.'.join(dest_file.split('.')[:-1]) + '.c'
        
        if op.exists(op.join(dest_dir, dest_file)):
            module_file = dest_file
        else:
            try:
                cythonize(dest_path)
                module_file = dest_file
                dest_path = op.join(dest_dir, dest_file)
                if pkg:
                    # correct module name in Cython-generated C file
                    wrong_name = '.'.join(dest_file.split('.')[:-1])
                    
                    with open(dest_path, 'r') as input_file:
                        with open(dest_path + '2', 'w') as output_file:
                            for line in input_file:
                                line = line.replace('"%s"' % wrong_name, '"%s"' % name)
                                output_file.write(line)
                                
                    os.remove(dest_path)
                    shutil.move(dest_path + '2', dest_path)
                    
            except KeyboardInterrupt: raise
            except:
                os.remove(op.join(dest_dir, dest_file))
                raise Exception('Cython failed to compile %s' % dest_path)
            
    if any([module_file.endswith(ext) for ext in compileable_exts]):
        # if there's a directory called Modules/{module} or 
        # Modules/extras/{module}, include that directory when compiling
        for inc_dir in (op.join('Modules', name), op.join(dest_dir, name)):
            if op.exists(inc_dir) and op.isdir(inc_dir):
                opts += ' -I%s' % op.abspath(inc_dir)
        
        if pkg:
            module_file = op.join('extras',
                                  name.split('.')[0],
                                  '.'.join(module_file.split('.')[:-1]).replace(
                                  '.', '__') + '.' + module_file.split('.')[-1]
                                  )
        else:
            module_file = op.join('extras', module_file)
        
        # add a line to Modules/Setup
        return ['%s %s%s' % (name.replace('.', '__'), module_file, opts)]
    else:
        raise Exception('Unknown file: %s' % module_file)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument('module', nargs='*', help='names of modules to be added as builtins')
    parser.add_argument('-s', '--script', nargs='?', default=None, 
                        help='add all dependencies of this script as builtins')
    parser.add_argument('-e', '--exclude', nargs='?', default=None, 
                        help='comma-separated list of modules to be excluded')
    parser.add_argument('-p', '--path', nargs='?', default=None, 
                        help='add this path to the module search path')
    parser.add_argument('-d', '--deps', action='store_true',
                        help='when adding a module, automatically add all of its dependencies')
    parser.add_argument('--src', nargs='?', default=None,
                        help='list of source package locations for shared libraries, e.g. `pkg1:/path/to/src,pkg2:/path/to/src`')
    parser.add_argument('-t', '--test', action='store_true',
                        help="don't actually add the modules right now, just output their names")
                        
    args = parser.parse_args()
    
    src_dirs = {pkg.split(':')[0]:pkg.split(':')[1]
                for pkg in args.src.split(',')
                } if args.src else None
    
    add_builtins(args.module, 
                 script=args.script, 
                 exclude=args.exclude.split(',') if args.exclude else None, 
                 path=args.path,
                 auto_add_deps=args.deps,
                 src_dirs=src_dirs,
                 test=args.test
                 )
