# -*- coding: utf-8 -*-
"""
File name: main
Reference:
Introduction:
Date: 2016-05-27
Last modified: 2016-05-27
Author: enihsyou
"""
from requests import Request, Session

s = Session()

req = Request('POST', "http://url")
prepped = req.prepare()

# do something with prepped.body
prepped.body = 'No, I want exactly this as the body.'
print()
from termcolor import colored

print(colored("abc", "green"))
