# 云盘strm生成

### 使用说明

目录监控格式：

- 1.监控目录#目的目录#媒体服务器内源文件路径
- 2.监控目录#目的目录#cd2#cd2挂载本地跟路径#cd2服务地址
- 3.监控目录#目的目录#alist#alist挂载本地跟路径#alist服务地址

路径：

- 监控目录：源文件目录即云盘挂载到MoviePilot中的路径
- 目的路径：MoviePilot中strm生成路径
- 媒体服务器内源文件路径：源文件目录即云盘挂载到媒体服务器的路径

示例：

- MoviePilot上云盘源文件路径 /mount/cloud/aliyun/emby`/tvshow/爸爸去哪儿/Season 5/14.特别版.mp4`

- MoviePilot上strm生成路径 /mnt/link/aliyun`/tvshow/爸爸去哪儿/Season 5/14.特别版.strm`

- 媒体服务器内源文件路径 /mount/cloud/aliyun/emby`/tvshow/爸爸去哪儿/Season 5/14.特别版.mp4`

- 监控配置为：/mount/cloud/aliyun/emby#/mnt/link/aliyun#/mount/cloud/aliyun/emby
