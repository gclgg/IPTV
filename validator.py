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

# 酒店源下面的子分组
HOTEL_SUB_GROUPS = ['央视频道', '卫视频道', '数字频道']

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
    """从原始 M3U 文件中提取 logo"""
    if not os.path.exists(m3u_file):
        return ""
    with open(m3u_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith('#EXTINF') and f',{channel_name}' in line:
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                return logo_match.group(1)
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
                    'is_announcement': current_group == '公告',
                    'source': 'local'  # 标记为本地源
                })
    
    return dict(channels_by_group)

async def fetch_hotel_source():
    """拉取酒店源，保持子分组结构"""
    print(f"\n🏨 正在拉取酒店源: {HOTEL_SOURCE_URL}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HOTEL_SOURCE_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return {}
                
                content = await resp.text()
                hotel_data = defaultdict(list)
                current_group = None
                lines = content.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.endswith('#genre#'):
                        current_group = clean_group_name(line[:-7].strip())
                        continue
                    
                    if ',' in line and current_group:
                        # 只保留需要的子分组
                        if current_group in HOTEL_SUB_GROUPS:
                            parts = line.split(',', 1)
                            channel_name = parts[0].strip()
                            channel_url = parts[1].strip()
                            
                            hotel_data[current_group].append({
                                'name': channel_name,
                                'url': channel_url,
                                'group': current_group,
                                'source': 'hotel'  # 标记为酒店源
                            })
                
                # 统计并显示
                total = sum(len(ch) for ch in hotel_data.values())
                print(f"✅ 拉取成功，{len(hotel_data)} 个子分组，{total} 个频道")
                for group in HOTEL_SUB_GROUPS:
                    if group in hotel_data:
                        print(f"   - {group}: {len(hotel_data[group])} 个频道")
                
                return dict(hotel_data)
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return {}

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
    source = channel.get('source', 'local')
    
    if is_announcement:
        return {
            'name': channel_name,
            'group': channel_group,
            'full_url': full_url,
            'logo': channel_logo,
            'valid': True,
            'height': 1080,
            'source': source
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
            'height': 720,
            'source': source
        }
    
    try:
        if await fast_check(session, clean_url):
            return {
                'name': channel_name,
                'group': channel_group,
                'full_url': full_url,
                'logo': channel_logo,
                'valid': True,
                'height': 720,
                'source': source
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
            'height': 720,
            'source': source
        }

async def main():
    import time
    start_time = time.time()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"\n🕐 当前时间: {current_time}")
    
    # 1. 拉取酒店源（保留子分组结构）
    hotel_data = await fetch_hotel_source()
    
    # 2. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    
    channels_by_group = parse_txt_file(INPUT_SOURCE)
    
    # 3. 分离公告和需要检测的本地频道
    announcement = None
    local_channels_to_check = []
    
    for group, channels in channels_by_group.items():
        for channel in channels:
            if group == '公告' and '更新日期' in channel['name']:
                announcement = channel
                announcement['source'] = 'local'
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
        
        # === 第二部分：本地有效频道 ===
        if local_by_group:
            f.write('\n# ========== 本地源 ==========\n')
            for group, channels in local_by_group.items():
                if channels:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in channels:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['full_url'] + '\n')
        
        # === 第三部分：酒店源 ===
        if hotel_data:
            # 酒店源大分组（带时间戳）
            f.write(f'\n# ========== {HOTEL_MAIN_GROUP} [{current_time}] ==========\n')
            
            # 按顺序写入子分组
            for subgroup in HOTEL_SUB_GROUPS:
                if subgroup in hotel_data and hotel_data[subgroup]:
                    f.write(f'\n# 分组：{subgroup}（{HOTEL_MAIN_GROUP}）\n')
                    for ch in hotel_data[subgroup]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        # 在分组名称中标注酒店源
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}" group-title="{subgroup}（{HOTEL_MAIN_GROUP}）",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
    
    # 统计信息
    total_hotel = sum(len(ch) for ch in hotel_data.values()) if hotel_data else 0
    elapsed = time.time() - start_time
    
    print(f"\n⏱️ 总耗时: {elapsed:.1f} 秒")
    print(f"🕐 更新时间: {current_time}")
    print(f"\n📊 最终文件统计:")
    print(f"  - 公告: 1 条")
    print(f"  - 本地有效源: {len(valid_local_channels)} 个")
    if hotel_data:
        print(f"  - {HOTEL_MAIN_GROUP}: {total_hotel} 个频道，{len(hotel_data)} 个子分组")
        for subgroup in HOTEL_SUB_GROUPS:
            if subgroup in hotel_data:
                print(f"      {subgroup}: {len(hotel_data[subgroup])} 个")
    print(f"  - 总计: {len(valid_local_channels) + total_hotel} 个源")

if __name__ == "__main__":
    asyncio.run(main())
