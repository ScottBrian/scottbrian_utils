#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

# setup(scripts=['sbt_pre_post_sphinx.py'])
setup(
    name='adjust_sphinx',
    version='1.0.0',
    packages=['adjust_sphinx'],
    entry_points={
    'console_scripts': [
        'sbt_pre_post_sphinx=adjust_sphinx.sbt_pre_post_sphinx:main',
    ],
})
