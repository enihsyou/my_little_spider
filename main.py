# -*- coding: utf-8 -*-
"""
File name: main
Reference:
Introduction:
Date: 2016-05-27
Last modified: 2016-06-22
Author: enihsyou
"""
with open("konachan.json", "rb+") as file:
    print(file.seek(-2, 2))
    file.write("0".encode())
