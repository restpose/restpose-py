try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

setup(name="Restpose",
      version='0.7.7',
      packages=find_packages(),
      include_package_data=True,
      author='Richard Boulton',
      author_email='richard@tartarus.org',
      description='Client for the Restpose Server',
      long_description=__doc__,
      zip_safe=False,
      platforms='any',
      license='MIT',
      url='https://github.com/restpose/restpose-py',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Operating System :: Unix',
      ],
      install_requires=[
        'restkit>=3.2.3',
        'six',
      ],
      setup_requires=[
      ],
      tests_require=[
        'coverage',
      ],
)
