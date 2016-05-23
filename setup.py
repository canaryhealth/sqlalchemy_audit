#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
  README = f.read()

requires = [
  'sqlalchemy >= 0.8.2',
  ]

test_requires = [
  'nose >= 1.3.0',
  ]

classifiers = [
  'Development Status :: 4 - Beta',
  'Environment :: Web Environment',
  'Intended Audience :: Developers',
  'License :: OSI Approved :: MIT License',
  'Natural Language :: English',
  'Operating System :: OS Independent',
  'Programming Language :: Python',
  'Topic :: Database',
]

setup(
  name='sqlalchemy_audit',
  version='0.1.0',
  description="sqlalchemy-audit provides an easy way to set up revision tracking for your data.",
  long_description=README,
  classifiers=classifiers,
  platforms=['any'],
  url='https://github.com/canaryhealth/sqlalchemy_audit',
  license='MIT',
  packages=find_packages(),
  include_package_data=True,
  zip_safe=True,
  test_suite='sqlalchemy_audit/test',
  install_requires=requires,
  tests_require=test_requires,
)
