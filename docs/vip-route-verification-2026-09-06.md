# VIP 播放线路验证（2026-09-06）

样例：https://v.qq.com/x/cover/uo1l1j78851me7b/p0020fdo3so.html?callTime=1788708053391

来源：https://vip.52api.cn/ 的线路选项；仅把通过本机播放检查的候选加入默认列表。

使用项目 Chrome 后台静音浏览器；未忽略证书错误、未处理人机验证。

- 虾米 https://jx.xmflv.cc/ ：页面显示“熊出没之秋日团团转_17”。视频总时长 780.053 秒；连续采样进度 7.64、17.66、27.66 秒，readyState=4，无媒体错误。保留完整 callTime 查询参数再次验证，跳转至 300、700 秒后分别推进到 303.98、703.96 秒。腾讯 getinfo 接口确认 VID p0020fdo3so、标题“熊出没之秋日团团转_17”、时长 780.245 秒，与解析结果一致。没有完整观看全片，也未验证其他 VIP 视频。
- 极速云 https://jx.2s0.cn/player/ ：导航超时；内嵌 analysis.php 页面空白，三次采样没有视频元素，不加入。
- 七哥 https://jx.nnxv.cn/tv.php ：跳到 Cloudflare 人机验证页，未验证播放，不加入。
- 原线路一 1717yun：上轮浏览器跳转后 HTTP 503，本轮移除。
- 原线路三 yparse：上轮浏览器 NET::ERR_CERT_DATE_INVALID，本轮移除。
- 原线路二 jsonplayer：上轮两次加载超时；暂保留并标明待复测。

上述结果只适用于本机、当次测试和该样例，不能推断所有 VIP 内容均可解析。
