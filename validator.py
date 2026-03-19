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

# 酒店源配置
HOTEL_SOURCE_URL = "https://raw.githubusercontent.com/gclgg/zubo/main/itvlist.txt"
HOTEL_MAIN_GROUP = "酒店源"  # 酒店源主分组名称

# 分组名称映射（将酒店源中容易混淆的分组改名）
GROUP_MAPPING = {
    "央视频道": "央视",
    # 如果有其他需要改名的分组，可以在这里添加
    # "卫视频道": "卫视",
    # "数字频道": "数字"
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.36',
]

EPG_URLS = [
    "http://epg.112114.xyz/pp.xml",
    "https://epg.112114.free.hr/pp.xml",
]

def clean_group_name(group_name):
    """清理分组名称，去掉逗号"""
    return re.sub(r',', '', group_name).strip()

def extract_logo_from_m3u(channel_name, m3u_file):
    """从原始 M3U 文件中提取指定频道的 logo URL"""
    if not os.path.exists(m3u_file):
        return ""
    
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if line.startswith('#EXTINF') and f',{channel_name}' in line:
                # 查找 tvg-logo 属性
                logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                if logo_match:
                    return logo_match.group(1)
    except:
        pass
    return ""

def parse_txt_file(filename):
    """解析本地直播源 TXT 文件"""
    channels_by_group = defaultdict(list)
    current_group = "未分组"
    m3u_file = filename.replace('.txt', '.m3u')
    
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
                logo_url = extract_logo_from_m3u(channel_name, m3u_file)
                
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
    """拉取酒店源，完整保留原始结构，并尝试获取logo"""
    print(f"\n🏨 正在拉取酒店源: {HOTEL_SOURCE_URL}")
    hotel_groups = defaultdict(list)
    hotel_group_order = []
    
    # 尝试获取本地已有的酒店源 M3U 文件（用于提取logo）
    hotel_m3u_file = "hotel_temp.m3u"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HOTEL_SOURCE_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return hotel_groups, hotel_group_order
                
                content = await resp.text()
                
                # 解析酒店源的完整内容
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
                        
                        # 尝试从本地已有的 M3U 中提取 logo（如果有的话）
                        # 这里暂时没有 logo，后续可以从其他地方获取
                        logo_url = ""
                        
                        hotel_groups[current_group].append({
                            'name': channel_name,
                            'url': channel_url,
                            'logo': logo_url
                        })
                
                # 统计
                total = sum(len(ch) for ch in hotel_groups.values())
                print(f"✅ 拉取成功，共 {len(hotel_groups)} 个分组，{total} 个频道")
                for group in hotel_group_order:
                    if group in hotel_groups:
                        print(f"   - {group}: {len(hotel_groups[group])} 个频道")
                
                return hotel_groups, hotel_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return hotel_groups, hotel_group_order

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
    
    # 1. 拉取酒店源（保留完整结构和原始顺序）
    hotel_groups, hotel_group_order = await fetch_hotel_source()
    
    # 2. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    
    channels_by_group = parse_txt_file(INPUT_SOURCE)
    
    # 3. 分离公告和需要检测的本地频道
    announcement = None
    local_channels_to_check = []
    local_group_order = []  # 记录本地分组的原始顺序
    
    for group, channels in channels_by_group.items():
        if group not in local_group_order:
            local_group_order.append(group)
        for channel in channels:
            if group == '公告' and '更新日期' in channel['name']:
                announcement = channel
            elif group != '公告':
                local_channels_to_check.append(channel)
    
    print(f"\n📢 公告: 1 条")
    print(f"📺 需要检测的本地频道: {len(local_channels_to_check)} 个")
    
    # 4. 检测本地频道
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
    
    # 5. 按分组整理本地有效源
    local_by_group = defaultdict(list)
    for ch in valid_local_channels:
        local_by_group[ch['group']].append(ch)
    
    # 6. 写入最终的 M3U 文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # 写入 EPG 信息行
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # === 第一部分：公告 ===
        if announcement:
            f.write('\n# 分组：公告\n')
            announcement_name = f"更新日期 {current_time}"
            tvg_id = str(abs(hash(announcement_name)) % 10000)
            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{announcement_name}"'
            if announcement.get('logo'):
                extinf += f' tvg-logo="{announcement["logo"]}"'
            extinf += f' group-title="公告",{announcement_name}'
            f.write(extinf + '\n')
            f.write(announcement['full_url'] + '\n')
        
        # === 第二部分：本地有效频道（按原始顺序） ===
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
        
        # === 第三部分：酒店源（完整保留原始结构） ===
        if hotel_groups and hotel_group_order:
            # 酒店源大分组标题 - 修正为"酒店源"
            f.write(f'\n# ========== {HOTEL_MAIN_GROUP} [{current_time}] ==========\n')
            
            # 按原始顺序写入酒店源的各个分组，但修改分组名称以区分本地源
            for group in hotel_group_order:
                if group in hotel_groups and hotel_groups[group]:
                    # 分组名称映射：将容易混淆的名称改为更容易区分的名称
                    display_group = GROUP_MAPPING.get(group, group)  # 如果有映射就用映射后的名称，否则用原名
                    
                    f.write(f'\n# 分组：{display_group}\n')
                    for ch in hotel_groups[group]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        
                        # 如果有logo就加上
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        
                        extinf += f' group-title="{display_group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
    
    # 统计信息
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    elapsed = time.time() - start_time
    
    print(f"\n⏱️ 总耗时: {elapsed:.1f} 秒")
    print(f"🕐 更新时间: {current_time}")
    print(f"\n📊 最终文件统计:")
    print(f"  - 公告: 1 条")
    print(f"  - 本地有效源: {len(valid_local_channels)} 个")
    if hotel_groups:
        print(f"  - {HOTEL_MAIN_GROUP}: {total_hotel} 个频道，{len(hotel_groups)} 个分组")
        for group in hotel_group_order:
            if group in hotel_groups:
                display_group = GROUP_MAPPING.get(group, group)
                print(f"      {display_group}: {len(hotel_groups[group])} 个")
    print(f"  - 总计: {len(valid_local_channels) + total_hotel} 个源")

if __name__ == "__main__":
    asyncio.run(main())
