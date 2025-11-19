import re
import requests
import logging
from collections import OrderedDict
from datetime import datetime
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("function.log", "w", encoding="utf-8"), logging.StreamHandler()]
)

# ----------- 获取 GitHub 更新时间 -----------
def get_github_repo_update_time(owner: str, repo: str) -> str:
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        updated_utc = datetime.strptime(resp.json()["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
        updated_local = updated_utc.replace(hour=(updated_utc.hour + 8) % 24)  # 简单 UTC+8
        return updated_local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"获取 GitHub 更新时间失败: {e}")
        return None

# ----------- 模板解析 -----------
def parse_template(template_file):
    template_channels = OrderedDict()
    current_category = None
    with open(template_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    template_channels[current_category] = []
                elif current_category:
                    channel_name = line.split(",")[0].strip()
                    template_channels[current_category].append(channel_name)
    return template_channels

# ----------- 爬取远程源 -----------
def fetch_channels(url):
    channels = OrderedDict()
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.splitlines()
        current_category = None
        is_m3u = any("#EXTINF" in line for line in lines[:15])
        source_type = "m3u" if is_m3u else "txt"
        logging.info(f"url: {url} 获取成功，判断为{source_type}格式")

        if is_m3u:
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    m = re.search(r'group-title="(.*?)",(.*)', line)
                    if m:
                        current_category = m.group(1).strip()
                        channel_name = m.group(2).strip()
                        if current_category not in channels:
                            channels[current_category] = []
                elif line and not line.startswith("#"):
                    if current_category and channel_name:
                        channels[current_category].append((channel_name, line.strip()))
        else:
            for line in lines:
                line = line.strip()
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    channels[current_category] = []
                elif current_category:
                    m = re.match(r"^(.*?),(.*?)$", line)
                    if m:
                        channels[current_category].append((m.group(1).strip(), m.group(2).strip()))
        if channels:
            logging.info(f"url: {url} 爬取成功✅，包含频道分类: {', '.join(channels.keys())}")
    except requests.RequestException as e:
        logging.error(f"url: {url} 爬取失败❌, Error: {e}")
    return channels

# ----------- 频道匹配 -----------
def match_channels(template_channels, all_channels):
    matched = OrderedDict()
    for category, ch_list in template_channels.items():
        matched[category] = OrderedDict()
        for ch_name in ch_list:
            for online_cat, online_list in all_channels.items():
                for name, url in online_list:
                    if ch_name == name:
                        matched[category].setdefault(ch_name, []).append(url)
    return matched

# ----------- 主过滤流程 -----------
def filter_source_urls(template_file):
    template_channels = parse_template(template_file)
    all_channels = OrderedDict()
    for url in config.source_urls:
        fetched = fetch_channels(url)
        for cat, lst in fetched.items():
            all_channels.setdefault(cat, []).extend(lst)
    return match_channels(template_channels, all_channels), template_channels

# ----------- IPV6 判断 -----------
def is_ipv6(url):
    return re.match(r'^http:\/\/\[[0-9a-fA-F:]+\]', url) is not None

# ----------- 生成 live.m3u & live.txt -----------
def updateChannelUrlsM3U(channels, template_channels):
    written_urls = set()
    current_date = datetime.now().strftime("%Y-%m-%d")

    # 获取仓库更新时间
    repo_time = get_github_repo_update_time("gclgg", "IPTV")
    update_channel_name = f"📦 仓库更新时间 {repo_time}" if repo_time else "📦 仓库更新时间 获取失败"

    for group in config.announcements:
        for entry in group['entries']:
            if entry['name'] is None:
                entry['name'] = current_date

    with open("live.m3u", "w", encoding="utf-8") as f_m3u, open("live.txt", "w", encoding="utf-8") as f_txt:
        # 文件头
        f_m3u.write(f"#EXTM3U x-tvg-url={','.join(f'\"{url}\"' for url in config.epg_urls)}\n")
        f_txt.write(f"# 仓库最后更新时间: {repo_time if repo_time else '获取失败'}\n")

        # 公告分类（先插入“伪频道”）
        f_txt.write("公告,#genre#\n")
        f_m3u.write(f'#EXTINF:-1 tvg-id="0" tvg-name="仓库更新时间" '
                    f'tvg-logo="https://cdn.jsdelivr.net/gh/lr77/IPTV@main/icons/update.png" '
                    f'group-title="公告",{update_channel_name}\n')
        f_m3u.write("https://vdse.bdstatic.com//a499dfbec34060ce0f380ea789446f07.mp4\n")
        f_txt.write(f"{update_channel_name},https://vdse.bdstatic.com//a499dfbec34060ce0f380ea789446f07.mp4\n")

        # 其余公告
        for group in config.announcements:
            f_txt.write(f"{group['channel']},#genre#\n")
            for entry in group['entries']:
                f_m3u.write(f"#EXTINF:-1 tvg-id=\"1\" tvg-name=\"{entry['name']}\" "
                            f"tvg-logo=\"{entry['logo']}\" group-title=\"{group['channel']}\",{entry['name']}\n")
                f_m3u.write(f"{entry['url']}\n")
                f_txt.write(f"{entry['name']},{entry['url']}\n")

        # 普通频道
        for category, ch_list in template_channels.items():
            f_txt.write(f"{category},#genre#\n")
            if category not in channels:
                continue
            for ch_name in ch_list:
                if ch_name not in channels[category]:
                    continue
                urls = sorted(channels[category][ch_name],
                              key=lambda u: not is_ipv6(u) if config.ip_version_priority == "ipv6" else is_ipv6(u))
                filtered = []
                for u in urls:
                    if u and u not in written_urls and not any(b in u for b in config.url_blacklist):
                        filtered.append(u)
                        written_urls.add(u)

                total = len(filtered)
                for idx, url in enumerate(filtered, 1):
                    suffix = f"$LR•IPV6『线路{idx}』" if is_ipv6(url) else f"$LR•IPV4『线路{idx}』"
                    base = url.split('$')[0]
                    new_url = f"{base}{suffix}"
                    f_m3u.write(f"#EXTINF:-1 tvg-id=\"{idx}\" tvg-name=\"{ch_name}\" "
                                f"tvg-logo=\"https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/{ch_name}.png\" "
                                f"group-title=\"{category}\",{ch_name}\n")
                    f_m3u.write(new_url + "\n")
                    f_txt.write(f"{ch_name},{new_url}\n")
            f_txt.write("\n")

# ----------- 入口 -----------
if __name__ == "__main__":
    logging.info("开始处理 IPTV 直播源...")
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    updateChannelUrlsM3U(channels, template_channels)
    logging.info("IPTV 直播源处理完成 ✅")
