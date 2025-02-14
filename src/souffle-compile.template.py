
# --- JSON_DATA_TEXT variable is inserted before this line ---

## Example of JSON_DATA_TEXT
if not JSON_DATA_TEXT:
    JSON_DATA_TEXT = """{
      "compiler": "/usr/bin/c++",
      "compiler_id": "GNU",
      "compiler_version": "8.3.0",
      "msvc_version": "",
      "includes": "-I/usr/include",
      "std_flag": "-std=c++17",
      "cxx_flags": " -fopenmp",
      "cxx_link_flags": "",
      "release_cxx_flags": "-O3 ",
      "debug_cxx_flags": "-g",
      "definitions": "-DRAM_DOMAIN_SIZE=64 -DUSE_NCURSES -DUSE_LIBZ -DUSE_SQLITE",
      "compile_options": "",
      "link_options": "-pthread -ldl -lstdc++fs /usr/lib/x86_64-linux-gnu/libsqlite3.so /usr/lib/x86_64-linux-gnu/libz.so /usr/lib/x86_64-linux-gnu/libncurses.so",
      "rpaths": "/usr/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu",
      "outname_fmt": "-o {}",
      "libdir_fmt": "-L{}",
      "libname_fmt": "-l{}",
      "rpath_fmt": "-Wl,-rpath,{}",
      "path_delimiter": ":",
      "exe_extension": "",
      "source_include_dir": "",
      "jni_includes": ""
    }"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

# run command and return status object
def launch_command(cmd, descr, verbose=False):
    if verbose:
        sys.stdout.write(cmd + "\n")
    status = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if status.returncode != 0:
        sys.stdout.write(status.stdout)
        sys.stderr.write(status.stderr)
        raise RuntimeError("Error: {}. Command: {}".format(descr, cmd))
    return status

# run command and return the standard output as a string
def capture_command_output(cmd, descr, verbose=False):
    status = launch_command(cmd, descr, verbose)
    return status.stdout


conf = json.loads(JSON_DATA_TEXT)
OUTNAME_FMT = conf['outname_fmt']
LIBDIR_FMT = conf['libdir_fmt']
LIBNAME_FMT = conf['libname_fmt']
RPATH_FMT = conf['rpath_fmt']
PATH_DELIMITER = conf['path_delimiter']
RPATHS = conf['rpaths'].split(PATH_DELIMITER)
exeext = conf['exe_extension']
SOURCE_INCLUDE_DIR = conf['source_include_dir']
JNI_INCLUDES = conf['jni_includes'].split(PATH_DELIMITER)

workdir = os.getcwd()
scriptdir = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser(description="Compile a C++ source file generated by Souffle")
parser.add_argument('-l', action='append', default=[], metavar='LIBNAME', dest='lib_names', type=str, help="Basename of a functors library. eg: `-l functors` => libfunctors.dll")
parser.add_argument('-L', action='append', default=[], metavar='LIBDIR', dest='lib_dirs', type=lambda p: pathlib.Path(p).absolute(), help="Search directory for functors libraries")
parser.add_argument('-g', action='store_true', dest='debug', help="Debug build type")
parser.add_argument('-s', metavar='LANG', dest='swiglang', choices=["java", "python"], help="use SWIG interface to generate into LANG language")
parser.add_argument('-v', action='store_true', dest='verbose', help="Verbose output")
parser.add_argument('source', metavar='SOURCE', type=lambda p: pathlib.Path(p).absolute(), help="C++ source file")

args = parser.parse_args()

stemname = args.source.stem
dirname = args.source.parent

if not os.path.isfile(args.source):
    raise RuntimeError("Cannot open source file: '{}'".format(args.source))

# Check if the input file has a valid extension
extname = args.source.suffix
if extname != ".cpp":
    raise RuntimeError("Source file is not a .cpp file: '{}'".format(args.source))

# Search for Souffle includes directory
souffle_include_dir = None
if (scriptdir / "include" / "souffle").exists():
    souffle_include_dir = scriptdir / "include" / "souffle"
elif (scriptdir / ".." / "include" / "souffle").exists():
    souffle_include_dir = scriptdir / ".." / "include" / "souffle"
elif SOURCE_INCLUDE_DIR and (pathlib.Path(SOURCE_INCLUDE_DIR) / "souffle").exists():
    souffle_include_dir = (pathlib.Path(SOURCE_INCLUDE_DIR) / "souffle")

if args.swiglang:
    if not (souffle_include_dir and (souffle_include_dir / "swig").exists()):
        raise RuntimeError("Cannot find 'souffle/swig' include directory")

    swig_include_dir = (souffle_include_dir / "swig")
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(swig_include_dir / "SwigInterface.h", tmpdir)
        shutil.copy(swig_include_dir / "SwigInterface.i", tmpdir)

        os.chdir(tmpdir)
        launch_command("swig -c++ -\"{}\" SwigInterface.i".format(args.swiglang), "SWIG generation", verbose=args.verbose)

        if args.swiglang == "python":
            swig_flags = capture_command_output("python3-config --cflags", "Python config", verbose=args.verbose)
            swig_ldflags = capture_command_output("python3-config --ldflags", "Python config", verbose=args.verbose)
            swig_outname = "_SwigInterface.so"
        elif args.swiglang == "java":
            swig_flags = " ".join(["-I{}".format(dir) for dir in JNI_INCLUDES])
            swig_ldflags = ""
            swig_outname = "libSwigInterface.so"

        # compile swig interface and program
        cmd = []
        cmd.append('"{}"'.format(conf['compiler']))
        cmd.append("-fPIC")
        cmd.append("-c")
        cmd.append("-D__EMBEDDED_SOUFFLE__")
        cmd.append("SwigInterface_wrap.cxx")
        cmd.append(str(args.source))
        cmd.append(conf['definitions'])
        cmd.append(conf['compile_options'])
        cmd.append(conf['includes'])
        cmd.append(conf['std_flag'])
        cmd.append(conf['cxx_flags'])
        if args.debug:
            cmd.append(conf['debug_cxx_flags'])
        else:
            cmd.append(conf['release_cxx_flags'])
        cmd.append(swig_flags)
        cmd = " ".join(cmd)
        launch_command(cmd, "Compilation of SWIG C++", verbose=args.verbose)

        # link swig interface and program
        cmd = []
        cmd.append('"{}"'.format(conf['compiler']))
        cmd.append("-shared")
        cmd.append("SwigInterface_wrap.o")
        cmd.append("{}{}".format(stemname, ".o"))
        cmd.append("-o")
        cmd.append(swig_outname)
        cmd.append(conf['definitions'])
        cmd.append(conf['compile_options'])
        cmd.append(conf['includes'])
        cmd.append(conf['std_flag'])
        cmd.append(conf['cxx_flags'])
        if args.debug:
            cmd.append(conf['debug_cxx_flags'])
        else:
            cmd.append(conf['release_cxx_flags'])
        cmd.append(conf['link_options'])
        cmd.extend(list(map(lambda rpath: RPATH_FMT.format(rpath), RPATHS)))
        cmd.extend(list(map(lambda libdir: LIBDIR_FMT.format(libdir), args.lib_dirs)))
        cmd.extend(list(map(lambda libname: LIBNAME_FMT.format(libname), args.lib_names)))
        cmd.append(swig_ldflags)
        cmd = " ".join(cmd)
        launch_command(cmd, "Link of SWIG C++", verbose=args.verbose)

        if args.swiglang == "python":
            shutil.copy("_SwigInterface.so", workdir)
            shutil.copy("SwigInterface.py", workdir)
        elif args.swiglang == "java":
            shutil.copy("libSwigInterface.so", workdir)
            for javasrc in pathlib.Path(tmpdir).glob("*.java"):
                shutil.copy(javasrc, workdir)

        # move generated files to same directory as cpp file
        os.sys.exit(0)
else:
    exepath = pathlib.Path(dirname.joinpath("{}{}".format(stemname, exeext)))

    cmd = []
    cmd.append('"{}"'.format(conf['compiler']))
    cmd.append(conf['definitions'])
    cmd.append(conf['compile_options'])
    cmd.append(conf['includes'])
    cmd.append(conf['std_flag'])
    cmd.append(conf['cxx_flags'])

    if args.debug:
        cmd.append(conf['debug_cxx_flags'])
    else:
        cmd.append(conf['release_cxx_flags'])

    cmd.append(OUTNAME_FMT.format(exepath))
    cmd.append(str(args.source))

    cmd.append(conf['link_options'])
    cmd.extend(list(map(lambda rpath: RPATH_FMT.format(rpath), RPATHS)))
    cmd.extend(list(map(lambda libdir: LIBDIR_FMT.format(libdir), args.lib_dirs)))
    cmd.extend(list(map(lambda libname: LIBNAME_FMT.format(libname), args.lib_names)))

    cmd = " ".join(cmd)

    if args.verbose:
        sys.stderr.write(cmd + "\n")

    if exepath.exists():
        exepath.unlink()

    status = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if status.returncode != 0:
        sys.stdout.write(status.stdout)
        sys.stderr.write(status.stderr)

    os.sys.exit(status.returncode)
