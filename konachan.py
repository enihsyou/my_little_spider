# -*- coding: utf-8 -*-
"""
File name: konachan
Reference:
Introduction:
Date: 2016-06-04
Last modified: 2016-06-04
Author: enihsyou
"""
import json
import re

from bs4 import BeautifulSoup
import requests
from multiprocessing import Pool
from collections import OrderedDict
import bs4

session = requests.Session()
base_url = "http://konachan.com"
session.headers.update({"Connection": "keep-alive",
                        "Pragma": "no-cache",
                        "Cache-Control": "no-cache",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Upgrade-Insecure-Requests": "1",
                        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
                        "Accept-Encoding": "gzip, deflate, sdch",
                        "Accept-Language": "zh-CN,zh;q=0.8,ja;q=0.6,en;q=0.4,zh-TW;q=0.2"})
session.proxies.update({"http": "http://localhost:8087"})

find_title_tag = re.compile(r"Tags: (.+) User")
find_page_number = re.compile(r"page=(\d+)")
total_pic_count = 0
json_body = []
file = open("konachan.json", "a")


def make_soup(data):
    bsObj = BeautifulSoup(data.text, "lxml")
    return bsObj


def get_data(page):
    r = session.get("http://konachan.com/post", params={"page": page})
    return make_soup(r)


# def post_data(page):
#     r = session.post("http://konachan.com/post", {"page": page})
#     return make_soup(r)


def dump_info(bsObj, pic_limit=10, page_limit=1):
    global total_pic_count
    pic_count = 0
    pic_body = bsObj.find("ul", id="post-list-posts")
    paginator = bsObj.find("div", id="paginator")
    current_page = paginator.div.find("em", class_="current").text
    print("当前页面: {}".format(current_page))

    next_page = find_page_number.search(
            paginator.find("a", class_="next_page")["href"]).group(1)
    pics = pic_body.find_all("li", class_="pending")

    for pic in pics:
        if pic is None: break
        if pic_count >= pic_limit: break
        total_pic_count += 1
        pic_count += 1
        information = OrderedDict()

        thumb = pic.find("a", class_="thumb")  # type: bs4.Tag 图片的缩略图链接
        pic_page = thumb["href"]  # 图片的详细页面链接
        thumb_img = thumb.img  # type: bs4.Tag 图片的缩略图
        thumb_img_src = thumb_img["src"]  # 图片的缩略图的URL
        thumb_img_title = thumb_img["title"]  # 图片的tag标题
        tag = find_title_tag.search(thumb_img_title).group(1)  # 取出tag

        direct_link = pic.find("a", class_="directlink")["href"]  # 默认大图的链接
        direct_link_resolution = pic.find("span",
                                          class_="directlink-res").text

        information["id"] = total_pic_count
        information["详细页面"] = base_url + pic_page
        information["缩略图URL"] = thumb_img_src
        information["Tags"] = tag
        information["大图URL"] = direct_link
        information["分辨率"] = direct_link_resolution

        print(information)
        json_body.append(information)

    if pic_count >= pic_limit or next_page == page_limit + 1:
        print("已经获取{}页数据 {}张图片，达到限制，跳出".format(current_page, total_pic_count))
        json.dump(json_body, file, indent=True, ensure_ascii=False)
        return
    else:
        print("\n下一页面: {}\n".format(next_page))
        dump_info(get_data(next_page))


dump_info(get_data(base_url + "/post"), page_limit=2)
file.close()
print()
