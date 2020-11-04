#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 00:09:16 2020

@author: Scott Tuttle
"""

from setuptools import setup, find_packages

with open('README.rst', 'r') as readme:
    long_description = readme.read()


setup(
      name='scottbrian_utils',
      version='1.0.0',
      author='Scott Tuttle',
      description='Print header/trailer utilities',
      long_description=long_description,
      long_description_content_type='text/x-rst',
      url='https://github.com/ScottBrian/scottbrian_utils.git',
      classifiers=[
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Operating System :: POSIX :: Linux'
                  ],
      project_urls={
          'Source': 'https://github.com/ScottBrian/scottbrian_utils.git'},
      python_requires='>=3.6',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      install_requires=['typing-extensions', 'wrapt'],
      package_data={"scottbrian_utils": ["__init__.pyi", "py.typed"]},
      zip_safe=False
     )
