# -*- coding: utf-8 -*-
"""
File name: konachan
Reference:
Introduction: 下载konachan.com上面的图片的小爬虫
Date: 2016-06-04
Last modified: 2016-06-04
Author: enihsyou
"""
import json
import os
import re
from collections import OrderedDict

import bs4
import requests
from bs4 import BeautifulSoup

session = requests.Session()

# 字段定义
base_url = "http://konachan.com"
data_file_name = "konachan.json"  # 需要保存的文件名
thumb_dir_name = "thumb"  # 临时文件夹的名字
large_img_dir_name = "images"  # 大图文件夹的名字

# 发送的HEADER
session.headers.update({
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, sdch",
    "Accept-Language": "zh-CN,zh;q=0.8,ja;q=0.6,en;q=0.4,zh-TW;q=0.2"})
# 代理设置
session.proxies.update({"http": "http://localhost:8087"})  # 本地代理，使用GAE:8087

re_title_tag = re.compile(r"Tags: (.+) User")  # 抓取出tag内容
re_page_number = re.compile(r"page=(\d+)")  # 抓取出page，当前页数
re_pic_id = re.compile(r"/(\d+?)/")  # 抓取出图片id
re_pics_class = re.compile(r"creator-id-\d*")  # 图片的所在位置的class
re_base_url = re.compile("^" + base_url)  # 用于去除http://hostname.xxx开头
re_host_name = re.compile(r"(?<=http://)?([^/]+?)\..+/?")  # 捕获次级域名
re_valid_path = re.compile(r"[:<>\"/\\\|\?\*]")
total_pic_count = 0  # 总共获取了多少图片的信息
json_body = []  # 需要一起写入到文件的信息


def _make_soup(response):
    """只是生成一个BeautifulSoup对象

    Args:
        response (requests.models.Response): 连接的响应对象

    Returns:
        bs4.BeautifulSoup: Soup
    """
    bsObj = BeautifulSoup(response.text, "lxml")
    return bsObj


def get_data(page):
    """连接第`page`页

    直接使用page参数get，而不是从网页中获取的信息
    Args:
        page (str(int)): 页数

    Returns:
        bs4.BeautifulSoup: 连接的Soup

    Raises:
        Exception (ERROR): 连接出问题
    """
    try:
        r = session.get(base_url + "/post", params={"page": page})
    except Exception as ERROR:
        print(ERROR)
        raise ERROR
    return _make_soup(r)


def dump_info(soup, pics_limit=-1, page_limit=-1):
    """获取信息，添加到一个列表中，等待序列化成json

    Args:
        soup (bs4.BeautifulSoup): 连接汤
        pics_limit (int): 限制获取图片的数量 (default: -1)
        page_limit (int): 限制获取页面的数量 (default: -1)

    Returns:
        None: 跳出
    """
    global total_pic_count
    pic_count = 0
    pic_body = soup.find("ul", id="post-list-posts")  # 图片存在的主体
    paginator = soup.find("div", id="paginator")  # 页面导航栏
    current_page = paginator.div.find("em", class_="current").text  # 当前页面，数字
    print("当前页面: {}".format(current_page))

    next_page_href = paginator.find("a", class_="next_page")["href"]  # 下一页的链接

    if next_page_href is None:  # 抵达最后一页
        next_page = 0
    else:
        next_page = int(re_page_number.search(next_page_href).group(1))

    pics = pic_body.find_all("li", class_=re_pics_class)  # 所有图片列表

    for pic in pics:
        if pic is None: break
        if pic_count == pics_limit: break
        total_pic_count += 1
        pic_count += 1
        information = OrderedDict()

        thumb = pic.find("a", class_="thumb")  # type: bs4.Tag 图片的缩略图链接
        pic_page = cut_base_url(thumb["href"])  # 图片的详细页面链接
        thumb_img = thumb.img  # type: bs4.Tag 图片的缩略图tag
        thumb_img_src = cut_base_url(thumb_img["src"])  # 图片的缩略图的URL
        thumb_img_title = thumb_img["title"]  # 图片的tag标题
        tag = re_title_tag.search(thumb_img_title).group(1)  # 取出tag
        pic_id = re_pic_id.search(pic_page).group(1)  # 图片在站点上的id
        direct_link = cut_base_url(
                pic.find("a", class_="directlink")["href"])  # 默认大图的链接
        direct_link_resolution = pic.find(
                "span", class_="directlink-res").text  # 图片实际分辨率

        # 注册信息
        information["index"] = total_pic_count
        information["id"] = pic_id
        information["详细页面"] = base_url + pic_page
        information["缩略图URL"] = thumb_img_src
        information["Tags"] = tag
        information["大图URL"] = direct_link
        information["分辨率"] = direct_link_resolution
        print(information)
        json_body.append(information)
        if bool_download_thumb:
            download_img(
                    thumb_img_src, [pic_id, thumb_dir_name, tag], ".jpg",
                    thumb=True)  # 下载缩略图
        if bool_download_large_img:
            download_img(direct_link, [pic_id, tag], ".jpg")  # 下载jpg大图

    if pic_count == pics_limit or next_page == page_limit + 1:  # 达到跳出条件
        print("已经获取{}页数据 {}张图片，完成 跳出".format(current_page, total_pic_count))
        return
    else:  # 没什么事情就继续爬下一页
        print("\n下一页面: {}\n".format(next_page))
        dump_info(get_data(next_page), pics_limit=pics_limit,
                  page_limit=page_limit)


def cut_base_url(url):
    """剪短链接 去除base_link

    Args:
        url (str): 需要处理的url字符串

    Returns:
        (str): 去除了base_link的url
    """
    if url.startswith(base_url):
        return re_base_url.sub("", url)
    else:
        return url


def size_format(_bytes, suffix="B"):
    """将byte字节数转换成适合人类阅读的文本

    References:
        http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size

    Args:
        _bytes (int): 要转换的字节数
        suffix (str): 尾号标记，一般是`B`，例如MB GB (default: "B")

    Returns:
        (str): 转换后的字符串
    """
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(_bytes) < 1024.0:
            return "{:3.1f}{}{}".format(_bytes, unit, suffix)
        _bytes /= 1024.0
    return "{:.1f}{}{}".format(_bytes, "Yi", suffix)


def download_img(url, file_name, suffix=".jpg", thumb=False):
    """下载url下的图片

    Args:
        url (str): 要下载的链接
        file_name (list): 打算存的文件名列表，会用join处理 添加空格
        suffix (str): 保存文件的后缀名，大部分是jpg格式的 (default: ".jpg")
        thumb (bool): 是否是缩略图，是的话会放到一个叫thumb的目录下 (default: False)
    Raises:
        Exception (ERROR): 连接出问题
    """
    try:
        data = session.get(base_url + url).content
    except Exception as ERROR:
        print(ERROR)
        raise ERROR
    base_url_host_name = re_host_name.search(base_url).group(1)
    file_name = [re_valid_path.sub("_", a) for a in file_name]
    file_name = " ".join(map(str, [base_url_host_name] + file_name))[:210] + suffix  # 长于210字符的会被切断
    if thumb:
        file_path = os.path.join("./" + thumb_dir_name, file_name)
    else:
        file_path = os.path.join("./" + large_img_dir_name, file_name)

    if os.path.exists(file_path):  # 处理同名文件
        print("同名文件已存在，覆盖")
    with open(file_path, "wb") as _file:
        bytes_write = _file.write(data)
    file_size = size_format(bytes_write)
    print("下载成功(大小: {}): {}".format(file_size, file_name))


if __name__ == "__main__":
    pics_limit = input("设定图数\n>>>")
    page_limit = input("设定页数\n>>>")
    bool_download_thumb = input("是否同时下载缩略图[y/n]\n>>>")
    bool_download_large_img = input("是否同时下载jpg大图[y/n]\n>>>")

    # 转换字符串到数字
    if pics_limit:
        pics_limit = int(pics_limit)
    else:
        pics_limit = -1
    if page_limit:
        page_limit = int(page_limit)
    else:
        page_limit = -1

    # 处理要下载文件时的必要事件
    if bool_download_thumb.lower() in ["y", "yes", "shi", "do", ""]:
        bool_download_thumb = True
        if not os.path.exists(thumb_dir_name):
            os.mkdir(thumb_dir_name)
    if bool_download_large_img.lower() in ["y", "yes", "shi", "do", ""]:
        bool_download_large_img = True
        if not os.path.exists(large_img_dir_name):
            os.mkdir(large_img_dir_name)

    dump_info(get_data(base_url + "/post"), pics_limit=pics_limit,
              page_limit=page_limit)  # 启动爬虫

    # 判断要写入的文件是否存在
    write_mode = "a"
    if os.path.exists(data_file_name):
        bool_override = input("文件已存在，是否覆盖？[y/n]\n>>>")
        if bool_override.lower() in ["y", "yes", "shi", "do", ""]:
            write_mode = "w"

    # 保存信息到文件
    with open(data_file_name, write_mode) as file:
        json.dump(json_body, file, indent=True, ensure_ascii=False)  # 写入文件

    print("\n写入完成…")
    os.system("pause")
