# 腾讯视频下载修复实测

验证视频：`https://v.qq.com/x/cover/mzc0020016apvkq/z0022yjl3ep.html`

## 原因与修复

- API 返回的旧签名 CDN 路径约 0.8 KiB/s；直连、系统代理、Range 请求均无明显改善。
- 浏览器播放同一正片正常。浏览器分片地址交给 requests 后测得约 1.6 MiB/s；仅替换旧地址的域名仍慢。
- 浏览器与原播放列表的分片文件名、index、字节范围和 token 一致。使用浏览器完整签名目录、保留原分片参数后，第 0、50、100 个分片均正常响应。
- 低于 16 KiB/s 时，通过后台浏览器的真实响应匹配正片分片，再更新完整 VOD 播放列表的 CDN 目录。拒绝不匹配的 token、范围、文件名，以及混合目录、直播、带 KEY/MAP/BYTERANGE 的列表。
- 本地临时播放列表交给 N_m3u8DL-RE，结束后删除；不在日志中输出签名 URL。
- FFmpeg/FFprobe 输出显式按 UTF-8 解码，修复 Windows GBK 默认解码导致中文文件的轨道校验失败。
- N_m3u8DL-RE 子进程不再弹出控制台窗口。

## 最终验证

- unittest：62 项，52 项通过，10 项原有跳过。
- 整集实际下载成功，总耗时 53.8 秒，包含解析、旧线路探测、浏览器线路捕获、下载与校验。
- 输出：`downloads/tencent-verified/给我一块钱_02 [browser].mp4`。
- 文件大小：48,728,946 字节。
- FFprobe：HEVC 视频 608×486、AAC 音频；容器时长 1341.226646 秒，与播放器的 1341.226 秒一致。
- 本次结果验证了上述视频；不同编码、需要登录的内容及其他播放列表结构未做真实验证。

## 启动环境

从自动化工具启动时，Windows 架构环境变量可能缺失，导致 Selenium Manager 报 `Unsupported platform/architecture combination: win32/`。
本次启动在进程环境中按系统实际架构补齐 `PROCESSOR_ARCHITECTURE`，未修改机器全局环境变量。
