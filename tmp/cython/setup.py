from distutils.core import setup
# from distutils.extension import Extension
from Cython.Distutils import build_ext
from Cython.Build import cythonize

# ext_modules = [Extension("hello", ["../../models/hello.pyx"])]

setup(
    # name = 'Hello world app',
    cmdclass = {'build_ext': build_ext},
    ext_modules = cythonize(["hello.pyx"])
)