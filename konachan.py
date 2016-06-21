# -*- coding: utf-8 -*-
"""
File name: konachan
Reference:
Introduction: 下载konachan.com上面的图片的小爬虫
Date: 2016-06-04
Last modified: 2016-06-07
Author: enihsyou
"""
import json
import os
import re
import sqlite3
from collections import OrderedDict
from time import perf_counter

import bs4
import requests
from bs4 import BeautifulSoup
from termcolor import colored

session = requests.Session()

# 字段定义
base_url = "http://konachan.com"
json_file_name = "konachan.json"  # 保存的json文件名
database_file_name = "konachan.sqlite3"  # 保存的sqlite3文件名
thumb_dir_name = "thumb"  # 临时文件夹的名字
large_img_dir_name = "images"  # 大图文件夹的名字

# 发送的HEADER
session.headers.update({
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, sdch"})
# 代理设置
session.proxies.update({"http": "http://localhost:8087"})  # 本地代理，使用GAE:8087

# 正则表达式搜索定义
RE_TITLE_TAG = re.compile(r"Tags: (.+) User")  # 抓取出tag内容
RE_PAGE_NUMBER = re.compile(r"page=(\d+)")  # 抓取出page，当前页数
RE_PIC_ID = re.compile(r"/(\d+?)/")  # 抓取出图片id
RE_PICS_CLASS = re.compile(r"creator-id-\d*")  # 图片的所在位置的class
RE_BASE_URL = re.compile("^" + base_url)  # 用于去除http://hostname.xxx开头
RE_HOST_NAME = re.compile(r"(?<=http://)?([^/]+?)\..+/?")  # 捕获次级域名
RE_VALID_PATH = re.compile(r"[:<>\"/\\\|\?\*]")

# 参数定义
total_pic_count = 0  # 总共获取了多少图片的信息
start_page = 1  # 起始页面
json_body = []  # 需要一起写入到文件的信息
pics_limit = -1  # 限制获取的图片数量
page_limit = -1  # 限制获取的页面数量
download_thumb = False  # 是否同时下载缩略图
download_large_img = False  # 是否同时下载大图
start_time = 0  # 处理开始的时间
cache_pages = 0  # 缓存中的页面数量
cache_limit = 50  # 写入文件需要达到的缓存数量
result = []  # 包含下一页的信息或者退出的信息

# 连接数据库
database = sqlite3.connect(":memory:")  # 储存在内存中
cursor = database.cursor()
cursor.executescript(
        r"""
        DROP TABLE IF EXISTS konachan;
        CREATE TABLE konachan(
            id INTEGER NOT NULL PRIMARY KEY UNIQUE,
            tags TEXT,
            information_link TEXT,
            sample_img_URL TEXT,
            thumb_img_URL TEXT,
            resolution TEXT,
            height INTEGER,
            width INTEGER);
        """)
database.commit()

with sqlite3.connect(database_file_name) as db:  # 初始化本地数据库文件
    db.execute("DROP TABLE IF EXISTS konachan")
    db.executescript("".join(database.iterdump()))


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
    global start_time
    if page == -1: return -1  # 退出
    try:
        start_time = perf_counter()  # 处理开始的时间
        response = session.get(base_url + "/post", params={"page": page})
        response.raise_for_status()
    except Exception as ERROR:
        print(colored(ERROR, "red"))
        raise ERROR

    return _make_soup(response)


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
    if soup == -1: return  # 退出
    pic_body = soup.find("ul", id="post-list-posts")  # 图片存在的主体
    paginator = soup.find("div", id="paginator")  # 页面导航栏
    current_page = int(
            paginator.div.find("em", class_="current").text)  # 当前页面，数字
    print(colored("当前页面: {}".format(current_page), "blue"))

    next_page_href = paginator.find("a", class_="next_page")  # 下一页的链接

    if next_page_href is not None:  # 未抵达最后一页
        next_page = int(RE_PAGE_NUMBER.search(next_page_href["href"]).group(1))
    else:
        next_page = -1

    pics = pic_body.find_all("li", class_=RE_PICS_CLASS)  # 所有图片列表

    for pic in pics:
        if pic is None: break
        if total_pic_count == pics_limit: break
        if current_page == page_limit: break

        total_pic_count += 1
        information = OrderedDict()

        # 提取信息
        thumb = pic.find("a", class_="thumb")  # type: bs4.Tag 图片的缩略图链接
        pic_page = cut_base_url(thumb["href"])  # 图片的详细页面链接
        thumb_img = thumb.img  # type: bs4.Tag 图片的缩略图tag
        thumb_img_src = cut_base_url(thumb_img["src"])  # 图片的缩略图的URL
        thumb_img_title = thumb_img["title"]  # 图片的tag标题
        tags = RE_TITLE_TAG.search(thumb_img_title).group(1)  # 取出tag
        pic_id = RE_PIC_ID.search(pic_page).group(1)  # 图片在站点上的id
        direct_img_link = cut_base_url(
                pic.find("a", class_="directlink")["href"])  # 默认大图的链接
        direct_link_resolution = pic.find(
                "span", class_="directlink-res").text  # 图片实际分辨率

        # 注册信息
        information["index"] = total_pic_count
        information["id"] = int(pic_id)
        information["tags"] = tags
        information["information_link"] = base_url + pic_page
        information["sample_img_URL"] = direct_img_link
        information["thumb_img_URL"] = thumb_img_src
        information["resolution"] = direct_link_resolution
        information["height"] = int(direct_link_resolution.split(" x ")[0])
        information["width"] = int(direct_link_resolution.split(" x ")[1])

        # 打印当前信息
        print(information["id"], information["information_link"])

        # json信息添加
        json_body.append(information)

        # 数据库信息添加
        update_database(information)

        # 下载
        if download_thumb:  # 下载缩略图
            download_img(thumb_img_src, [pic_id, thumb_dir_name, tags], ".jpg",
                         thumb=True)
        if download_large_img:  # 下载jpg大图
            download_img(direct_img_link, [pic_id, tags], ".jpg")

        # 跳出条件检测
        if total_pic_count == pics_limit:
            return current_page - start_page + 1, total_pic_count, perf_counter() - running_time, -1
    # 没什么事情就继续爬下一页
    if next_page_href is None or next_page >= page_limit:
        return current_page - start_page + 1, total_pic_count, perf_counter() - running_time, -1
    print(colored("\n下一页面: {}  {} s\n".format(
            next_page, perf_counter() - start_time), "blue"))
    return next_page,


def update_database(information_dict, cursor=cursor):
    """写入信息到内存数据库"""
    cursor.execute(
            r"""
            INSERT INTO konachan (
            id, tags, information_link, sample_img_URL, thumb_img_URL, resolution, height, width)
            VALUES ({},{},{},{},{},{},{},{})
            """.format(
                    information_dict["id"],
                    "'" + information_dict["tags"].replace("'", "''") + "'",
                    "'" + information_dict["information_link"].replace("'",
                                                                       "''") + "'",
                    "'" + information_dict["sample_img_URL"].replace("'",
                                                                     "''") + "'",
                    "'" + information_dict["thumb_img_URL"].replace("'",
                                                                    "''") + "'",
                    "'" + information_dict["resolution"].replace("'",
                                                                 "''") + "'",
                    information_dict["height"],
                    information_dict["width"]
            )
    )


def cut_base_url(url):
    """剪短链接 去除base_link

    Args:
        url (str): 需要处理的url字符串

    Returns:
        (str): 去除了base_link的url
    """
    if url.startswith(base_url):
        return RE_BASE_URL.sub("", url)
    else:
        return url


def format_size(_bytes, suffix="B"):
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
        start_time = perf_counter()
        data = session.get(base_url + url).content
    except Exception as ERROR:
        print(colored(ERROR, "red"))
        raise ERROR
    base_url_host_name = RE_HOST_NAME.search(base_url).group(1)
    file_name = [RE_VALID_PATH.sub("_", a) for a in file_name]
    file_name = " ".join(map(str, [base_url_host_name] + file_name))[
                :210] + suffix  # 长于210字符的会被切断
    if thumb:
        file_path = os.path.join("./" + thumb_dir_name, file_name)
    else:
        file_path = os.path.join("./" + large_img_dir_name, file_name)

    if os.path.exists(file_path):  # 处理同名文件
        print(colored("同名文件已存在，覆盖", "yellow"))
    with open(file_path, "wb") as _file:
        bytes_write = _file.write(data)
    file_size = format_size(bytes_write)
    print(colored(
            "下载成功(大小: {} {}s): {}".format(
                    file_size, perf_counter() - start_time, file_name),
            "green"))


def dump_json(json_body):
    """增量写入json文件"""
    start_time = perf_counter()
    with open(json_file_name, "a") as file:
        json.dump(json_body, file, indent=True)  # 写入文件
    print(colored(
            "写入 {} 完成… {}s".format(json_file_name, perf_counter() - start_time),
            "green"))


def dump_database(database):
    """增量写入数据库"""
    start_time = perf_counter()
    database.commit()

    database_iter = database.iterdump()

    with sqlite3.connect(database_file_name) as db:
        for line in database_iter:
            if line.startswith("INSERT"):
                db.execute(line)
    database.execute("DELETE FROM konachan")
    print(colored("写入 {} 完成… {}s".format(database_file_name,
                                         perf_counter() - start_time), "green"))


if __name__ == "__main__":
    _pics_limit = input("设定图数\n>>>")
    _page_limit = input("设定页数\n>>>")

    # 转换字符串到数字
    if _pics_limit: pics_limit = int(_pics_limit)
    if _page_limit: page_limit = int(_page_limit)

    # 处理要下载文件时的必要事件
    if download_thumb:
        if not os.path.exists(thumb_dir_name):
            os.mkdir(thumb_dir_name)
    if download_large_img:
        if not os.path.exists(large_img_dir_name):
            os.mkdir(large_img_dir_name)

    # 判断要写入的文件是否存在
    if os.path.exists(json_file_name):
        bool_override = input(
                colored("文件 {} 已存在，是否覆盖？ [y/n (y)]\n>>>".format(json_file_name),
                        "yellow"))
        if bool_override.lower() in ["y", "yes", "shi", "do", ""]:
            os.remove(json_file_name)

    # 启动爬虫
    running_time = perf_counter()  # 启动时间
    times = 1  # 统计倍率

    while start_page >= 0:
        result = dump_info(get_data(start_page), pics_limit=pics_limit,
                           page_limit=page_limit)
        start_page = result[-1]
        # 达到缓存数量后 写入本地文件
        if total_pic_count >= cache_limit * times or start_page < 0:
            # 保存信息到json
            dump_json(json_body)
            json_body = []

            # 保存信息到sqlite3
            dump_database(database)
            times += 1

    print(colored("已经获取{}页数据 {}张图片，完成\n--- {} seconds ---".format(
            *result[:-1]), "magenta"))

    database.close()
os.system("pause")
