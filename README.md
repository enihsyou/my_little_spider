# 介绍

用来作为练习项目的基于bs4和requests的小爬虫

# CHANGELOG
##v0.3.3 2016-06-28
- 添加对yande.re的支持
- 改进程序的通用性

##v0.3.2 2016-06-26
- 修正线程同步问题
- 修改代码页，让文字正常显示

- 让线程互相自动获取下一页

##v0.3.1 2016-06-26
- 修正json文件分块写入时中途退出造成的文件不完整
- 修正数据库信息添加缺失的失误
- 再次添加处理信息的输出···


##v0.3.0 2016-06-25
- 实现多线程获取，下载

- 完善逻辑
- 修正多份json文件写入时的矛盾
- 修正写入的文件列表顺序是随机的问题
- 添加缺失的文档

##v0.2.4 2016-06-22
- 添加配置文件

- 稍微修改结构，增加信息
- 修正json写入时的编码问题
- 修正当文件不处在时的崩溃
- 移除运行时不必要的用户输入操作

##v0.2.3 2016-06-22
- 启用多线程下载的功能

- 修复服务器端更新图片造成的错误

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

