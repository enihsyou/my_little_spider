# -*- coding: utf-8 -*-
"""
File name: konachan
Reference:
Introduction: 下载konachan.com上面的图片的小爬虫
Date: 2016-06-04
Last modified: 2016-06-28
Author: enihsyou
"""
import json
import os
import re
import sqlite3
from collections import OrderedDict
from queue import Queue
from threading import Thread, Lock
from time import perf_counter, sleep

import requests
from bs4 import BeautifulSoup

# 参数定义(default)
base_url = "http://konachan.com"
json_file_name = "konachan.json"  # 保存信息的json文件名
database_file_name = "konachan.sqlite3"  # 保存的sqlite3文件名
large_img_dir_name = "images"  # 大图文件夹的名字
thumb_dir_name = "thumb"  # 缩略图文件夹的名字
start_page = 1  # 起始页面
pics_limit = -1  # 限制获取的图片数量 (-1=无限)
page_limit = -1  # 限制获取的页面数量 (-1=无限)
DOWNLOAD_LARGE_IMG = False  # 是否同时下载大图
DOWNLOAD_THUMB = False  # 是否同时下载缩略图
THREAD_WAITING_TIME = 0.5  # 线程获取数据的等待时间
PROXY = "http://localhost:8087"  # 本地HTTP代理，使用GAE:8087
DUPLICATE_OVERWRITE = True  # 遇到同名文件是否覆盖
DATA_DROP = True  # 是否默认清除先前的数据 (default: True)
cache_limit = 1000  # 写入文件需要达到的缓存数量
THREAD_LIMIT = os.cpu_count()  # 运行中的线程数量限制

CONFIG_FILE = json_file_name.replace(".json", "_config.json")  # 配置文件
DEFAULT_PARAMETER = OrderedDict((
    ("base_url", base_url),
    ("json_file_name", json_file_name),  # 保存的json文件名
    ("database_file_name", database_file_name),  # 保存的sqlite3文件名
    ("large_img_dir_name", large_img_dir_name),  # 大图文件夹的名字
    ("thumb_dir_name", thumb_dir_name),  # 缩略图文件夹的名字
    ("start_page", start_page),  # 起始页面
    ("pics_limit", pics_limit),  # 限制获取的图片数量 (-1=无限)
    ("page_limit", page_limit),  # 限制获取的页面数量 (-1=无限)
    ("DOWNLOAD_LARGE_IMG", DOWNLOAD_LARGE_IMG),  # 是否同时下载大图
    ("DOWNLOAD_THUMB", DOWNLOAD_THUMB),  # 是否同时下载缩略图
    ("THREAD_WAITING_TIME", THREAD_WAITING_TIME),  # 线程获取数据的等待时间
    ("PROXY", PROXY),  # 本地HTTP代理，使用GAE":8087
    ("DATA_DROP", DATA_DROP),  # 是否默认清除先前的数据 (default: False)
    ("DUPLICATE_OVERWRITE", DUPLICATE_OVERWRITE),  # 遇到同名文件是否覆盖
    ("cache_limit", cache_limit),  # 写入文件需要达到的缓存数量
    ("THREAD_LIMIT", THREAD_LIMIT))  # 运行中的线程数量限制
)
# 正则表达式搜索定义
RE_TITLE_TAG = re.compile(r"Tags: (.+) User")  # 抓取出tag内容
RE_PAGE_NUMBER = re.compile(r"page=(\d+)")  # 抓取出page，当前页数
RE_PIC_ID = re.compile(r"\b(\d+)\b")  # 抓取出图片id
RE_PICS_CLASS = re.compile(r"creator-id-\d*")  # 图片的所在位置的class
# RE_BASE_URL = re.compile("^" + base_url)  # 用于去除http://hostname.xxx开头
RE_HOST_NAME = re.compile(r"(?<=http://)?([^/]+?)\..+/?")  # 捕获次级域名
RE_VALID_PATH = re.compile(r"[:<>\"/\\\|\?\*]")  # 替换有效文件路径

# 字段定义
session = requests.Session()
download_queue = Queue()  # 下载队列
update_queue = Queue()  # 等待更新写入队列
page_queue = Queue()  # 页面获取队列
UPDATE_QUEUE_LOCK = Lock()  # 更新数据用的锁
EXIT_FLAG = False  # 程序退出的标志
working_downloader_threads = []  # 工作中的下载器线程
working_page_threads = []  # 工作中的页面获取进程
total_pic_count = 0  # 总共获取了多少图片的信息
START_TIME = 0  # 处理开始的时间
get_time = 0  # 获取页面的起始时间
cache_pages = 0  # 缓存中的页面数量
last_page = 0  # 最后获取成功的页面
result = []  # 包含下一页的信息或者退出的信息
DATABASE_TABLE_NAME = RE_HOST_NAME.search(base_url).group(0).rsplit(".")[0]  # 数据库表名

# 发送的HEADER
session.headers.update({
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, sdch"})

# 代理设置
session.proxies.update({PROXY.split("://")[0]: PROXY})


def get_data(page):
    """连接第`page`页

    直接使用page参数get，而不是从网页中获取的信息
    Args:
        page (str(int)): 页数

    Returns:
        bs4.BeautifulSoup: 连接的Soup
        time (int): 连接消耗的时间

    Raises:
        Exception (ERROR): 连接出问题
    """
    try:
        get_time = perf_counter()
        response = session.get(base_url + "/post", params={"page": page})
        response.raise_for_status()
    except Exception as ERROR:
        print(ERROR)
        raise ERROR

    return BeautifulSoup(response.text, "lxml"), perf_counter() - get_time


def make_json(file_name):
    """创建json文件，判断是否覆盖，并初始化"""
    FILE_EXISTS = os.path.exists(file_name)
    if not DATA_DROP and FILE_EXISTS: return

    with open(file_name, "w", encoding="utf-8") as file:
        file.write("[  ")  # 加空格是为了在后面去掉


def exit_handler():
    """处理退出必要的操作"""
    global EXIT_FLAG

    try:
        # 等待队列清空
        for t in working_page_threads:
            t.join()

        update_queue.join()
        download_queue.join()

        # 通知线程已经结束
        EXIT_FLAG = True

        # 终止线程
        update_thread.join()
        for t in working_downloader_threads:
            t.join()
    finally:
        print("已经获取{}页数据 {}张图片，完成\n--- {:.4f} seconds ---".format(
                last_page - start_page + 1, total_pic_count, perf_counter() - START_TIME))
        exit()


def extract_info(li):
    """提取出一个对象中的图片信息"""
    pic = Picture()
    # 图片详细页面
    tag_thumb = li.find("a", class_="thumb")  # type: bs4.Tag 图片的缩略图链接
    pic.add("information_link", tag_thumb["href"])

    # 图片的缩略图的URL
    tag_thumb_img = tag_thumb.img  # type: bs4.Tag 图片的缩略图tag
    pic.add("thumb_img_URL", tag_thumb_img["src"])

    # 图片Tags和id
    title_container = tag_thumb_img["alt"]
    tags = RE_TITLE_TAG.search(title_container).group(1)  # 取出tag
    pic_id = li["id"][1:]  # 图片在站点上的id "p123456"
    pic.add(tags=tags, id=pic_id)

    # 默认大图的链接和图片实际分辨率
    direct_link_container = li.find("a", class_="directlink")
    resolution = direct_link_container.find("span", class_="directlink-res")
    pic.add(sample_img_URL=direct_link_container["href"],
            resolution=resolution.text)

    # 添加图片长度和宽度以及index
    width, height = resolution.text.split(" x ")
    pic.add(width=int(width), height=int(height), index=total_pic_count)

    return pic


def add_base_url(url, base_url=base_url):
    """将相对链接变成绝对链接

    Args:
        url (str): 需要处理的url字符串
        base_url (str): 要添加的域名

    Returns:
        (str): 包含了base_link的url
    """
    if url.startswith("/"):
        return base_url + url
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


def download_img(url, file_name, suffix=".jpg", thumb=False, thread=""):
    """下载url下的图片

    Args:
        url (str): 要下载的链接
        file_name (list): 打算存的文件名列表，会用join处理 添加空格
        suffix (str): 保存文件的后缀名，大部分是jpg格式的 (default: ".jpg")
        thumb (bool): 是否是缩略图，是的话会放到一个叫thumb的目录下 (default: False)
        thread (str): 下载所在的进程名字 debug用
    Raises:
        Exception (ERROR): 连接出现了问题(大概)
    """
    url = add_base_url(url)
    start_time = perf_counter()
    try:
        data = session.get(url).content
    except requests.Timeout as ERROR:
        print("超时", "red")
        raise ERROR
    except Exception as ERROR:
        print(ERROR, "red")
        raise ERROR
    base_url_host_name = RE_HOST_NAME.search(base_url).group(1)
    file_name = [RE_VALID_PATH.sub("_", a) for a in file_name]
    file_name = " ".join(map(str, [base_url_host_name] + file_name))[:210] + suffix  # 长于210字符的会被切断
    if thumb:
        file_path = os.path.join("./" + thumb_dir_name, file_name)
    else:
        file_path = os.path.join("./" + large_img_dir_name, file_name)

    if os.path.exists(file_path):  # 处理同名文件
        print("同名文件已存在 id: {}".format(RE_PIC_ID.search(file_name).group(1)))
        if not DUPLICATE_OVERWRITE:
            return
    with open(file_path, "wb") as _file:
        bytes_write = _file.write(data)
    file_size = format_size(bytes_write)
    print("下载成功({} 大小: {} {:.4f}s): {}".format(thread, file_size, perf_counter() - start_time, file_name))


class DownloadThread(Thread):
    """下载器线程"""

    def __init__(self):
        super().__init__()

    def run(self):
        while not download_queue.empty() or not EXIT_FLAG:
            if not download_queue.empty():
                work = download_queue.get()  # 取得一个任务
                try:
                    work["target"](*work["args"], thread=self.getName())  # 进行下载
                    download_queue.task_done()
                except requests.Timeout:
                    download_queue.put(work)  # 失败则重新放回队列
                except Exception as ERROR:
                    raise ERROR

            sleep(THREAD_WAITING_TIME)


class Picture:
    """储存有一张图片的信息"""

    def __init__(self, **pic_info):
        self.information = OrderedDict((
            ("index", 0),  # 获取的序号
            ("id", 0),  # 图片在站点上的id
            ("tags", ""),  # 图片tags
            ("information_link", ""),  # 图片详细页面
            ("sample_img_URL", ""),  # 默认大图链接
            ("thumb_img_URL", ""),  # 缩略图链接
            ("resolution", ""),  # 图片实际分辨率
            ("width", 0),  # 宽
            ("height", 0))  # 高
        )
        if pic_info: self.add(pic_info)
        self.index = 0
        self.id = 0
        self.tags = ""
        self.information_link = ""
        self.thumb_img_URL = ""
        self.sample_img_URL = ""
        self.resolution = ""
        self.width = 0
        self.height = 0

    def add(self, *field_info, **info_dict):
        """添加信息"""
        ordered_dict = self.information
        if field_info:
            field, info = field_info
            ordered_dict[field] = info
            try:
                setattr(self, field, info)
            except Exception as E:
                print(E)
        if info_dict:
            for key in info_dict:
                ordered_dict[key] = info_dict[key]
                try:
                    setattr(self, key, info_dict[key])
                except Exception as E:
                    print(E)

    def get(self, item):
        """返回一条对应的信息"""
        return self.information[item]


class PageThread(Thread):
    """获取一页每张图片的信息的一条线程"""

    def __init__(self):
        super().__init__()
        self.working_page = 0  # 线程的工作页面
        self.html = None
        self.connect_time = 0  # 连接开始的时间
        self.pic_list = None  # 所有图片列表
        self.parser_time = 0  # 处理页面消耗的时间
        # self.paginator = self.html.find("div", id="paginator")  # 页面导航栏

    def run(self):
        """线程执行"""

        # 程序没有退出而且没有达到最后一面
        while not EXIT_FLAG:
            working_page = page_queue.get()
            page_queue.put(working_page + 1)
            self.init(working_page)

            # 处理到达最后一面的情况 或者 特殊意外
            if self.html is not None:
                if working_page == -1: return
                self.pic_list = self.html.find_all("li")  # 所有图片列表
                self.parser(self.pic_list)
                if working_page == page_limit: return
            else:
                return

    def init(self, working_page):
        """初始化，主要判断是否有可获取的内容"""
        self.working_page = working_page
        container, self.connect_time = get_data(working_page)
        self.html = container.find("ul", id="post-list-posts")

    def parser(self, pics_list):
        """从列表中获取信息"""
        global total_pic_count, cache_pages, last_page
        print("{} 当前页面: {}".format(self.getName(), self.working_page))
        start_time = perf_counter()
        last_page = max(self.working_page, last_page)

        for pic in pics_list:
            if pic is None: break
            if total_pic_count == pics_limit: break  # 达到图片总数限制

            total_pic_count += 1
            cache_pages += 1

            # 提取信息
            pic_info = extract_info(pic)

            # 添加到待更新队列
            with UPDATE_QUEUE_LOCK:
                update_queue.put(pic_info.information)

            # 打印当前信息
            print(pic_info.id, pic_info.information_link)

            # 下载
            if DOWNLOAD_THUMB:  # 下载缩略图
                download_queue.put({"target": download_img,
                                    "args": (pic_info.thumb_img_URL,
                                             [pic_info.id, thumb_dir_name, pic_info.tags], ".jpg", True)})
            if DOWNLOAD_LARGE_IMG:  # 下载jpg大图
                download_queue.put({"target": download_img,
                                    "args": (pic_info.sample_img_URL, [pic_info.id, pic_info.tags], ".jpg")})

            # 跳出条件检测
            if total_pic_count == pics_limit:
                break
        self.parser_time = perf_counter() - start_time
        print("连接时间: {:.4f}s 处理时间: {:.4f}s 本页获取: {} 缓存: {}/{} 已获取:{} 启动: {:.4f}s\n".format(
                self.connect_time, self.parser_time, len(pics_list), cache_pages, cache_limit, total_pic_count,
                perf_counter() - START_TIME))


class UpdateThread(Thread):
    """单独线程读写数据库"""

    def __init__(self):
        super().__init__()

        self.json_body = []  # 需要一起写入到文件的信息

        # 连接数据库
        self.database = None  # 内存数据库
        self.local_database = None  # 本地数据库

    def run(self):
        global cache_pages

        self.init_database()
        self.init_local_database()

        while not EXIT_FLAG:
            if update_queue.empty():
                sleep(THREAD_WAITING_TIME)
            else:
                work = update_queue.get()
                self.update_json(work)
                self.update_database(work)
                if cache_pages >= cache_limit:
                    with UPDATE_QUEUE_LOCK:  # 锁定队列
                        # 保存信息到json
                        self.dump_json()
                        self.json_body = []

                        # 保存信息到sqlite3
                        self.dump_database()

                        cache_pages = 0
                update_queue.task_done()
        self.exit()

    def init_database(self):
        """初始化内存数据库"""
        self.database = sqlite3.connect(":memory:")  # 连接内存数据库
        self.database.execute(
                r"""
                CREATE TABLE {}(
                    id INTEGER NOT NULL PRIMARY KEY UNIQUE,
                    tags TEXT,
                    information_link TEXT,
                    sample_img_URL TEXT,
                    thumb_img_URL TEXT,
                    resolution TEXT,
                    height INTEGER,
                    width INTEGER);
                """.format(DATABASE_TABLE_NAME))
        self.database.commit()

    def init_local_database(self):
        """初始化本地数据库文件"""
        self.local_database = sqlite3.connect(database_file_name)  # 连接本地数据库
        if DATA_DROP:
            self.local_database.execute("DROP TABLE IF EXISTS {}".format(DATABASE_TABLE_NAME))
            self.local_database.executescript("".join(self.database.iterdump()))

    def update_json(self, information_dict):
        """添加一条信息到待写入列表"""
        self.json_body.append(information_dict)

    def update_database(self, information_dict):
        """写入信息到内存数据库"""
        try:
            self.database.execute(
                    r"""
                    INSERT INTO {} (
                    id, tags, information_link, sample_img_URL, thumb_img_URL, resolution, height, width)
                    VALUES ({},{},{},{},{},{},{},{})
                    """.format(
                            DATABASE_TABLE_NAME,
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
                            information_dict["width"],
                            information_dict["height"]
                    )
            )
        except sqlite3.IntegrityError:
            print(information_dict["id"])

    def dump_json(self):
        """增量写入json文件"""
        start_time = perf_counter()
        with open(json_file_name, "rb+") as file:
            json_data = json.dumps(self.json_body, indent=True, ensure_ascii=False)  # 写入文件
            json_data = json_data[1:]
            file.seek(-3, 2)
            start = file.read(1)
            if start == b"[":
                file.write(json_data.encode())
            else:
                file.write(("," + json_data).encode())
        print("写入 {} 完成… {} {:.4f}s".format(json_file_name, format_size(
                os.path.getsize(json_file_name)), perf_counter() - start_time))

    def dump_database(self):
        """增量写入本地数据库"""
        start_time = perf_counter()
        self.database.commit()

        database_iter = self.database.iterdump()

        with sqlite3.connect(database_file_name) as db:
            for line in database_iter:
                if line.startswith("INSERT"):
                    try:
                        db.execute(line)
                    except sqlite3.IntegrityError:  # 可能由于服务器更新了新的图片
                        pass
        self.database.execute("DELETE FROM {}".format(DATABASE_TABLE_NAME))
        print("写入 {} 完成… {} {:.4f}s".format(database_file_name, format_size(
                os.path.getsize(database_file_name)), perf_counter() - start_time))

    def exit(self):
        self.dump_json()
        self.dump_database()
        self.database.close()
        self.local_database.close()


if __name__ == "__main__":
    # 更改代码页
    os.system("chcp 65001")
    os.system("cls")

    # 信息载入
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            try:
                config = json.loads(f.read(), "utf-8")
            except Exception:
                raise
            for line in config:
                exec("{} = config[line]".format(line))
    else:  # 如果配置文件不存在则创建
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(DEFAULT_PARAMETER, ensure_ascii=False, indent=True))

    # 创建下载文件夹
    if DOWNLOAD_THUMB:
        if not os.path.exists(thumb_dir_name):
            os.mkdir(thumb_dir_name)
    if DOWNLOAD_LARGE_IMG:
        if not os.path.exists(large_img_dir_name):
            os.mkdir(large_img_dir_name)

    # 判断要写入的文件是否存在，并创建
    make_json(json_file_name)

    # 启动下载器线程
    for _ in range(THREAD_LIMIT):
        thread = DownloadThread()
        thread.start()
        working_downloader_threads.append(thread)  # 添加到工作中的线程队列

    # 启动文件更新线程
    update_thread = UpdateThread()
    update_thread.start()

    # 启动爬虫线程
    START_TIME = perf_counter()  # 爬虫启动时间
    page_queue.put(start_page)
    for _ in range(THREAD_LIMIT):
        thread = PageThread()
        thread.start()
        working_page_threads.append(thread)

    # 退出准备
    exit_handler()
    os.system("pause")
