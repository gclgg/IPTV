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

# 通用Logo库
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
    "湖南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hunan.png",
    "浙江卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Zhejiang.png",
    "江苏卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Jiangsu.png",
    "东方卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DragonTV.png",
    "北京卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Beijing.png",
    "广东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Guangdong.png",
    "深圳卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Shenzhen.png",
    "凤凰卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Phoenix.png",
    "凤凰卫视中文台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixChinese.png",
    "凤凰卫视资讯台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixInfo.png",
}

def get_logo(channel_name):
    # 直接匹配
    if channel_name in COMMON_LOGOS:
        return COMMON_LOGOS[channel_name]
    # 模糊匹配
    for key in COMMON_LOGOS:
        if channel_name == key or key == channel_name:
            return COMMON_LOGOS[key]
        if channel_name.startswith(key) or key.startswith(channel_name):
            return COMMON_LOGOS[key]
    return ""

def parse_txt_file(filename, current_time):
    """解析 live.txt，只读取公告和本地源"""
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

async def fetch_hotel_source():
    """拉取酒店源"""
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
                lines = content.strip().split('\n')
                
                current_group = "未分组"
                current_name = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('#EXTINF'):
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            current_group = group_match.group(1).strip()
                            if current_group not in hotel_group_order:
                                hotel_group_order.append(current_group)
                        
                        name_match = re.search(r',([^,]+)$', line)
                        if name_match:
                            current_name = name_match.group(1).strip()
                        continue
                    
                    if line and not line.startswith('#') and current_name:
                        logo_url = get_logo(current_name)
                        hotel_groups[current_group].append({
                            'name': current_name,
                            'url': line,
                            'logo': logo_url
                        })
                        current_name = ""
                
                total = sum(len(ch) for ch in hotel_groups.values())
                if total > 0:
                    print(f"✅ 酒店源拉取成功，共 {len(hotel_groups)} 个分组，{total} 个频道")
                    for group in hotel_group_order[:5]:
                        print(f"   - {group}: {len(hotel_groups[group])} 个频道")
                else:
                    print(f"⚠️ 酒店源未解析到频道")
                
                return hotel_groups, hotel_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return hotel_groups, hotel_group_order

async def fetch_iptv_api_source():
    """拉取 iptv-api 源"""
    print(f"\n📡 正在拉取 iptv-api 源: {IPTV_API_URL}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(IPTV_API_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return {}, []
                
                content = await resp.text()
                lines = content.strip().split('\n')
                
                iptv_groups = defaultdict(list)
                iptv_group_order = []
                current_group = "未分组"
                current_name = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('#EXTINF'):
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            current_group = group_match.group(1).strip()
                            if current_group not in iptv_group_order:
                                iptv_group_order.append(current_group)
                        
                        name_match = re.search(r',([^,]+)$', line)
                        if name_match:
                            current_name = name_match.group(1).strip()
                        continue
                    
                    if line and not line.startswith('#') and current_name:
                        logo_url = get_logo(current_name)
                        iptv_groups[current_group].append({
                            'name': current_name,
                            'url': line,
                            'logo': logo_url
                        })
                        current_name = ""
                
                total = sum(len(ch) for ch in iptv_groups.values())
                if total > 0:
                    print(f"✅ iptv-api 拉取成功，共 {len(iptv_groups)} 个分组，{total} 个频道")
                else:
                    print(f"⚠️ iptv-api 未解析到频道")
                
                return iptv_groups, iptv_group_order
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return {}, []

async def main():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n🕐 当前时间: {current_time}")
    print(f"{'='*50}")
    
    # 1. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：{INPUT_SOURCE} 不存在！请先运行 main.py 生成 live.txt")
        return
    channels_by_group = parse_txt_file(INPUT_SOURCE, current_time)
    
    # 2. 拉取酒店源
    hotel_groups, hotel_group_order = await fetch_hotel_source()
    
    # 3. 拉取 iptv-api 源
    iptv_groups, iptv_group_order = await fetch_iptv_api_source()
    
    # 4. 写入最终的 M3U 文件
    print(f"\n📝 正在写入 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # ========== 公告（带时间戳）==========
        f.write(f'\n# ========== 公告 ==========\n')
        f.write(f'#EXTINF:-1 tvg-id="update" tvg-name="更新时间" group-title="公告",更新时间 {current_time}\n')
        f.write(f'https://vdse.bdstatic.com//a499dfbec34060ce0f380ea789446f07.mp4\n')
        
        # ========== 本地源 ==========
        if channels_by_group:
            local_count = 0
            for group, channels in channels_by_group.items():
                if group == '公告':
                    continue
                f.write(f'\n# ========== 本地源 ==========\n')
                f.write(f'\n# 分组：{group}\n')
                for ch in channels:
                    extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                    if ch.get('logo'):
                        extinf += f' tvg-logo="{ch["logo"]}"'
                    extinf += f' group-title="{group}",{ch["name"]}'
                    f.write(extinf + '\n')
                    f.write(ch['url'] + '\n')
                    local_count += 1
            print(f"   - 本地源: {local_count} 个频道")
        
        # ========== 酒店源（带时间戳）==========
        if hotel_groups:
            hotel_count = 0
            f.write(f'\n# ========== {HOTEL_MAIN_GROUP} [{current_time}] ==========\n')
            for group in hotel_group_order:
                if group in hotel_groups and hotel_groups[group]:
                    # 分组名称映射
                    display_group = "央    视" if group == "央视频道" else group
                    f.write(f'\n# 分组：{display_group}\n')
                    for ch in hotel_groups[group]:
                        extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{display_group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
                        hotel_count += 1
            print(f"   - 酒店源: {hotel_count} 个频道")
        else:
            print(f"   - 酒店源: 0 个频道（请检查URL是否正确）")
        
        # ========== iptv-api 源（带时间戳）==========
        if iptv_groups:
            iptv_count = 0
            f.write(f'\n# ========== {IPTV_API_MAIN_GROUP} [{current_time}] ==========\n')
            for group in iptv_group_order:
                if group in iptv_groups and iptv_groups[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in iptv_groups[group]:
                        extinf = f'#EXTINF:-1 tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')
                        iptv_count += 1
            print(f"   - iptv-api: {iptv_count} 个频道")
        else:
            print(f"   - iptv-api: 0 个频道")
    
    print(f"\n{'='*50}")
    print(f"✅ 合并完成！输出文件: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
