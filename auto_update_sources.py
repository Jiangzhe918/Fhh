# -*- coding: utf-8 -*-
"""
TVBox 采集站 + 短剧专区 + 电视直播源 (lives) 全自动探活与双配置生成脚本 (v3.0)

核心升级特性：
1. 【15站全量池 + 短剧强站优选】：覆盖 15 个主流综合与短剧采集站（含暴风、iKun、卧龙等），单独计算短剧强站最优主站并自动注入 `py_duanju_pro`（🎭 短剧聚合专区）。
2. 【电视直播源 (lives) 自动探活、M3U/TXT 双格式清洗与仓库本地快照自愈】：
   - 内置多路主流开源 IPTV 直播源候选池 + 上游仓库 `lives` 动态嗅探；
   - 自动探测各直播源 HTTP 可用性与有效频道数量（过滤 404/空壳页面），支持将 M3U 格式自动转换为 TVBox 标准 `,#genre#` TXT 格式；
   - 每次巡检自动合并最优存活直播源生成仓库内建 `./live_tv.txt` 快照（防上游删库失联），并在配置 `lives` 列表中同时挂载本地快照主线与多路远程存活备线（自带 EPG 节目单与台标接口）。
3. 【深度内容探活与国内权重校准】：优先探测 `?ac=detail&pg=1` 校验实际片源数据非空，叠加国内体验权重分防止海外节点抢占默认主站。
4. 【相对路径主配置 + 国内镜像加速双配置输出】：同步生成 `tvbox_config.json`（保留 `./` 相对路径）与 `tvbox_mirror.json`（自动为 `.py` 插件和 `live_tv.txt` 注入国内镜像前缀）。
"""

import copy
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 15个主流综合与短剧采集站的官方主备域名池、匹配关键词与国内优先级权重
SITE_MATRIX = {
    "lzi": {
        "config_key": "lzi_cms",
        "tier_penalty": -80,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["量子"],
        "url_keywords": ["lzi", "lzzy"],
        "candidates": [
            "http://cj.lziapi.com/api.php/provide/vod/",
            "https://cj.lziapi.com/api.php/provide/vod/",
            "http://cj.lzzyapi.com/api.php/provide/vod/"
        ]
    },
    "ffzy": {
        "config_key": "ffzy_cms",
        "tier_penalty": -80,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["非凡"],
        "url_keywords": ["ffzy"],
        "candidates": [
            "http://cj.ffzyapi.com/api.php/provide/vod/",
            "https://cj.ffzyapi.com/api.php/provide/vod/",
            "http://ffzy5.tv/api.php/provide/vod/",
            "http://ffzy1.tv/api.php/provide/vod/"
        ]
    },
    "suoni": {
        "config_key": "suoni_cms",
        "tier_penalty": -65,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["索尼"],
        "url_keywords": ["suoni", "snzy"],
        "candidates": [
            "https://suoniapi.com/api.php/provide/vod/",
            "http://suoniapi.com/api.php/provide/vod/"
        ]
    },
    "jisu": {
        "config_key": "jisu_cms",
        "tier_penalty": -55,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["极速"],
        "url_keywords": ["jszy", "jisu"],
        "candidates": [
            "https://jszyapi.com/api.php/provide/vod/",
            "http://jszyapi.com/api.php/provide/vod/"
        ]
    },
    "bfzy": {
        "config_key": "bfzy_cms",
        "tier_penalty": -45,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["暴风"],
        "url_keywords": ["bfzy", "baofeng"],
        "candidates": [
            "https://bfzyapi.com/api.php/provide/vod/",
            "http://bfzyapi.com/api.php/provide/vod/",
            "https://app.bfzyapi.com/api.php/provide/vod/"
        ]
    },
    "ikun": {
        "config_key": "ikun_cms",
        "tier_penalty": -30,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["ikun", "爱坤"],
        "url_keywords": ["ikunzy", "ikun"],
        "candidates": [
            "https://ikunzyapi.com/api.php/provide/vod/",
            "http://ikunzyapi.com/api.php/provide/vod/"
        ]
    },
    "wolong": {
        "config_key": "wolong_cms",
        "tier_penalty": -20,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["卧龙"],
        "url_keywords": ["wolong"],
        "candidates": [
            "https://collect.wolongzyw.com/api.php/provide/vod/",
            "https://collect.wolongzy.cc/api.php/provide/vod/"
        ]
    },
    "guangsu": {
        "config_key": "guangsu_cms",
        "tier_penalty": 0,
        "eligible_default": True,
        "duanju_strong": False,
        "name_keywords": ["光速"],
        "url_keywords": ["guangsu", "gszy"],
        "candidates": [
            "https://api.guangsuapi.com/api.php/provide/vod/",
            "http://api.guangsuapi.com/api.php/provide/vod/"
        ]
    },
    "tiankong": {
        "config_key": "tiankong_cms",
        "tier_penalty": 0,
        "eligible_default": True,
        "duanju_strong": False,
        "name_keywords": ["天空"],
        "url_keywords": ["tiankong", "tkzy"],
        "candidates": [
            "http://m3u8.tiankongapi.com/api.php/provide/vod/",
            "https://m3u8.tiankongapi.com/api.php/provide/vod/",
            "https://api.tiankongapi.com/api.php/provide/vod/"
        ]
    },
    "hongniu": {
        "config_key": "hongniu_cms",
        "tier_penalty": 0,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["红牛"],
        "url_keywords": ["hongniu", "hnzy"],
        "candidates": [
            "https://hongniuzy2.com/api.php/provide/vod/",
            "https://www.hongniuzy2.com/api.php/provide/vod/",
            "https://www.hongniuzy3.com/api.php/provide/vod/"
        ]
    },
    "wujin": {
        "config_key": "wujin_cms",
        "tier_penalty": 15,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["无尽"],
        "url_keywords": ["wujin", "wjzy"],
        "candidates": [
            "https://api.wujinapi.com/api.php/provide/vod/",
            "https://api.wujinapi.me/api.php/provide/vod/",
            "https://api.wujinapi.net/api.php/provide/vod/",
            "https://api.wujinapi.cc/api.php/provide/vod/"
        ]
    },
    "haohua": {
        "config_key": "haohua_cms",
        "tier_penalty": 15,
        "eligible_default": True,
        "duanju_strong": True,
        "name_keywords": ["豪华"],
        "url_keywords": ["hhzy", "haohua"],
        "candidates": [
            "https://hhzyapi.com/api.php/provide/vod/",
            "http://hhzyapi.com/api.php/provide/vod/"
        ]
    },
    "baidu": {
        "config_key": "baidu_cms",
        "tier_penalty": 350,
        "eligible_default": False,
        "duanju_strong": False,
        "name_keywords": ["百度"],
        "url_keywords": ["apibdzy", "bdzy"],
        "candidates": [
            "https://api.apibdzy.com/api.php/provide/vod/",
            "http://api.apibdzy.com/api.php/provide/vod/"
        ]
    },
    "360zy": {
        "config_key": "360_cms",
        "tier_penalty": 350,
        "eligible_default": False,
        "duanju_strong": True,
        "name_keywords": ["360"],
        "url_keywords": ["360zy"],
        "candidates": [
            "https://360zy.com/api.php/provide/vod/",
            "http://360zy.com/api.php/provide/vod/",
            "https://360zy5.com/api.php/provide/vod/"
        ]
    },
    "haiwaikan": {
        "config_key": "haiwaikan_cms",
        "tier_penalty": 1500,
        "eligible_default": False,
        "duanju_strong": False,
        "name_keywords": ["海外看"],
        "url_keywords": ["haiwaikan", "hwk"],
        "candidates": [
            "https://haiwaikan.com/api.php/provide/vod/",
            "https://www.haiwaikan.com/api.php/provide/vod/"
        ]
    }
}

# 电视直播源 (lives) 候选矩阵（支持 M3U 与 TVBox TXT 格式）
LIVE_CANDIDATES = [
    {
        "name": "📺 范明明 IPv6/v4 高清直播",
        "url": "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
        "ua": "okhttp/3.15"
    },
    {
        "name": "📡 vbskycn 央卫全聚合直播",
        "url": "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "ua": "okhttp/3.15"
    },
    {
        "name": "🌐 vbskycn IPv6 专线直播",
        "url": "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv6.txt",
        "ua": "okhttp/3.15"
    },
    {
        "name": "⚡ Guovin 自动测速电视直播",
        "url": "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
        "ua": "okhttp/3.15"
    },
    {
        "name": "🎬 YanG 体育与综合聚合直播",
        "url": "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
        "ua": "okhttp/3.15"
    },
    {
        "name": "🛰️ Joevess 央视卫视精选源",
        "url": "https://raw.githubusercontent.com/joevess/IPTV/main/home.m3u8",
        "ua": "okhttp/3.15"
    }
]

DEFAULT_EPG_URL = "https://epg.112114.xyz/?ch={name}&date={date}"
DEFAULT_LOGO_URL = "https://epg.112114.xyz/logo/{name}.png"

UPSTREAM_SOURCES = [
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://raw.githubusercontent.com/YuanHsing/freed/master/TVBox/interface.txt"
]

DEFAULT_MIRROR_PREFIX = "https://gh-proxy.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, application/xml, text/xml, */*"
}


def _validate_cms_payload(text, require_non_empty=True):
    text = (text or "").strip()
    if not text:
        return False
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if require_non_empty:
                return bool(data.get("list") or data.get("class"))
            return "list" in data or "class" in data
        except Exception:
            return False
    if text.startswith("<?xml") or "<rss" in text[:100]:
        if require_non_empty:
            return "<video>" in text or "<ty " in text
        return "<class>" in text or "<list" in text
    return False


def probe_cms_api(api_url, timeout=8):
    """
    深度探测单个 CMS 接口是否存活：
    优先请求 ?ac=detail&pg=1 验证实际片源数据非空，若站点限制则回退 ?ac=list
    """
    for ac_mode in ("detail", "list"):
        start = time.time()
        try:
            params = {"ac": ac_mode, "pg": "1"} if ac_mode == "detail" else {"ac": "list"}
            resp = requests.get(
                api_url,
                params=params,
                headers=HEADERS,
                timeout=timeout,
                verify=False,
                allow_redirects=True
            )
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code != 200:
                continue
            if _validate_cms_payload(resp.text, require_non_empty=True):
                final_url = resp.url.split("?")[0]
                if not final_url.endswith("/"):
                    final_url += "/"
                return True, final_url, latency_ms
        except Exception:
            continue
    return False, api_url, 99999


def scrape_upstream_candidates():
    """
    从社区上游公开仓库自动提取包含 /api.php/provide/vod/ 的最新存活域名及站点名上下文
    """
    discovered = []
    seen_urls = set()
    url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-_]+(?::\d+)?/api\.php/provide/vod/?')
    obj_pattern = re.compile(r'\{[^{}]*?/api\.php/provide/vod/[^{}]*?\}', re.DOTALL)

    for src_url in UPSTREAM_SOURCES:
        try:
            resp = requests.get(src_url, headers=HEADERS, timeout=10, verify=False)
            if resp.status_code != 200:
                continue
            text = resp.text
            for obj_str in obj_pattern.findall(text):
                m_url = url_pattern.search(obj_str)
                if m_url:
                    raw_u = m_url.group(0)
                    norm_u = raw_u if raw_u.endswith("/") else raw_u + "/"
                    if norm_u not in seen_urls:
                        seen_urls.add(norm_u)
                        discovered.append((obj_str, norm_u))
            for line in text.splitlines():
                for raw_u in url_pattern.findall(line):
                    norm_u = raw_u if raw_u.endswith("/") else raw_u + "/"
                    if norm_u not in seen_urls:
                        seen_urls.add(norm_u)
                        discovered.append((line, norm_u))
        except Exception:
            continue
    return discovered


def resolve_best_apis():
    """并发探测所有 15 个站点的候选池，结合国内体验权重返回每个站点的最优存活 API"""
    upstream_entries = scrape_upstream_candidates()
    best_results = {}

    for site_key, meta in SITE_MATRIX.items():
        candidates = list(meta["candidates"])
        for ctx_text, up_url in upstream_entries:
            name_hit = any(nk.lower() in ctx_text.lower() for nk in meta.get("name_keywords", []))
            url_hit = any(uk.lower() in up_url.lower() for uk in meta.get("url_keywords", []))
            if (name_hit or url_hit) and up_url not in candidates:
                candidates.append(up_url)

        best_url = candidates[0]
        best_latency = 99999
        alive_found = False

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(probe_cms_api, url): url for url in candidates}
            for fut in as_completed(futures):
                ok, final_url, latency = fut.result()
                if ok and latency < best_latency:
                    best_latency = latency
                    best_url = final_url
                    alive_found = True

        penalty = meta.get("tier_penalty", 0)
        weighted_score = (best_latency + penalty) if alive_found else (99999 + penalty)

        best_results[site_key] = {
            "config_key": meta["config_key"],
            "api": best_url,
            "alive": alive_found,
            "latency_ms": best_latency,
            "weighted_score": weighted_score,
            "eligible_default": meta.get("eligible_default", True),
            "duanju_strong": meta.get("duanju_strong", False)
        }
        status_tag = f"✅ 存活 (实测 {best_latency}ms | 权重分 {weighted_score})" if alive_found else "⚠️ 暂不可达 (保留原地址并降权置底)"
        print(f"[{site_key}] {status_tag} -> {best_url}")

    return best_results


# ==================== 电视直播源 (lives) 探活、M3U/TXT 转换与本地自愈快照 ====================

def convert_m3u_to_txt(m3u_text):
    """
    将标准 #EXTM3U 直播源文本转换为 TVBox 通用 TXT 分组格式 (`分组名,#genre#` + `频道名,URL`)
    """
    groups = {}
    group_order = []
    current_group = "精选直播"
    current_name = ""

    for raw_line in m3u_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            g_match = re.search(r'group-title="([^"]+)"', line, re.IGNORECASE)
            current_group = g_match.group(1).strip() if g_match else "精选直播"
            if "," in line:
                current_name = line.rsplit(",", 1)[-1].strip()
            else:
                current_name = "未知频道"
        elif not line.startswith("#") and re.match(r"^(?:https?|rtmp|rtsp|mitv|p3p)://", line, re.IGNORECASE):
            if current_name:
                if current_group not in groups:
                    groups[current_group] = []
                    group_order.append(current_group)
                groups[current_group].append(f"{current_name},{line}")
                current_name = ""

    out_lines = []
    for grp in group_order:
        out_lines.append(f"{grp},#genre#")
        out_lines.extend(groups[grp])
        out_lines.append("")
    return "\n".join(out_lines).strip()


def parse_and_validate_live_text(raw_text):
    """
    校验直播源内容是否有效，返回 (is_valid: bool, channel_count: int, normalized_txt: str)
    """
    text = (raw_text or "").strip()
    if not text or "<html" in text[:300].lower():
        return False, 0, ""

    # 1. M3U 格式
    if text.startswith("#EXTM3U") or "#EXTINF:" in text[:1000]:
        txt_converted = convert_m3u_to_txt(text)
        ch_lines = [
            l for l in txt_converted.splitlines()
            if "," in l and not l.endswith("#genre#") and "://" in l
        ]
        if len(ch_lines) >= 5:
            return True, len(ch_lines), txt_converted
        return False, 0, ""

    # 2. TVBox TXT 格式 (包含 ,#genre# 或 频道名,http...)
    clean_lines = []
    ch_count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ",#genre#" in line:
            clean_lines.append(line)
        elif "," in line and re.search(r",\s*(?:https?|rtmp|rtsp|mitv|p3p)://", line, re.IGNORECASE):
            clean_lines.append(line)
            ch_count += 1

    if ch_count >= 5:
        return True, ch_count, "\n".join(clean_lines)
    return False, 0, ""


def probe_live_source(candidate, timeout=8):
    """探测单个电视直播源 URL 的可用性、延迟与有效频道数量"""
    url = candidate["url"]
    start = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        latency_ms = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            resp.encoding = "utf-8"
            ok, ch_count, norm_txt = parse_and_validate_live_text(resp.text)
            if ok:
                return {
                    "name": candidate["name"],
                    "url": resp.url,
                    "ua": candidate.get("ua", "okhttp/3.15"),
                    "alive": True,
                    "latency_ms": latency_ms,
                    "channel_count": ch_count,
                    "normalized_txt": norm_txt
                }
    except Exception:
        pass
    return {
        "name": candidate["name"],
        "url": url,
        "ua": candidate.get("ua", "okhttp/3.15"),
        "alive": False,
        "latency_ms": 99999,
        "channel_count": 0,
        "normalized_txt": ""
    }


def resolve_best_lives(live_txt_path="live_tv.txt"):
    """
    并发探测全部候选电视直播源，将最快且频道最全的存活源写入本地自愈快照 `live_tv.txt`，
    并返回排序后的直播源探测结果。
    """
    print("\n📺 开始探测电视直播源 (lives) 可用性与频道规模...")
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(probe_live_source, c): c for c in LIVE_CANDIDATES}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            tag = f"✅ 存活 ({res['latency_ms']}ms | {res['channel_count']}个频道)" if res["alive"] else "⚠️ 暂不可达"
            print(f"[{res['name']}] {tag} -> {res['url']}")

    # 存活优先，按响应延迟升序排序
    results.sort(key=lambda x: (0 if x["alive"] else 1, x["latency_ms"]))

    # 将最优存活直播源合并/更新至仓库内建的 live_tv.txt（若全部暂不可达则保留仓库内已有快照）
    alive_with_txt = [r for r in results if r["alive"] and r.get("normalized_txt")]
    if alive_with_txt:
        # 选取综合质量最优的直播源写入本地快照（最多保留前 2500 行防止体积膨胀）
        best_live = alive_with_txt[0]
        lines = best_live["normalized_txt"].splitlines()[:2500]
        header_banner = (
            f"# TVBox 自动巡检自愈直播源快照 (来源: {best_live['name']} | 频道数: {best_live['channel_count']})\n"
        )
        with open(live_txt_path, "w", encoding="utf-8") as f:
            f.write(header_banner + "\n".join(lines) + "\n")
        print(f"✨ 已自动更新仓库本地直播源快照: {live_txt_path} ({len(lines)} 行)")
    else:
        print(f"ℹ️ 外部直播源本次探测未返回新数据，保留仓库现有 {live_txt_path} 快照兜底。")

    return results


def build_lives_entries(live_results, mirror_prefix=None, raw_base=None):
    """
    构建写入 tvbox_config.json / tvbox_mirror.json 的 `lives` 数组：
    - 第 1 条固定为仓库内建自愈直播源（标准版用 `./live_tv.txt`，镜像版用 `mirror_prefix/raw_base/live_tv.txt`）
    - 后续挂载探测存活的远程精选直播源作为一键切换备用源
    """
    if mirror_prefix and raw_base:
        local_live_url = f"{mirror_prefix}/{raw_base}/live_tv.txt"
    else:
        local_live_url = "./live_tv.txt"

    lives_list = [
        {
            "name": "🏠 仓库自愈聚合直播 (央视/卫视/高清主线)",
            "type": 0,
            "url": local_live_url,
            "playerType": 1,
            "ua": "okhttp/3.15",
            "epg": DEFAULT_EPG_URL,
            "logo": DEFAULT_LOGO_URL
        }
    ]

    for item in live_results:
        raw_u = item["url"]
        if mirror_prefix and "raw.githubusercontent.com" in raw_u and not raw_u.startswith(mirror_prefix):
            out_u = f"{mirror_prefix}/{raw_u}"
        else:
            out_u = raw_u

        lives_list.append({
            "name": item["name"],
            "type": 0,
            "url": out_u,
            "playerType": 1,
            "ua": item.get("ua", "okhttp/3.15"),
            "epg": DEFAULT_EPG_URL,
            "logo": DEFAULT_LOGO_URL
        })

    return lives_list


def resolve_runtime_options():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    mirror_prefix = os.environ.get("TVBOX_MIRROR_PREFIX", DEFAULT_MIRROR_PREFIX).rstrip("/")

    args = sys.argv[1:]
    if "--repo" in args:
        idx = args.index("--repo")
        if idx + 1 < len(args):
            repo = args[idx + 1]
    if "--branch" in args:
        idx = args.index("--branch")
        if idx + 1 < len(args):
            branch = args[idx + 1]
    if "--mirror-prefix" in args:
        idx = args.index("--mirror-prefix")
        if idx + 1 < len(args):
            mirror_prefix = args[idx + 1].rstrip("/")

    raw_base = f"https://raw.githubusercontent.com/{repo}/{branch}" if (repo and "/" in repo) else None
    return raw_base, mirror_prefix


def _normalize_relative_py_api(api_str):
    api_str = str(api_str or "").strip()
    m = re.search(r"(py_[a-zA-Z0-9_]+\.py)$", api_str)
    if m:
        return f"./{m.group(1)}"
    return api_str


def update_files(
    best_results,
    live_results=None,
    config_path="tvbox_config.json",
    mirror_config_path="tvbox_mirror.json",
    spider_path="py_cms_spider.py",
    douban_path="py_douban.py",
    raw_base=None,
    mirror_prefix=DEFAULT_MIRROR_PREFIX
):
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    # 1. 选出综合默认主站 (fastest_site_key) 与短剧专区默认主站 (fastest_duanju_key)
    eligible_alive = [
        (k, v["weighted_score"])
        for k, v in best_results.items()
        if v["alive"] and v.get("eligible_default", True)
    ]
    if not eligible_alive:
        eligible_alive = [(k, v["weighted_score"]) for k, v in best_results.items() if v["alive"]]
    eligible_alive.sort(key=lambda x: x[1])
    fastest_site_key = eligible_alive[0][0] if eligible_alive else "lzi"

    duanju_alive = [
        (k, v["weighted_score"])
        for k, v in best_results.items()
        if v["alive"] and v.get("duanju_strong", False)
    ]
    duanju_alive.sort(key=lambda x: x[1])
    fastest_duanju_key = duanju_alive[0][0] if duanju_alive else fastest_site_key

    config_key_map = {v["config_key"]: v for k, v in best_results.items()}

    spider_sites = []
    cms_sites = []

    for site_entry in config_data.get("sites", []):
        s_key = site_entry.get("key", "")

        if isinstance(site_entry.get("ext"), dict):
            site_entry["ext"] = json.dumps(site_entry["ext"], ensure_ascii=False, separators=(",", ":"))

        if site_entry.get("type") == 3:
            site_entry["api"] = _normalize_relative_py_api(site_entry.get("api", ""))

        if s_key == "py_cms_pro" and isinstance(site_entry.get("ext"), str):
            try:
                ext_obj = json.loads(site_entry["ext"]) if site_entry["ext"] else {}
                ext_obj["default_site"] = fastest_site_key
                site_entry["ext"] = json.dumps(ext_obj, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                pass
            spider_sites.append(site_entry)
        elif s_key == "py_duanju_pro" and isinstance(site_entry.get("ext"), str):
            try:
                ext_obj = json.loads(site_entry["ext"]) if site_entry["ext"] else {}
                ext_obj["default_site"] = fastest_duanju_key
                ext_obj["mode"] = "duanju"
                site_entry["ext"] = json.dumps(ext_obj, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                pass
            spider_sites.append(site_entry)
        elif site_entry.get("type") == 3:
            spider_sites.append(site_entry)
        elif s_key in config_key_map:
            info = config_key_map[s_key]
            site_entry["api"] = info["api"]
            cms_sites.append((info["weighted_score"], site_entry))
        else:
            cms_sites.append((50000, site_entry))

    cms_sites.sort(key=lambda x: x[0])
    config_data["sites"] = spider_sites + [item[1] for item in cms_sites]

    # 2. 更新 lives 电视直播源配置
    if live_results is None:
        live_results = [
            {
                "name": c["name"],
                "url": c["url"],
                "ua": c.get("ua", "okhttp/3.15"),
                "alive": True,
                "latency_ms": 100 + i * 10
            }
            for i, c in enumerate(LIVE_CANDIDATES)
        ]

    config_data["lives"] = build_lives_entries(live_results, mirror_prefix=None, raw_base=None)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 3. 生成国内镜像加速专版 tvbox_mirror.json（自动为 .py 与 live_tv.txt 加上镜像前缀）
    mirror_data = copy.deepcopy(config_data)
    effective_raw = raw_base or "https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main"
    for site_entry in mirror_data.get("sites", []):
        api = str(site_entry.get("api", ""))
        if api.startswith("./") and api.endswith(".py"):
            site_entry["api"] = f"{mirror_prefix}/{effective_raw}/{api[2:]}"

    mirror_data["lives"] = build_lives_entries(live_results, mirror_prefix=mirror_prefix, raw_base=effective_raw)

    with open(mirror_config_path, "w", encoding="utf-8") as f:
        json.dump(mirror_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 4. 同步更新 py_cms_spider.py 与 py_douban.py 中的 15 站字典 API 地址与默认主站
    for py_path in (spider_path, douban_path):
        if not os.path.exists(py_path):
            continue
        with open(py_path, "r", encoding="utf-8") as f:
            spider_code = f.read()

        for site_key, info in best_results.items():
            pattern = re.compile(
                rf'("{re.escape(site_key)}"\s*:\s*\{{[^}}]*?"api"\s*:\s*)"[^"]+"'
            )
            spider_code = pattern.sub(rf'\1"{info["api"]}"', spider_code)

        spider_code = re.sub(
            r'(self\.default_site\s*=\s*)"[^"]+"',
            rf'\1"{fastest_site_key}"',
            spider_code,
            count=1
        )

        with open(py_path, "w", encoding="utf-8") as f:
            f.write(spider_code)

    print(
        f"\n✨ 配置文件、直播源与 Spider 脚本已全部同步更新！\n"
        f"   - 综合最优主站: {fastest_site_key} | 短剧专区最优主站: {fastest_duanju_key}\n"
        f"   - 标准相对路径配置: {config_path}\n"
        f"   - 国内镜像加速配置: {mirror_config_path}"
    )


if __name__ == "__main__":
    print("🚀 开始执行 TVBox 15站点播 + 短剧专区 + 电视直播源全自动探活...")
    cms_results = resolve_best_apis()
    live_probe_results = resolve_best_lives("live_tv.txt")
    raw_base_url, mirror_pfx = resolve_runtime_options()
    update_files(
        cms_results,
        live_results=live_probe_results,
        raw_base=raw_base_url,
        mirror_prefix=mirror_pfx
    )
