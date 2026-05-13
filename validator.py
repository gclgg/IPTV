import re
import os
import aiohttp
import asyncio
from collections import defaultdict
from datetime import datetime

OUTPUT_FILE = "live.m3u"
INPUT_SOURCE = "live.txt"

# 酒店源配置
HOTEL_SOURCE_URL = "https://itv.gcl.de5.net/sub?950428=m3u"
HOTEL_MAIN_GROUP = "酒店源"

# iptv-api 源配置
IPTV_API_URL = "https://raw.githubusercontent.com/gclgg/iptv-api/refs/heads/master/output/result.m3u"
IPTV_API_MAIN_GROUP = "iptv-api"

EPG_URLS = [
    "https://epg.gcl.de5.net/epg/51zmt.xml",
    "https://epg.gcl.de5.net/epg/51zmt_df.xml",
    "https://epg.gcl.de5.net/epg/51zmt_cc.xml",
    "https://epg.gcl.de5.net/epg/epg_pw.xml",
    "http://epg.51zmt.top:8000/e.xml",
]

# Logo库
COMMON_LOGOS = {
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
    "凤凰卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Phoenix.png",
    "凤凰卫视中文台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixChinese.png",
    "凤凰卫视资讯台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixInfo.png",
    "湖南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hunan.png",
    "浙江卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Zhejiang.png",
    "江苏卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Jiangsu.png",
    "东方卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DragonTV.png",
    "北京卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Beijing.png",
    "广东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Guangdong.png",
    "深圳卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Shenzhen.png",
}

def get_logo(channel_name):
    if channel_name in COMMON_LOGOS:
        return COMMON_LOGOS[channel_name]
    for key in COMMON_LOGOS:
        if key in channel_name or channel_name in key:
            return COMMON_LOGOS[key]
    return ""

def parse_txt_file(filename, current_time):
    """读取 live.txt 中的本地源"""
    channels_by_group = defaultdict(list)
    current_group = "未分组"
    
    if not os.path.exists(filename):
        return channels_by_group
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith('#genre#'):
                current_group = line[:-7].strip()
                continue
            if ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    channel_name = parts[0].strip()
                    full_url = parts[1].strip()
                    logo_url = get_logo(channel_name)
                    channels_by_group[current_group].append({
                        'name': channel_name,
                        'url': full_url,
                        'logo': logo_url
                    })
    return dict(channels_by_group)

async def fetch_m3u_source(url, source_name):
    """通用M3U拉取函数"""
    print(f"\n📡 正在拉取 {source_name}: {url}")
    groups = defaultdict(list)
    group_order = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ {source_name} 拉取失败: HTTP {resp.status}")
                    return groups, group_order
                
                content = await resp.text()
                lines = content.strip().split('\n')
                
                current_group = ""
                current_name = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('#EXTINF'):
                        # 提取 group-title
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            current_group = group_match.group(1)
                            if current_group and current_group not in group_order:
                                group_order.append(current_group)
                        
                        # 提取频道名称
                        if ',' in line:
                            current_name = line.split(',')[-1].strip()
                        continue
                    
                    # 匹配URL行
                    if line and not line.startswith('#') and current_name and current_group:
                        if line.startswith('http'):
                            logo_url = get_logo(current_name)
                            groups[current_group].append({
                                'name': current_name,
                                'url': line,
                                'logo': logo_url
                            })
                            current_name = ""
                
                total = sum(len(groups[g]) for g in groups)
                if total > 0:
                    print(f"✅ {source_name} 拉取成功: {len(groups)} 个分组, {total} 个频道")
                else:
                    print(f"⚠️ {source_name} 未能解析到任何频道")
                
                return groups, group_order
                
    except Exception as e:
        print(f"❌ {source_name} 拉取失败: {e}")
        return groups, group_order

async def main():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*50}")
    print(f"开始合并直播源 - {current_time}")
    print(f"{'='*50}\n")
    
    # 1. 读取本地源（从 live.txt）
    local_groups = parse_txt_file(INPUT_SOURCE, current_time)
    local_count = sum(len(local_groups[g]) for g in local_groups)
    print(f"📁 本地源: {len(local_groups)} 个分组, {local_count} 个频道")
    
    # 2. 拉取酒店源
    hotel_groups, hotel_order = await fetch_m3u_source(HOTEL_SOURCE_URL, "酒店源")
    
    # 3. 拉取 iptv-api 源
    iptv_groups, iptv_order = await fetch_m3u_source(IPTV_API_URL, "iptv-api源")
    
    # 4. 写入最终的 M3U 文件
    print(f"\n📝 正在写入 {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # ========== 1. 本地源 ==========
        if local_groups:
            f.write(f'\n# ========== 本地源 ==========\n')
            for group, channels in local_groups.items():
                f.write(f'\n# 分组：{group}\n')
                for ch in channels:
                    extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                    if ch.get('logo'):
                        extinf += f' tvg-logo="{ch["logo"]}"'
                    extinf += f' group-title="{group}",{ch["name"]}'
                    f.write(extinf + '\n')
                    f.write(ch['url'] + '\n')
        
        # ========== 2. 酒店源（带时间戳） ==========
        if hotel_groups:
            f.write(f'\n# ========== 酒店源 [{current_time}] ==========\n')
            for group in hotel_order:
                if group in hotel_groups and hotel_groups[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in hotel_groups[group]:
                        extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
        
        # ========== 3. iptv-api 源（带时间戳） ==========
        if iptv_groups:
            f.write(f'\n# ========== iptv-api [{current_time}] ==========\n')
            for group in iptv_order:
                if group in iptv_groups and iptv_groups[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in iptv_groups[group]:
                        extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
    
    # 统计
    hotel_count = sum(len(hotel_groups[g]) for g in hotel_groups) if hotel_groups else 0
    iptv_count = sum(len(iptv_groups[g]) for g in iptv_groups) if iptv_groups else 0
    
    print(f"\n{'='*50}")
    print(f"✅ 合并完成！")
    print(f"   - 本地源: {local_count} 个频道")
    print(f"   - 酒店源: {hotel_count} 个频道")
    print(f"   - iptv-api: {iptv_count} 个频道")
    print(f"   - 总计: {local_count + hotel_count + iptv_count} 个频道")
    print(f"   - 输出文件: {OUTPUT_FILE}")
    print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())
