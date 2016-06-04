# -*- coding: utf-8 -*-
"""
File name: bilibili_new_bangumi_information
Reference:
Introduction:
Date: 2016-06-02
Last modified: 2016-06-02
Author: enihsyou
"""
import json

from bs4 import BeautifulSoup
import requests
from multiprocessing import Pool
from collections import OrderedDict
import bs4
import os

url = "http://www.bilibili.com/list/default-33-{}-2016-05-27~2016-06-03.html"

js = []

if os.path.exists("bilibili_new_bangumi_information"):
    print("文件存在")
    file = open("bilibili_new_bangumi_information", "wa", encoding='utf-8')
else:
    file = open("bilibili_new_bangumi_information", "w", encoding='utf-8')


def pull_info(soup, js):
    info = OrderedDict()
    print(page)
    for link in soup.find_all("div", class_="l-r"):  # type: bs4.Tag
        info["名称"] = link.find("a", class_="title").text
        info["点击"] = link.find("span", "gk").span["number"]
        info["弹幕"] = link.find("span", "dm").span["number"]
        info["收藏"] = link.find("span", "sc").span["number"]
        json.dump(info, file, ensure_ascii=False, indent=True)
        # js.append(info)
        print(info)


def turn_to_next_page(page):
    next_page = url.format(page)
    resp = requests.get(next_page)
    soup = BeautifulSoup(resp.text, "lxml")
    return soup


for page in range(1, 973):
    pull_info(turn_to_next_page(page), js)

file.close()
print()
