# MoviePilot-Plugins
MoviePilot官方插件市场：https://github.com/jxxghp/MoviePilot-Plugins

### [媒体库封面生成 CoverGen](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/covergen)
  > 参考项目：https://github.com/HappyQuQu/jellyfin-library-poster

  CoverGen 用于为 Emby / Jellyfin 媒体库自动生成统一风格的媒体库封面。插件会按已选择的媒体服务器与媒体库抓取海报素材，生成静态或动态封面，并可自动上传回媒体服务器。

  主要用途：
  - 统一电影、电视剧、合集、歌单等媒体库封面风格
  - 支持库白名单、合集来源黑名单、用户黑名单过滤，避免不希望展示的内容参与封面生成
  - 支持多种静态 / 动态封面风格、字体配置、标题缩放、Dry Run 与手动单库重生成
  - 保留历史封面与最近执行记录，便于回看生成结果和排查失败原因

### [云盘Strm助手（CD2增强）](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/strmmanage)
  生成 strm 并支持 CloudDrive2 下载非视频文件，提供 CD2 处理方式配置。

### [CloudDrive2 存储](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/clouddrive2disk)
  通过基于 clouddrivedisk/cd2disk 修改而成的 CloudDrive2 proto 0.9.24 / gRPC 直连与 API 令牌接入 CloudDrive2，注册为 MoviePilot 存储，支持浏览、上传、下载、删除、重命名、移动、复制与空间统计。

### [AnimeZ保活](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/azkeepalive)
  定时访问 AnimeZ 并从种子页选种提交下载器，满足登录和下载保活要求。

### [PT站点自动签到](https://github.com/wuyaos/MoviePilot-Plugins/tree/main/plugins.v2/autoptcheckin)
  自动签到 / 登录站点，支持自定义站点和验证码识别。
