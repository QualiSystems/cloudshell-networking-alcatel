#!/usr/bin/python
# -*- coding: utf-8 -*-

import nose.config
import sys
from nose.plugins.manager import DefaultPluginManager


c = nose.config.Config()
c.plugins = DefaultPluginManager()
c.srcDirs = ['cloudshell']
if not nose.run(config=c):
    sys.exit(1)
