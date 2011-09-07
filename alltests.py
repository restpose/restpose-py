#!/usr/bin/env python
# Run all tests

import os
import subprocess
import sys

topdir = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
os.chdir(topdir)
retcode = subprocess.call("nosetests")
if not retcode:
    os.chdir(os.path.join(topdir, "docs"))
    subprocess.call("make", "doctest")
