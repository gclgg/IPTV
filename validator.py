原py配置
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
    # 主力 EPG 源（已验证可用）
    "https://epg.pw/xmltv/epg_CN.xml",
    
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
    """清理分组名称，去掉逗号"""
    return re.sub(r',', '', group_name).strip()

async def fetch_my_logo_list():
    """从你的GitHub仓库获取Logo列表"""
    print(f"\n📡 正在从你的仓库拉取Logo列表: {LOGO_BASE_URL}")
    api_url = f"https://api.github.com/repos/{LOGO_REPO_OWNER}/{LOGO_REPO_NAME}/contents/{LOGO_PATH_IN_REPO}"
    my_logos = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status != 200:
                    print(f"⚠️ 无法获取Logo列表 (HTTP {resp.status})")
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
    """建立完整的Logo数据库"""
    global LOGO_DATABASE
    LOGO_DATABASE = {}
    
    # 1. 从你的GitHub仓库获取
    my_logos = await fetch_my_logo_list()
    LOGO_DATABASE.update(my_logos)
    print(f"📦 从你的仓库加载 {len(my_logos)} 个logo")
    
    # 2. 从本地 M3U 提取（如果有）
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
            print(f"📦 从本地 M3U 补充了一些logo")
        except:
            pass
    
    # 3. 从通用库补充
    for name, url in COMMON_LOGOS.items():
        if name not in LOGO_DATABASE:
            LOGO_DATABASE[name] = url
    print(f"✅ Logo数据库共 {len(LOGO_DATABASE)} 条记录")

def get_logo(channel_name):
    """获取频道Logo"""
    return LOGO_DATABASE.get(channel_name, "")

def parse_txt_file(filename, current_time):
    """解析 TXT 文件"""
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
                
                # 公告分组：更新时间戳
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
    
    # 3. 拉取酒店源
    hotel_groups, hotel_group_order = await fetch_hotel_source()
    
    # 4. 写入M3U文件
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
    
    # 统计
    total_local = sum(len(ch) for ch in channels_by_group.values())
    total_hotel = sum(len(ch) for ch in hotel_groups.values()) if hotel_groups else 0
    print(f"\n✅ 转换完成！")
    print(f"   - 本地源: {total_local} 个频道")
    print(f"   - 酒店源: {total_hotel} 个频道")
    print(f"   - 总计: {total_local + total_hotel} 个频道")

if __name__ == "__main__":
    asyncio.run(main())





原main配置
name: Scheduled Auto Update

on:
  schedule:
    - cron: '0 22 * * *'
  workflow_dispatch:

jobs:
  auto-update:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          persist-credentials: true

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install requests aiohttp

      - name: Run main.py
        run: python main.py
        env:
          TZ: Asia/Shanghai

      - name: Run validator.py
        run: python validator.py

      - name: Commit & Push
        if: always()
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if [ -n "$(git status --porcelain)" ]; then
            git add .
            git commit -m "AutoUpdate: $(date +'%Y-%m-%d %H:%M:%S')"
            git pull --rebase origin main
            git push origin main
          fi
