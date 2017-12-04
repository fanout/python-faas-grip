#!/usr/bin/env python

from setuptools import setup

setup(
name='faas-grip',
version='1.0.0',
description='FaaS GRIP library',
author='Justin Karneges',
author_email='justin@fanout.io',
url='https://github.com/fanout/python-faas-grip',
license='MIT',
py_modules=['faas_grip'],
install_requires=['pubcontrol>=2.4.1,<3', 'gripcontrol>=3.2.0,<4', 'six>=1.10,<2'],
classifiers=[
	'Topic :: Utilities',
	'License :: OSI Approved :: MIT License'
]
)
