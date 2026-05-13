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
        updated_local = updated_utc.replace(hour=(updated_utc.hour + 8) % 24)
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
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.splitlines()
        current_category = None
        current_name = None
        is_m3u = any("#EXTINF" in line for line in lines[:15])
        source_type = "m3u" if is_m3u else "txt"
        logging.info(f"url: {url} 获取成功，判断为{source_type}格式")

        if is_m3u:
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    group_match = re.search(r'group-title="([^"]+)"', line)
                    name_match = re.search(r',([^,]+)$', line)
                    if group_match:
                        current_category = group_match.group(1).strip()
                        if current_category not in channels:
                            channels[current_category] = []
                    if name_match:
                        current_name = name_match.group(1).strip()
                elif line and not line.startswith("#") and current_category and current_name:
                    if line.startswith("http"):
                        channels[current_category].append((current_name, line.strip()))
                    current_name = None
        else:
            for line in lines:
                line = line.strip()
                if "#genre#" in line:
                    current_category = line.split(",")[0].strip()
                    channels[current_category] = []
                elif current_category and "," in line:
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

# ----------- 生成 live.txt（全部写入，不跳过任何分组） -----------
def updateChannelUrlsM3U(channels, template_channels):
    written_urls = set()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open("live.txt", "w", encoding="utf-8") as f_txt:
        # 写入公告分组
        f_txt.write(f"公   告,#genre#\n")
        
        # 获取公告URL
        announcement_url = "https://vdse.bdstatic.com//a499dfbec34060ce0f380ea789446f07.mp4"
        
        # 写入公告（不带时间戳，时间戳由 validator.py 添加）
        f_txt.write(f"更新时间,{announcement_url}\n\n")
        
        # 写入所有匹配到的频道（不跳过任何分组）
        for category, ch_dict in channels.items():
            f_txt.write(f"{category},#genre#\n")
            for ch_name, urls in ch_dict.items():
                # 去重、过滤、排序
                urls = list(OrderedDict.fromkeys(urls))
                urls = [u for u in urls if u and u not in written_urls and not any(b in u for b in config.url_blacklist)]
                urls.sort(key=lambda u: not is_ipv6(u) if config.ip_version_priority == "ipv6" else is_ipv6(u))
                
                max_urls = getattr(config, 'max_urls_per_channel', 10)
                for idx, url in enumerate(urls[:max_urls], 1):
                    suffix = f"$LR•IPV6『线路{idx}』" if is_ipv6(url) else f"$LR•IPV4『线路{idx}』"
                    base_url = url.split('$')[0]
                    final_url = f"{base_url}{suffix}"
                    f_txt.write(f"{ch_name},{final_url}\n")
                    written_urls.add(url)
            f_txt.write("\n")
    
    # 统计
    total_categories = len(channels)
    total_channels = sum(len(ch_dict) for ch_dict in channels.values())
    logging.info(f"✅ live.txt 生成完成，共写入 {total_categories} 个分组，{total_channels} 个频道")

# ----------- 入口 -----------
if __name__ == "__main__":
    logging.info("开始处理 IPTV 直播源...")
    template_file = "demo.txt"
    channels, template_channels = filter_source_urls(template_file)
    
    # 打印所有匹配到的分组，方便调试
    logging.info(f"匹配到的所有分组: {list(channels.keys())}")
    
    updateChannelUrlsM3U(channels, template_channels)
    logging.info("IPTV 直播源处理完成 ✅")
