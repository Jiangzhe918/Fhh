# TVBox 全自动无人值守订阅源仓库 v3.0（豆瓣推荐 + 短剧专区 + 15站聚合 + 电视直播自愈版）

本仓库包含 **🌟 豆瓣推荐**、**🎭 短剧聚合专区（同步红果/河马/番茄热播爽剧）**、**15 个主流苹果 CMS 影视采集站**以及 **📺 多路自动探活电视直播源 (`lives`)**，并内置 **GitHub Actions 全自动深度探活、国内权重校准、直播源快照自愈与双配置生成流水线**。上传到 GitHub 后即可作为远程订阅源长期免维护使用。

## 📁 仓库文件说明

| 文件 | 作用 |
| --- | --- |
| `tvbox_config.json` | **标准自适应订阅配置（推荐）**：保持 `./py_douban.py`、`./py_cms_spider.py`、`./live_tv.txt` 相对路径，FongMi 影视 / 影视仓 / TVBoxOSC 套任意镜像前缀订阅时，内部 Python 插件与本地直播源快照自动继承同一镜像加速 |
| `tvbox_mirror.json` | **国内镜像绝对路径配置（兼容老壳子）**：由 Actions 自动将内部 Python 插件与直播源地址改写为带 `https://gh-proxy.com/` 镜像前缀的绝对地址，专供不支持 `./` 相对路径的早期 TVBox 分支订阅 |
| `live_tv.txt` | **🏠 仓库内建自愈电视直播源快照**：由 Actions 每次巡检时自动拉取最快存活直播源、清洗校验并转换生成的本地 TXT 频道表（含央视/卫视/地方台），防止外部直播库删库或 404 导致电视直播断流 |
| `py_douban.py` | 🌟 豆瓣推荐爬虫 v3.0：`vod_id` 内嵌片名/年份/封面秒级容错（防豆瓣 403 白屏）、PC + 移动端 Rexxar 双接口兜底、海报防盗链修复、15 站归一化换源、内置本地代理 M3U8 去广告 |
| `py_cms_spider.py` | 🐍 全聚合 & 🎭 短剧专区双模引擎 v3.0：支持 `mode="all"`（15 站综合聚合）与 `mode="duanju"`（短剧聚合专区，自动提取各站短剧子分类 + 9 大热门爽剧题材直达 + 15 站短剧并发搜索），内置 Master Playlist 最高码率优选与防误杀本地代理去广告 |
| `auto_update_sources.py` | 无人值守深度探活（`?ac=detail` 内容校验）、国内优先级权重校准、短剧强站优选、6 路主流电视直播源探活与 M3U→TXT 清洗合并，同步生成 `tvbox_config.json`、`tvbox_mirror.json` 与 `live_tv.txt` |
| `.github/workflows/update_sources.yml` | GitHub Actions 定时任务（每天北京时间 04:00 与 16:00 自动巡检，含双配置 JSON 校验、直播快照非空校验与 Python 语法编译校验） |

## 🚀 三步开启 GitHub 托管 + 全自动维护

1. **上传至 GitHub 公开仓库**
   新建一个 **Public（公开）** 仓库，把本目录所有文件（**包含隐藏的 `.github` 文件夹**）原样上传到仓库根目录。

2. **开启 Actions 写入权限并运行一次**
   - 仓库 **Settings → Actions → General → Workflow permissions**，勾选 **Read and write permissions** 并 **Save**。
   - 打开 **Actions** 标签页 → 左侧 **Auto Update TVBox Sources** → 右侧 **Run workflow** 手动触发首次巡检，自动生成最新存活的 `tvbox_config.json`、`tvbox_mirror.json` 与 `live_tv.txt`。

3. **在 TVBox / 影视 / 影视仓 中填入订阅链接**

   - **方式 A：标准自适应配置（强烈推荐，FongMi 影视 / 影视仓 / TVBoxOSC 首选）**
     由于 `tvbox_config.json` 采用 `./` 相对路径，你在订阅链接前加任何有效 GitHub 镜像前缀，内部的 Python 爬虫与 `./live_tv.txt` 电视直播都会自动走同一个镜像加载：
     ```text
     https://gh-proxy.com/https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/tvbox_config.json
     ```
     （海外或具备直连条件可直接填 `https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/tvbox_config.json`）

   - **方式 B：内置镜像绝对路径配置（供不支持相对路径的老版本壳子使用）**
     ```text
     https://gh-proxy.com/https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/tvbox_mirror.json
     ```

## ✨ v3.0 核心功能架构

| 模块 | 核心机制 |
| --- | --- |
| **🎭 短剧聚合专区 (`py_duanju_pro`)** | 汇聚量子、索尼、极速、暴风、iKun、卧龙、无尽、豪华、360 等 15 站每日实时同步的红果/河马/番茄短剧资源；自动提取各站短剧细分栏目（现代都市/年代穿越/古装仙侠/脑洞悬疑/女频恋爱/反转爽剧），并内置逆袭、霸总、战神、重生、神医、闪婚、萌宝等 9 大题材筛选与 15 站短剧并发换源 |
| **📺 电视直播自愈 (`lives` + `live_tv.txt`)** | 每次 Actions 运行自动探测范明明 IPv6、vbskycn IPv4/v6、Guovin、YanG、Joevess 等多路直播源，校验有效频道数并将最优源转换为标准 TXT 写入仓库 `./live_tv.txt` 作为首推主线，其余存活源按延迟排序作为直播切换备线，内置 `112114` EPG 电子节目单与高清台标 |
| **🛡️ 国内镜像穿透与防白屏** | 标准配置保留 `./` 相对路径自动继承镜像前缀 + 镜像专版双配置；豆瓣推荐将 `id$title$year$cover` 编码进 `vod_id`，无惧豆瓣接口 403 限流 |
| **🧹 M3U8 最高码率优选与防误杀去广告** | 自动解析 `#EXT-X-STREAM-INF` 选择最高画质子流；结合 `#EXT-X-DISCONTINUITY`、跨域名检测与分片命名模式（顺序编号 vs 随机哈希）精准剔除插播广告 |

## 🖥️ 本地使用 / 二次开发

```bash
pip install requests urllib3

# 本地运行全量探活（点播 + 短剧 + 直播）并更新全部配置
python auto_update_sources.py --repo 你的用户名/仓库名 --branch main

# 自定义国内 GitHub 镜像前缀
python auto_update_sources.py --repo 你的用户名/仓库名 --branch main --mirror-prefix https://gh-proxy.com
```

## ⚠️ 免责声明

本仓库仅供个人学习与技术交流，所有影视及直播资源均来自第三方公开接口，请在当地法律法规允许的范围内使用，支持正版。
