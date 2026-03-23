import subprocess
import json
import asyncio
import aiohttp
import re
import os
import random
import time
from collections import defaultdict
from datetime import datetime

# --- 配置参数 ---
CONCURRENT_CHECKS = 5           # 降低并发，避免被源站屏蔽
CONNECT_TIMEOUT = 8              # 连接超时（秒）
PLAY_DURATION = 8                # 模拟播放时长（秒）
MIN_SPEED = 200                  # 最低速度要求（KB/s）
MIN_CHUNKS = 5                   # 最少需要收到的数据块数
OUTPUT_FILE = "live.m3u"
INPUT_SOURCE = "live.txt"

# 酒店源配置（不检测，直接合并）
HOTEL_SOURCE_URL = "https://raw.githubusercontent.com/gclgg/zubo/main/itvlist.txt"
HOTEL_MAIN_GROUP = "酒店源"

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

# 通用频道Logo库（保持原有内容）
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
    return re.sub(r',', '', group_name).strip()

async def fetch_my_logo_list():
    print(f"\n📡 正在从你的仓库拉取Logo列表: {LOGO_BASE_URL}")
    api_url = f"https://api.github.com/repos/{LOGO_REPO_OWNER}/{LOGO_REPO_NAME}/contents/{LOGO_PATH_IN_REPO}"
    my_logos = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status != 200:
                    return my_logos
                files = await resp.json()
                png_files = [f for f in files if f['name'].lower().endswith('.png')]
                for file_info in png_files:
                    channel_name = file_info['name'][:-4]
                    logo_url = f"{LOGO_BASE_URL}/{file_info['name']}"
                    my_logos[channel_name] = logo_url
                print(f"✅ 成功获取 {len(my_logos)} 个Logo")
    except Exception as e:
        print(f"⚠️ 拉取Logo列表出错: {e}")
    return my_logos

async def build_comprehensive_logo_database(m3u_file):
    global LOGO_DATABASE
    LOGO_DATABASE = {}
    my_logos = await fetch_my_logo_list()
    LOGO_DATABASE.update(my_logos)
    if os.path.exists(m3u_file):
        try:
            with open(m3u_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith('#EXTINF'):
                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    name_match = re.search(r',([^,]+)$', line)
                    if logo_match and name_match:
                        channel_name = name_match.group(1).strip()
                        if channel_name not in LOGO_DATABASE:
                            LOGO_DATABASE[channel_name] = logo_match.group(1)
        except:
            pass
    for name, url in COMMON_LOGOS.items():
        if name not in LOGO_DATABASE:
            LOGO_DATABASE[name] = url
    print(f"✅ Logo数据库共 {len(LOGO_DATABASE)} 条记录")

def get_logo(channel_name):
    return LOGO_DATABASE.get(channel_name, "")

def parse_txt_file(filename, current_time):
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
    """拉取酒店源（不检测，直接合并）"""
    print(f"\n🏨 正在拉取酒店源: {HOTEL_SOURCE_URL}")
    hotel_groups = defaultdict(list)
    hotel_group_order = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HOTEL_SOURCE_URL, timeout=30) as resp:
                if resp.status != 200:
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
                return hotel_groups, hotel_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return hotel_groups, hotel_group_order

async def simulate_play(session, url):
    """模拟播放检测，返回(是否可用, 质量分, 速度)"""
    start_time = time.time()
    chunks = []
    
    try:
        async with session.get(url, timeout=CONNECT_TIMEOUT) as resp:
            if resp.status not in [200, 206]:
                return False, 0, 0
            
            # 模拟播放，持续接收数据
            play_start = time.time()
            chunk_count = 0
            async for chunk in resp.content.iter_chunks():
                if chunk[0]:
                    chunks.append(len(chunk[0]))
                    chunk_count += 1
                    
                    # 计算实时速度
                    elapsed = time.time() - play_start
                    if elapsed >= 1 and chunks:
                        total_bytes = sum(chunks)
                        speed = total_bytes / elapsed / 1024
                        
                        # 如果速度太低，提前退出
                        if elapsed >= 3 and speed < MIN_SPEED / 2:
                            return False, 0, speed
                    
                    # 达到播放时长，退出
                    if time.time() - play_start >= PLAY_DURATION:
                        break
            
            total_time = time.time() - start_time
            total_bytes = sum(chunks) if chunks else 0
            avg_speed = total_bytes / PLAY_DURATION / 1024 if total_bytes > 0 else 0
            chunk_count = len(chunks)
            
            if chunk_count < MIN_CHUNKS:
                return False, 0, avg_speed
            if avg_speed < MIN_SPEED:
                return False, 0, avg_speed
            
            # 质量分 = 速度分 + 稳定性分
            speed_score = min(500, int(avg_speed * 2))
            stability_score = min(300, chunk_count * 10)
            quality_score = speed_score + stability_score
            
            return True, quality_score, avg_speed
            
    except asyncio.TimeoutError:
        return False, 0, 0
    except Exception:
        return False, 0, 0

async def check_channel(session, channel):
    """检测单个本地频道（使用模拟播放）"""
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
            'quality_score': 1000,
            'speed': 0
        }
    
    # RTSP 流直接接受（难以检测）
    if clean_url.startswith('rtsp://'):
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'quality_score': 500,
            'speed': 0
        }
    
    valid, quality_score, speed = await simulate_play(session, clean_url)
    
    if valid:
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'quality_score': quality_score,
            'speed': speed
        }
    else:
        return None

async def main():
    start_time = time.time()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n🕐 当前时间: {current_time}")
    print(f"⚙️ 检测参数: 播放时长={PLAY_DURATION}秒, 最低速度={MIN_SPEED}KB/s")
    
    # 1. 建立logo数据库
    m3u_file = INPUT_SOURCE.replace('.txt', '.m3u')
    await build_comprehensive_logo_database(m3u_file)
    
    # 2. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    channels_by_group = parse_txt_file(INPUT_SOURCE, current_time)
    
    # 3. 拉取酒店源（不检测）
    hotel_groups, hotel_group_order = await fetch_hotel_source()
    
    # 4. 分离公告和本地频道
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
    
    # 5. 检测本地频道
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
    
    # 6. 按分组整理并排序
    local_by_group = defaultdict(list)
    for ch in valid_local_channels:
        local_by_group[ch['group']].append(ch)
    for group in local_by_group:
        local_by_group[group].sort(key=lambda x: -x['quality_score'])
    
    # 7. 写入M3U文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # 公告
        if announcement_channel:
            f.write('\n# 分组：公告\n')
            tvg_id = str(abs(hash(announcement_channel['name'])) % 10000)
            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{announcement_channel["name"]}"'
            if announcement_channel.get('logo'):
                extinf += f' tvg-logo="{announcement_channel["logo"]}"'
            extinf += f' group-title="公告",{announcement_channel["name"]}'
            f.write(extinf + '\n')
            f.write(announcement_channel['full_url'] + '\n')
        
        # 本地源
        if local_by_group:
            f.write('\n# ========== 本地源 ==========\n')
            for group in local_group_order:
                if group != '公告' and group in local_by_group and local_by_group[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for idx, ch in enumerate(local_by_group[group], 1):
                        # 添加线路编号
                        clean_base = re.sub(r'\$.*$', '', ch['full_url'])
                        numbered_url = f"{clean_base}『线路{idx}』"
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(numbered_url + '\n')
                        # 添加质量注释
                        if ch.get('speed', 0) > 0:
                            f.write(f"# 质量: {ch['quality_score']}分, 速度: {ch['speed']:.1f}KB/s\n")
        
        # 酒店源（直接合并）
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
    
    # 统计
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    elapsed = time.time() - start_time
    print(f"\n⏱️ 总耗时: {elapsed:.1f} 秒")
    print(f"📊 最终统计: 本地有效 {len(valid_local_channels)} 个, 酒店源 {total_hotel} 个")

if __name__ == "__main__":
    asyncio.run(main())
