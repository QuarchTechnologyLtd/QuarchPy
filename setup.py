from setuptools import setup
import re


VERSIONFILE="quarchpy/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(name='quarchpy',
      version=verstr,
      description='This packpage offers Python support for Quarch Technology modules.',
      long_description_content_type='text/x-rst',
      long_description= open('quarchpy/docs/CHANGES.rst').read(),
      home_page = 'https://www.quarch.com',
      author='Quarch Technology ltd',
      author_email='support@quarch.com',
      license='Quarch Technology ltd',
      keywords='quarch quarchpy torridon',
      packages=['quarchpy', 
      'quarchpy.config_files', 
      'quarchpy.config_files.Switch_Modules', 
      'quarchpy.config_files.Power_Margining', 
      'quarchpy.config_files.Drive_Modules', 
      'quarchpy.config_files.Card_Modules', 
      'quarchpy.config_files.Cable_Modules',
      'quarchpy.connection_specific',
      'quarchpy.connection_specific.usb_libs', 
      'quarchpy.connection_specific.usb_libs.MS32', 
      'quarchpy.connection_specific.usb_libs.MS64', 
      'quarchpy.connection_specific.serial', 
      'quarchpy.debug', 
      'quarchpy.device', 
      'quarchpy.disk_test', 
      'quarchpy.docs',
      'quarchpy.fio', 
      'quarchpy.iometer', 
      'quarchpy.qis', 
      'quarchpy.qps',
      'quarchpy.user_interface',
      'quarchpy.utilities'],
      package_data={'': ['QuarchPy Function Listing.xlsx']},
      classifiers=
      [
      'Intended Audience :: Information Technology',
      'Intended Audience :: Developers',
      'Natural Language :: English',
      'Operating System :: MacOS',
      'Operating System :: Microsoft :: Windows',
      'Operating System :: POSIX',
      'Programming Language :: Python',
      'Topic :: Scientific/Engineering :: Information Analysis',
      'Topic :: System',
      'Topic :: System :: Power (UPS)'
      ],

      install_requires=[
            'zeroconf>=0.23.0',
            'numpy',
            'pandas',
            'requests',
            'packaging',
            'quarchpy-binaries',
            'typing-extensions'],
      python_requires='>=3.7',
      include_package_data=True,
      zip_safe=False)