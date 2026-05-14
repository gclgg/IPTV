import subprocess
import json
import asyncio
import aiohttp
import re
import os
import random
from collections import defaultdict
from datetime import datetime

# --- 配置参数 ---
CONCURRENT_CHECKS = 30
FAST_CHECK_TIMEOUT = 5
MIN_BITRATE = 200
OUTPUT_FILE = "live.m3u"
INPUT_SOURCE = "live.txt"

# 酒店源配置（已更换为新地址）
HOTEL_SOURCE_URL = "https://itv.gcl.de5.net/sub?950428=txt"
HOTEL_MAIN_GROUP = "酒店源"

# iptv-api 源配置（新增）
IPTV_API_SOURCE_URL = "https://raw.githubusercontent.com/gclgg/iptv-api/refs/heads/master/output/result.m3u"
IPTV_API_MAIN_GROUP = "iptv-api"

# 你的Logo仓库配置
LOGO_REPO_OWNER = "gclgg"
LOGO_REPO_NAME = "live"
LOGO_PATH_IN_REPO = "tv"
LOGO_BASE_URL = f"https://raw.githubusercontent.com/{LOGO_REPO_OWNER}/{LOGO_REPO_NAME}/main/{LOGO_PATH_IN_REPO}"

# 分组名称映射
GROUP_MAPPING = {
    "央视频道": "央    视",
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.36',
]

EPG_URLS = [
    "http://epg.112114.xyz/pp.xml",
    "https://epg.112114.free.hr/pp.xml",
]

# 全局logo库
LOGO_DATABASE = {}

# 通用频道Logo库
COMMON_LOGOS = {
    # 央视系列
    "CCTV1": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV1.png",
    "CCTV2": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV2.png",
    "CCTV3": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV3.png",
    "CCTV4": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV4.png",
    "CCTV5": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV5.png",
    "CCTV5+": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV5Plus.png",
    "CCTV6": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV6.png",
    "CCTV7": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV7.png",
    "CCTV8": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV8.png",
    "CCTV9": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV9.png",
    "CCTV10": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV10.png",
    "CCTV11": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV11.png",
    "CCTV12": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV12.png",
    "CCTV13": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV13.png",
    "CCTV14": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV14.png",
    "CCTV15": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV15.png",
    "CCTV16": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV16.png",
    "CCTV17": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/CCTV17.png",
    # 凤凰系列
    "凤凰卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Phoenix.png",
    "凤凰卫视中文台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixChinese.png",
    "凤凰卫视资讯台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixInfo.png",
    "凤凰卫视香港台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixHK.png",
    "凤凰卫视电影台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixMovies.png",
    # 卫视频道
    "湖南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hunan.png",
    "浙江卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Zhejiang.png",
    "江苏卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Jiangsu.png",
    "东方卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DragonTV.png",
    "北京卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Beijing.png",
    "广东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Guangdong.png",
    "深圳卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Shenzhen.png",
    "湖北卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hubei.png",
    "安徽卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Anhui.png",
    "山东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Shandong.png",
    "天津卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Tianjin.png",
    "重庆卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Chongqing.png",
    "四川卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Sichuan.png",
    "河南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Henan.png",
    "河北卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hebei.png",
    # 数字频道
    "求索纪录": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Discovery.png",
    "求索科学": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DiscoveryScience.png",
    "求索动物": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DiscoveryAnimal.png",
    "全纪实": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Documentary.png",
    "生活时尚": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Lifestyle.png",
}

def clean_group_name(group_name):
    """清理分组名称，去掉逗号"""
    return re.sub(r',', '', group_name).strip()

async def fetch_my_logo_list():
    """从你的GitHub仓库获取Logo文件列表"""
    print(f"\n📡 正在从你的仓库拉取Logo列表: {LOGO_BASE_URL}")
    api_url = f"https://api.github.com/repos/{LOGO_REPO_OWNER}/{LOGO_REPO_NAME}/contents/{LOGO_PATH_IN_REPO}"
    my_logos = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status != 200:
                    print(f"⚠️ 无法通过API获取Logo列表 (HTTP {resp.status})，将使用备用logo库")
                    return my_logos
                
                files = await resp.json()
                png_files = [f for f in files if f['name'].lower().endswith('.png')]
                
                for file_info in png_files:
                    channel_name = file_info['name'][:-4]
                    logo_url = f"{LOGO_BASE_URL}/{file_info['name']}"
                    my_logos[channel_name] = logo_url
                
                print(f"✅ 成功获取 {len(my_logos)} 个来自你仓库的Logo")
                sample_items = list(my_logos.items())[:5]
                print(f"   示例: {sample_items}")
                
    except Exception as e:
        print(f"⚠️ 拉取你的Logo列表时出错: {e}")
    
    return my_logos

async def build_comprehensive_logo_database(m3u_file):
    """建立完整的logo数据库"""
    global LOGO_DATABASE
    LOGO_DATABASE = {}
    
    # 1. 从你的GitHub仓库获取
    my_logos = await fetch_my_logo_list()
    LOGO_DATABASE.update(my_logos)
    print(f"📦 从你的仓库加载 {len(my_logos)} 个logo")
    
    # 2. 从本地 M3U 文件提取
    if os.path.exists(m3u_file):
        try:
            with open(m3u_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            local_count = 0
            for line in lines:
                if line.startswith('#EXTINF'):
                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    name_match = re.search(r',([^,]+)$', line)
                    if logo_match and name_match:
                        channel_name = name_match.group(1).strip()
                        if channel_name not in LOGO_DATABASE:
                            LOGO_DATABASE[channel_name] = logo_match.group(1)
                            local_count += 1
            print(f"📦 从本地 M3U 补充 {local_count} 个logo")
        except Exception as e:
            print(f"⚠️ 从本地M3U提取logo失败: {e}")
    
    # 3. 从通用库补充
    common_added = 0
    for name, url in COMMON_LOGOS.items():
        if name not in LOGO_DATABASE:
            LOGO_DATABASE[name] = url
            common_added += 1
    print(f"📦 从通用库补充 {common_added} 个logo")
    print(f"✅ 最终Logo数据库共 {len(LOGO_DATABASE)} 条记录")

def get_logo(channel_name):
    """获取频道的logo"""
    return LOGO_DATABASE.get(channel_name, "")

def parse_txt_file(filename, current_time):
    """解析本地直播源 TXT 文件"""
    channels_by_group = defaultdict(list)
    current_group = "未分组"
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith('#genre#'):
                current_group = clean_group_name(line[:-7].strip())
                continue
            if ',' in line:
                parts = line.split(',', 1)
                channel_name = parts[0].strip()
                full_url = parts[1].strip()
                clean_url = re.sub(r'\$.*$', '', full_url)
                logo_url = get_logo(channel_name)
                
                # 处理公告分组：只保留一个"更新时间"子分组
                if current_group == '公告':
                    channel_name = f"更新时间 {current_time}"
                
                channels_by_group[current_group].append({
                    'name': channel_name,
                    'full_url': full_url,
                    'clean_url': clean_url,
                    'logo': logo_url,
                    'group': current_group,
                    'is_announcement': current_group == '公告'
                })
    
    return dict(channels_by_group)

async def fetch_hotel_source():
    """拉取酒店源（新地址，TXT格式）"""
    print(f"\n🏨 正在拉取酒店源: {HOTEL_SOURCE_URL}")
    hotel_groups = defaultdict(list)
    hotel_group_order = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HOTEL_SOURCE_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return hotel_groups, hotel_group_order
                
                content = await resp.text()
                
                current_group = None
                lines = content.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.endswith('#genre#'):
                        current_group = clean_group_name(line[:-7].strip())
                        if current_group not in hotel_group_order:
                            hotel_group_order.append(current_group)
                        continue
                    
                    if ',' in line and current_group:
                        parts = line.split(',', 1)
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        logo_url = get_logo(channel_name)
                        
                        hotel_groups[current_group].append({
                            'name': channel_name,
                            'url': channel_url,
                            'logo': logo_url
                        })
                
                total = sum(len(ch) for ch in hotel_groups.values())
                print(f"✅ 拉取成功，共 {len(hotel_groups)} 个分组，{total} 个频道")
                
                logo_count = sum(1 for group in hotel_groups.values() for ch in group if ch['logo'])
                if logo_count > 0:
                    print(f"   🖼️ 其中 {logo_count} 个频道已有logo")
                
                for group in hotel_group_order:
                    if group in hotel_groups:
                        group_logo_count = sum(1 for ch in hotel_groups[group] if ch['logo'])
                        print(f"   - {group}: {len(hotel_groups[group])} 个频道 ({group_logo_count} 个有logo)")
                
                return hotel_groups, hotel_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return hotel_groups, hotel_group_order

async def fetch_iptv_api_source():
    """拉取 iptv-api 源（M3U8格式）"""
    print(f"\n📡 正在拉取 iptv-api 源: {IPTV_API_SOURCE_URL}")
    iptv_groups = defaultdict(list)
    iptv_group_order = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(IPTV_API_SOURCE_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return iptv_groups, iptv_group_order
                
                content = await resp.text()
                lines = content.strip().split('\n')
                
                current_group = None
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析 M3U 分组信息
                    if line.startswith('#EXTINF'):
                        # 尝试提取 group-title
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            current_group = group_match.group(1).strip()
                            if current_group not in iptv_group_order:
                                iptv_group_order.append(current_group)
                        # 提取频道名
                        name_match = re.search(r',([^,]+)$', line)
                        if name_match:
                            current_name = name_match.group(1).strip()
                        continue
                    
                    # 如果是 URL 行且已有分组和频道名
                    if line and not line.startswith('#') and current_group and current_name:
                        logo_url = get_logo(current_name)
                        iptv_groups[current_group].append({
                            'name': current_name,
                            'url': line,
                            'logo': logo_url
                        })
                        current_name = None
                
                total = sum(len(ch) for ch in iptv_groups.values())
                print(f"✅ 拉取成功，共 {len(iptv_groups)} 个分组，{total} 个频道")
                
                for group in iptv_group_order:
                    if group in iptv_groups:
                        print(f"   - {group}: {len(iptv_groups[group])} 个频道")
                
                return iptv_groups, iptv_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return iptv_groups, iptv_group_order

async def fast_check(session, clean_url):
    """快速 HEAD 检查"""
    try:
        async with session.head(clean_url, timeout=FAST_CHECK_TIMEOUT, allow_redirects=True) as resp:
            is_valid = resp.status in [200, 301, 302, 307, 308]
            if is_valid:
                print(f"  ✅ {resp.status}")
            else:
                print(f"  ❌ {resp.status}")
            return is_valid
    except Exception as e:
        error_type = type(e).__name__
        print(f"  ⚠️ {error_type}")
        return False

async def check_channel(session, channel):
    """检测单个频道"""
    channel_name = channel.get('name', '未知')
    channel_group = channel.get('group', '未分组')
    channel_logo = channel.get('logo', '')
    full_url = channel.get('full_url', '')
    clean_url = channel.get('clean_url', '')
    is_announcement = channel.get('is_announcement', False)
    
    if is_announcement:
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'height': 1080
        }
    
    print(f"检测: {channel_name} - {clean_url[:60]}...")
    
    if clean_url.startswith('rtsp://'):
        print(f"  📹 RTSP流（直接接受）")
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'height': 720
        }
    
    try:
        if await fast_check(session, clean_url):
            return {
                'name': channel_name,
                'group': channel_group,
                'full_url': full_url,
                'logo': channel_logo,
                'valid': True,
                'height': 720
            }
        else:
            return None
    except Exception as e:
        print(f"  ⚠️ 异常但仍接受: {type(e).__name__}")
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'height': 720
        }

async def main():
    import time
    start_time = time.time()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"\n🕐 当前时间: {current_time}")
    
    # 1. 建立logo数据库
    m3u_file = INPUT_SOURCE.replace('.txt', '.m3u')
    await build_comprehensive_logo_database(m3u_file)
    
    # 2. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    
    channels_by_group = parse_txt_file(INPUT_SOURCE, current_time)
    
    # 3. 拉取酒店源
    hotel_groups, hotel_group_order = await fetch_hotel_source()
    
    # 4. 拉取 iptv-api 源
    iptv_groups, iptv_group_order = await fetch_iptv_api_source()
    
    # 5. 分离需要检测的本地频道（排除公告）
    announcement_channel = None
    local_channels_to_check = []
    local_group_order = []
    
    for group, channels in channels_by_group.items():
        if group not in local_group_order:
            local_group_order.append(group)
        for channel in channels:
            if group == '公告':
                if announcement_channel is None:
                    announcement_channel = channel
            else:
                local_channels_to_check.append(channel)
    
    print(f"\n📢 公告: {1 if announcement_channel else 0} 条")
    print(f"📺 需要检测的本地频道: {len(local_channels_to_check)} 个")
    
    # 6. 检测本地频道
    valid_local_channels = []
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False),
        headers={'User-Agent': random.choice(USER_AGENTS)}
    ) as session:
        semaphore = asyncio.Semaphore(CONCURRENT_CHECKS)
        
        async def bounded_check(ch):
            async with semaphore:
                return await check_channel(session, ch)
        
        tasks = [bounded_check(ch) for ch in local_channels_to_check]
        results = await asyncio.gather(*tasks)
    
    valid_local_channels = [r for r in results if r]
    print(f"\n✅ 本地频道检测完成！有效: {len(valid_local_channels)}")
    
    # 7. 按分组整理本地有效源
    local_by_group = defaultdict(list)
    for ch in valid_local_channels:
        local_by_group[ch['group']].append(ch)
    
    # 8. 写入最终的 M3U 文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # 写入 EPG 信息行
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # === 第一部分：公告（只保留一个）===
        if announcement_channel:
            f.write('\n# 分组：公告\n')
            tvg_id = str(abs(hash(announcement_channel['name'])) % 10000)
            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{announcement_channel["name"]}"'
            if announcement_channel.get('logo'):
                extinf += f' tvg-logo="{announcement_channel["logo"]}"'
            extinf += f' group-title="公告",{announcement_channel["name"]}'
            f.write(extinf + '\n')
            f.write(announcement_channel['full_url'] + '\n')
        
        # === 第二部分：本地有效频道 ===
        if local_by_group:
            f.write('\n# ========== 本地源 ==========\n')
            for group in local_group_order:
                if group != '公告' and group in local_by_group and local_by_group[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in local_by_group[group]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['full_url'] + '\n')
        
        # === 第三部分：酒店源 ===
        if hotel_groups and hotel_group_order:
            f.write(f'\n# ========== {HOTEL_MAIN_GROUP} [{current_time}] ==========\n')
            
            for group in hotel_group_order:
                if group in hotel_groups and hotel_groups[group]:
                    display_group = GROUP_MAPPING.get(group, group)
                    
                    f.write(f'\n# 分组：{display_group}\n')
                    for ch in hotel_groups[group]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        
                        extinf += f' group-title="{display_group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
        
        # === 第四部分：iptv-api 源 ===
        if iptv_groups and iptv_group_order:
            f.write(f'\n# ========== {IPTV_API_MAIN_GROUP} [{current_time}] ==========\n')
            
            for group in iptv_group_order:
                if group in iptv_groups and iptv_groups[group]:
                    # iptv-api 源分组不做额外映射，直接使用
                    f.write(f'\n# 分组：{group}\n')
                    for ch in iptv_groups[group]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
    
    # 统计信息
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    hotel_logo_count = sum(1 for group in hotel_groups.values() for ch in group if ch['logo']) if hotel_groups else 0
    total_iptv = sum(len(ch) for ch in iptv_groups.values()) if iptv_groups else 0
    
    elapsed = time.time() - start_time
    
    print(f"\n⏱️ 总耗时: {elapsed:.1f} 秒")
    print(f"🕐 更新时间: {current_time}")
    print(f"\n📊 最终文件统计:")
    print(f"  - 公告: {1 if announcement_channel else 0} 条 (更新时间: {current_time})")
    print(f"  - 本地有效源: {len(valid_local_channels)} 个")
    if hotel_groups:
        print(f"  - {HOTEL_MAIN_GROUP}: {total_hotel} 个频道，{len(hotel_groups)} 个分组")
        print(f"      其中有 {hotel_logo_count} 个频道已添加logo")
        for group in hotel_group_order:
            if group in hotel_groups:
                display_group = GROUP_MAPPING.get(group, group)
                group_logo_count = sum(1 for ch in hotel_groups[group] if ch['logo'])
                print(f"      {display_group}: {len(hotel_groups[group])} 个频道 ({group_logo_count} 个有logo)")
    if iptv_groups:
        print(f"  - {IPTV_API_MAIN_GROUP}: {total_iptv} 个频道，{len(iptv_groups)} 个分组")
        for group in iptv_group_order:
            if group in iptv_groups:
                print(f"      {group}: {len(iptv_groups[group])} 个频道")
    print(f"  - 总计: {len(valid_local_channels) + total_hotel + total_iptv + (1 if announcement_channel else 0)} 个源")

if __name__ == "__main__":
    asyncio.run(main())
