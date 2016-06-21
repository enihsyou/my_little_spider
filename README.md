# 介绍

用来作为练习项目的基于bs4和requests的小爬虫

# CHANGELOG
##v0.2.2 2016-06-22
- 优化逻辑，避免递归过多
- 达到数量写入文件，保存数据
- 优化页面控制


##v0.2.1 2016-06-21
- 增加了konachan的起始页面功能
- 增加了执行时间统计功能

- 修复表重复时的bug


##v0.2.0 2016-06-21
- 给konachan的爬虫添加了写入sqlite数据库的功能


##v0.1.0 2016-06-07
比较早的练手项目

能够做到:

1. konachan.com
    - 抓取页面图片信息
    - 导出json文件
    - 下载原始图片和缩略图

2. bilibili.com
    - 抓取番剧播放信息

---
缺少的待添加的功能

- 写入数据库
- 多线程下载
- GUI
- 搜索功能
- tag
