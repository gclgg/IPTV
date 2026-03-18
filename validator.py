import subprocess
import json
import asyncio
import aiohttp
import re
import os
from collections import defaultdict
from datetime import datetime

# --- 配置参数 ---
CONCURRENT_CHECKS = 20          # 并发数
FAST_CHECK_TIMEOUT = 5          # 快速 HEAD 检查超时（秒）
FFPROBE_TIMEOUT = 15            # ffprobe 超时时间（秒）
MIN_BITRATE = 500               # 最小码率要求 (kbps)
OUTPUT_FILE = "live.m3u"        # 最终生成的有效源文件
INPUT_SOURCE = "live.txt"       # 原始源列表文件
# ------------------------------------

def clean_group_name(group_name):
    """清理分组名称，去掉逗号等特殊字符"""
    return re.sub(r'[,\n\r]', ' ', group_name).strip()

def extract_logo_from_m3u(channel_name, m3u_file):
    """从原始 M3U 文件中提取指定频道的 logo URL"""
    if not os.path.exists(m3u_file):
        return ""
    
    with open(m3u_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF') and f',{channel_name}' in line:
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                return logo_match.group(1)
    return ""

def parse_txt_file(filename):
    """
    解析直播源 TXT 文件，返回结构化的数据
    """
    channels_by_group = defaultdict(list)
    current_group = "未分组"
    
    # 获取同名的 M3U 文件（用于提取 logo）
    m3u_file = filename.replace('.txt', '.m3u')
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是分组行（以 #genre# 结尾）
            if line.endswith('#genre#'):
                raw_group = line[:-7].strip()
                current_group = clean_group_name(raw_group)
                continue
            
            # 处理频道行（格式：频道名,完整URL）
            if ',' in line:
                parts = line.split(',', 1)
                channel_name = parts[0].strip()
                full_url = parts[1].strip()
                
                # 提取纯净的URL（去掉$后面的所有参数）- 只用于检测
                clean_url = re.sub(r'\$.*$', '', full_url)
                
                # 提取线路信息（如果有）
                line_info = ""
                line_match = re.search(r'『([^』]+)』', full_url)
                if line_match:
                    line_info = line_match.group(1)
                
                # 从 M3U 文件中提取 logo
                logo_url = extract_logo_from_m3u(channel_name, m3u_file)
                
                channels_by_group[current_group].append({
                    'name': channel_name,
                    'full_url': full_url,
                    'clean_url': clean_url,
                    'line_info': line_info,
                    'logo': logo_url,
                    'original_line_num': line_num,
                    'is_announcement': current_group == '公告'
                })
    
    return dict(channels_by_group)

async def fast_check(session, clean_url):
    """快速 HEAD 检查，判断 URL 是否可达"""
    try:
        async with session.head(clean_url, timeout=FAST_CHECK_TIMEOUT, allow_redirects=True) as resp:
            if resp.status in [200, 301, 302, 307, 308]:
                return True, resp.status
            else:
                return False, f"HTTP {resp.status}"
    except asyncio.TimeoutError:
        return False, "HEAD timeout"
    except Exception as e:
        return False, str(e)[:50]

async def ffprobe_check(clean_url):
    """使用 ffprobe 详细检测流信息，返回分辨率和码率"""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams',
        '-rw_timeout', f'{FFPROBE_TIMEOUT * 1000000}',
        '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '-i', clean_url
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=FFPROBE_TIMEOUT)
        
        if process.returncode != 0:
            return None
        
        data = json.loads(stdout)
        
        video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        
        if video_stream:
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            bitrate = video_stream.get('bit_rate', 0)
            
            if bitrate and int(bitrate) / 1000 < MIN_BITRATE:
                return None
            
            # 计算质量分数：分辨率越高越好，码率越高越好
            quality_score = (height * 10000) + (bitrate / 1000)  # 分辨率优先
            
            return {
                'resolution': f"{width}x{height}",
                'height': height,
                'bitrate': int(bitrate) if bitrate else 0,
                'quality_score': quality_score
            }
        else:
            return None
            
    except:
        return None

async def check_channel(session, channel):
    """检测单个频道，返回结果和分辨率信息"""
    # 如果是公告分组，直接返回有效（不检测）
    if channel.get('is_announcement', False):
        return {
            'name': channel['name'],
            'group': channel['group'],
            'full_url': channel['full_url'],
            'logo': channel['logo'],
            'valid': True,
            'height': 1080,
            'resolution': '1920x1080',
            'bitrate': 5000,
            'quality_score': 10800000,  # 高分
            'is_announcement': True
        }
    
    clean_url = channel['clean_url']
    
    # 快速 HEAD 检查
    head_ok, _ = await fast_check(session, clean_url)
    if not head_ok:
        return None
    
    # ffprobe 详细检测
    probe_result = await ffprobe_check(clean_url)
    if not probe_result:
        return None
    
    return {
        'name': channel['name'],
        'group': channel['group'],
        'full_url': channel['full_url'],
        'logo': channel['logo'],
        'valid': True,
        'height': probe_result['height'],
        'resolution': probe_result['resolution'],
        'bitrate': probe_result['bitrate'],
        'quality_score': probe_result['quality_score'],
        'is_announcement': False
    }

async def main():
    import time
    start_time = time.time()
    
    # 获取当前时间
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"🕐 当前时间: {current_time}")
    
    # 1. 解析文件
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    
    channels_by_group = parse_txt_file(INPUT_SOURCE)
    total_channels = sum(len(channels) for channels in channels_by_group.values())
    print(f"解析完成，共 {len(channels_by_group)} 个分组，{total_channels} 个频道")
    
    if total_channels == 0:
        print("没有找到任何频道，请检查文件格式。")
        return

    # 2. 分离公告分组和其他分组
    announcement_channels = []
    normal_channels_by_name = defaultdict(list)
    
    # 用于存储公告的logo和视频URL
    announcement_logo = ""
    announcement_video_url = ""
    
    for group, channels in channels_by_group.items():
        for channel in channels:
            if group == '公告':
                # 收集公告信息
                if '更新日期' in channel['name']:
                    announcement_logo = channel['logo']
                    announcement_video_url = channel['full_url']
            else:
                normal_channels_by_name[channel['name']].append({
                    'group': group,
                    'name': channel['name'],
                    'clean_url': channel['clean_url'],
                    'full_url': channel['full_url'],
                    'logo': channel['logo'],
                    'is_announcement': False
                })

    print(f"📢 公告信息已保留")
    print(f"📺 待检测频道: {sum(len(v) for v in normal_channels_by_name.values())} 个源，{len(normal_channels_by_name)} 个频道")

    # 3. 并发检测普通频道
    all_tasks = []
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False),
        headers={'User-Agent': 'Mozilla/5.0'}
    ) as session:
        semaphore = asyncio.Semaphore(CONCURRENT_CHECKS)
        
        for channel_name, sources in normal_channels_by_name.items():
            for source in sources:
                async def check_with_semaphore(s=source):
                    async with semaphore:
                        return await check_channel(session, s)
                all_tasks.append(check_with_semaphore())
        
        results = await asyncio.gather(*all_tasks)

    # 4. 按频道名分组有效结果（只保留有效的）
    valid_by_channel = defaultdict(list)
    for result in results:
        if result and result['valid']:
            valid_by_channel[result['name']].append(result)

    # 5. 为每个频道的多个源按质量排序并重新编号
    epg_urls = [
        "http://epg.112114.xyz/pp.xml",
        "https://epg.112114.free.hr/pp.xml",
        "https://epg.112114.eu.org/pp.xml",
        "https://epg.v1.mk/fy.xml",
        "https://epg.v1.mk/fy.xml.gz",
        "http://epg.51zmt.top:8000/e.xml",
        "http://epg.51zmt.top:8000/e.xml.gz",
        "http://epg.aptvapp.com/xml",
        "https://epg.pw/xmltv/epg_CN.xml",
        "https://epg.pw/xmltv/epg_HK.xml",
        "https://epg.pw/xmltv/epg_TW.xml"
    ]

    # 写入最终的 M3U 文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # 写入 EPG 信息行
        epg_line = '#EXTM3U x-tvg-url="' + '","'.join(epg_urls) + '"'
        f.write(epg_line + '\n')
        
        # 1. 写入公告分组（只保留更新日期一条）
        if announcement_video_url:
            f.write("\n# 分组：公告\n")
            
            # 更新日期带时间
            announcement_name = f"更新日期 {current_time}"
            
            # 生成 tvg-id
            tvg_id = str(abs(hash(announcement_name)) % 10000)
            
            # 构建 EXTINF 行
            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{announcement_name}"'
            if announcement_logo:
                extinf += f' tvg-logo="{announcement_logo}"'
            extinf += f' group-title="公告",{announcement_name}'
            
            f.write(extinf + '\n')
            f.write(announcement_video_url + '\n')
        
        # 2. 按原分组顺序写入普通频道
        output_by_group = defaultdict(list)
        
        # 对每个频道的多个源按质量分数排序
        for channel_name, sources in valid_by_channel.items():
            # 按质量分数从高到低排序（分辨率优先，码率次之）
            sources.sort(key=lambda x: -x['quality_score'])
            
            # 重新编号线路（从1开始，按质量排序）
            for idx, source in enumerate(sources, 1):
                group = source['group']
                full_url = source['full_url']
                logo = source['logo']
                
                # 提取纯净URL并添加新的线路编号
                clean_base = re.sub(r'\$.*$', '', full_url)
                numbered_url = f"{clean_base}『线路{idx}』"
                
                output_by_group[group].append({
                    'name': channel_name,
                    'url': numbered_url,
                    'quality_score': source['quality_score'],
                    'height': source['height'],
                    'logo': logo,
                    'line_num': idx  # 记录线路编号
                })
        
        # 按原分组顺序写入，组内按质量排序
        for group in channels_by_group.keys():
            if group != '公告' and group in output_by_group and output_by_group[group]:
                # 组内按质量分数排序（高的在前）
                output_by_group[group].sort(key=lambda x: -x['quality_score'])
                
                f.write(f"\n# 分组：{group}\n")
                
                for channel in output_by_group[group]:
                    tvg_id = str(abs(hash(channel['name'])) % 10000)
                    
                    extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{channel["name"]}"'
                    if channel['logo']:
                        extinf += f' tvg-logo="{channel["logo"]}"'
                    extinf += f' group-title="{group}",{channel["name"]}'
                    
                    f.write(extinf + '\n')
                    f.write(channel['url'] + '\n')

    # 统计信息
    total_valid = sum(len(s) for s in valid_by_channel.values())
    elapsed = time.time() - start_time
    
    print(f"\n✅ 检测完成！耗时: {elapsed:.1f} 秒")
    print(f"有效源: {total_valid}，频道数: {len(valid_by_channel)}")
    
    # 打印分组统计
    print("\n📁 分组统计：")
    print(f"  公告: 1 (更新日期 {current_time})")
    for group in channels_by_group.keys():
        if group != '公告' and group in output_by_group:
            count = len(output_by_group[group])
            # 计算该组平均质量
            avg_height = sum(c['height'] for c in output_by_group[group]) / count if count > 0 else 0
            print(f"  {group}: {count} 个源 (平均{int(avg_height)}p)")
    
    # 打印质量最好的几个频道示例
    print("\n🏆 质量最好的频道示例：")
    best_channels = []
    for group in output_by_group:
        for channel in output_by_group[group][:1]:  # 每组取第一个
            best_channels.append(channel)
    
    best_channels.sort(key=lambda x: -x['quality_score'])
    for channel in best_channels[:5]:
        print(f"  {channel['name']}: {channel['height']}p (线路{channel['line_num']})")
    
    print(f"\n🕐 更新时间: {current_time}")

if __name__ == "__main__":
    asyncio.run(main())
