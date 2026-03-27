import re
import os
import aiohttp
import asyncio
from collections import defaultdict
from datetime import datetime

OUTPUT_FILE = "live.m3u"
INPUT_SOURCE = "live.txt"

# 酒店源配置
HOTEL_SOURCE_URL = "https://raw.githubusercontent.com/gclgg/zubo/main/itvlist.txt"
HOTEL_MAIN_GROUP = "酒店源"

# iptv-api 源配置

IPTV_API_URL = "https://raw.githubusercontent.com/gclgg/iptv-api/refs/heads/master/output/result.m3u"
IPTV_API_MAIN_GROUP = "iptv-api"

# Logo仓库配置
LOGO_REPO_OWNER = "gclgg"
LOGO_REPO_NAME = "live"
LOGO_PATH_IN_REPO = "tv"
LOGO_BASE_URL = f"https://raw.githubusercontent.com/{LOGO_REPO_OWNER}/{LOGO_REPO_NAME}/main/{LOGO_PATH_IN_REPO}"

# 分组名称映射
GROUP_MAPPING = {
    "央视频道": "央    视",
}

EPG_URLS = [
"https://epg.gcl.de5.net/epg/51zmt.xml",
"https://epg.gcl.de5.net/epg/51zmt_df.xml",
"https://epg.gcl.de5.net/epg/51zmt_cc.xml",
"https://epg.gcl.de5.net/epg/epg_pw.xml",
"http://epg.51zmt.top:8000/e.xml",
]

# 全局Logo库
LOGO_DATABASE = {}

# 通用Logo库（备用）
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
    "凤凰卫视香港台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixHK.png",
    "凤凰卫视电影台": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/PhoenixMovies.png",
    "湖南卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hunan.png",
    "浙江卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Zhejiang.png",
    "江苏卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Jiangsu.png",
    "东方卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/DragonTV.png",
    "北京卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Beijing.png",
    "广东卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Guangdong.png",
    "深圳卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Shenzhen.png",
    "湖北卫视": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Hubei.png",
    "求索纪录": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Discovery.png",
    "全纪实": "https://gcore.jsdelivr.net/gh/yuanzl77/TVlogo@master/png/Documentary.png",
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

async def build_logo_database(m3u_file):
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
                logo_url = get_logo(channel_name)
                if current_group == '公告':
                    if '更新日期' in channel_name:
                        channel_name = f"更新日期 {current_time}"
                    elif '仓库更新时间' in channel_name:
                        channel_name = f"📦 仓库更新时间 {current_time}"
                channels_by_group[current_group].append({
                    'name': channel_name,
                    'url': full_url,
                    'logo': logo_url
                })
    return dict(channels_by_group)

async def fetch_hotel_source():
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

async def fetch_iptv_api_source():
    """拉取 iptv-api 源的 M3U 文件，通过 group-title 解析分组"""
    print(f"\n📡 正在拉取 iptv-api 源: {IPTV_API_URL}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(IPTV_API_URL, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ 拉取失败: HTTP {resp.status}")
                    return None, None
                
                content = await resp.text()
                print(f"📄 原始内容长度: {len(content)} 字符")
                
                lines = content.strip().split('\n')
                
                iptv_groups = defaultdict(list)
                iptv_group_order = []
                current_name = ""
                current_group = "未分组"
                current_tvg_id = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 处理 EXTINF 行，从中提取 group-title
                    if line.startswith('#EXTINF'):
                        # 提取 group-title
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            current_group = group_match.group(1).strip()
                            if current_group not in iptv_group_order:
                                iptv_group_order.append(current_group)
                                print(f"   📁 发现分组: {current_group}")
                        
                        # 提取频道名称
                        name_match = re.search(r',([^,]+)$', line)
                        if name_match:
                            current_name = name_match.group(1).strip()
                            # 去掉 CCTV- 中的横杠
                            current_name = current_name.replace('CCTV-', 'CCTV')
                        
                        # 提取 tvg-id
                        tvg_id_match = re.search(r'tvg-id="([^"]+)"', line)
                        if tvg_id_match:
                            current_tvg_id = tvg_id_match.group(1)
                            # 同时处理 tvg-id 中的横杠
                            current_tvg_id = current_tvg_id.replace('CCTV-', 'CCTV')
                        continue
                    
                    # 处理 URL 行（不以 # 开头）
                    if line and not line.startswith('#') and current_name:
                        iptv_groups[current_group].append({
                            'name': current_name,
                            'url': line,
                            'tvg_id': current_tvg_id,
                            'logo': get_logo(current_name)
                        })
                        if len(iptv_groups[current_group]) == 1:
                            print(f"   ✅ 示例频道: {current_name} -> 使用本仓库Logo")
                        current_name = ""
                        current_tvg_id = ""
                
                total = sum(len(ch) for ch in iptv_groups.values())
                if total == 0:
                    print(f"⚠️ 解析到 0 个频道")
                    iptv_groups["iptv-api源"].append({
                        'name': 'iptv-api 源',
                        'url': IPTV_API_URL,
                        'logo': ''
                    })
                    iptv_group_order = ["iptv-api源"]
                    total = 1
                else:
                    print(f"✅ 拉取成功，共 {len(iptv_groups)} 个分组，{total} 个频道")
                    for group in iptv_group_order:
                        if group in iptv_groups:
                            print(f"   - {group}: {len(iptv_groups[group])} 个频道")
                
                return iptv_groups, iptv_group_order
                
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return None, None

async def main():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n🕐 当前时间: {current_time}")
    
    # 1. 建立Logo数据库
    m3u_file = INPUT_SOURCE.replace('.txt', '.m3u')
    await build_logo_database(m3u_file)
    
    # 2. 解析本地源
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    channels_by_group = parse_txt_file(INPUT_SOURCE, current_time)
    
    # 3. 拉取酒店源（初始化默认值）
    hotel_groups = {}
    hotel_group_order = []
    try:
        result = await fetch_hotel_source()
        if result and len(result) == 2:
            hotel_groups, hotel_group_order = result
        else:
            print(f"⚠️ 酒店源返回数据格式异常，使用默认值")
    except Exception as e:
        print(f"⚠️ 拉取酒店源失败: {e}")
    
    # 4. 拉取 iptv-api 源（初始化默认值）
    iptv_groups = {}
    iptv_group_order = []
    try:
        result = await fetch_iptv_api_source()
        if result and len(result) == 2:
            iptv_groups, iptv_group_order = result
        else:
            print(f"⚠️ iptv-api 源返回数据格式异常，使用默认值")
    except Exception as e:
        print(f"⚠️ 拉取 iptv-api 源失败: {e}")
    
    # 确保变量是字典和列表类型
    if iptv_groups is None:
        iptv_groups = {}
    if iptv_group_order is None:
        iptv_group_order = []
    if hotel_groups is None:
        hotel_groups = {}
    if hotel_group_order is None:
        hotel_group_order = []
    
    # 5. 写入M3U文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # === 本地源 ===
        for group, channels in channels_by_group.items():
            if group == '公告':
                f.write(f'\n# ========== 公告 ==========\n')
            else:
                f.write(f'\n# ========== 本地源 ==========\n')
                f.write(f'\n# 分组：{group}\n')
            
            for ch in channels:
                tvg_id = str(abs(hash(ch['name'])) % 10000)
                extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                if ch.get('logo'):
                    extinf += f' tvg-logo="{ch["logo"]}"'
                extinf += f' group-title="{group}",{ch["name"]}'
                f.write(extinf + '\n')
                f.write(ch['url'] + '\n')
        
        # === 酒店源 ===
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
        
        # === iptv-api 源 ===
        if iptv_groups and iptv_group_order:
            f.write(f'\n# ========== {IPTV_API_MAIN_GROUP} [{current_time}] ==========\n')
            for group in iptv_group_order:
                if group in iptv_groups and iptv_groups[group]:
                    f.write(f'\n# 分组：{group}\n')
                    for ch in iptv_groups[group]:
                        tvg_id = str(abs(hash(ch['name'])) % 10000)
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}"'
                        if ch.get('logo'):
                            extinf += f' tvg-logo="{ch["logo"]}"'
                        extinf += f' group-title="{group}",{ch["name"]}'
                        f.write(extinf + '\n')
                        f.write(ch['url'] + '\n')

            
    # 统计
    total_local = sum(len(ch) for ch in channels_by_group.values())
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    total_iptv = sum(len(ch) for ch in iptv_groups.values()) if iptv_groups else 0
    print(f"\n✅ 转换完成！")
    print(f"   - 本地源: {total_local} 个频道")
    print(f"   - 酒店源: {total_hotel} 个频道")
    print(f"   - iptv-api: {total_iptv} 个频道")
    print(f"   - 总计: {total_local + total_hotel + total_iptv} 个频道")

    # 统计
    total_local = sum(len(ch) for ch in channels_by_group.values())
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    total_iptv = sum(len(ch) for ch in iptv_groups.values()) if iptv_groups else 0
    print(f"\n✅ 转换完成！")
    print(f"   - 本地源: {total_local} 个频道")
    print(f"   - 酒店源: {total_hotel} 个频道")
    print(f"   - iptv-api: {total_iptv} 个频道")
    print(f"   - 总计: {total_local + total_hotel + total_iptv} 个频道")

if __name__ == "__main__":
    asyncio.run(main())
