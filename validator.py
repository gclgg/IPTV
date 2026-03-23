import re
import os
from collections import defaultdict
from datetime import datetime

OUTPUT_FILE = "live.m3u"
INPUT_SOURCE = "live.txt"

EPG_URLS = [
    "http://epg.112114.xyz/pp.xml",
    "https://epg.112114.free.hr/pp.xml",
]

def clean_group_name(group_name):
    """清理分组名称，去掉逗号"""
    return re.sub(r',', '', group_name).strip()

def parse_txt_file(filename, current_time):
    """解析 TXT 文件，直接转换为 M3U 结构"""
    channels_by_group = defaultdict(list)
    current_group = "未分组"
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 分组行
            if line.endswith('#genre#'):
                current_group = clean_group_name(line[:-7].strip())
                continue
            # 频道行
            if ',' in line:
                parts = line.split(',', 1)
                channel_name = parts[0].strip()
                full_url = parts[1].strip()
                
                # 公告分组：更新时间戳
                if current_group == '公告':
                    if '更新日期' in channel_name:
                        channel_name = f"更新日期 {current_time}"
                    elif '仓库更新时间' in channel_name:
                        channel_name = f"📦 仓库更新时间 {current_time}"
                
                channels_by_group[current_group].append({
                    'name': channel_name,
                    'url': full_url
                })
    
    return dict(channels_by_group)

def main():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n🕐 当前时间: {current_time}")
    
    # 检查输入文件
    if not os.path.exists(INPUT_SOURCE):
        print(f"错误：文件 {INPUT_SOURCE} 不存在！")
        return
    
    # 解析文件
    channels_by_group = parse_txt_file(INPUT_SOURCE, current_time)
    
    # 统计
    total_channels = sum(len(ch) for ch in channels_by_group.values())
    print(f"📊 解析完成，共 {len(channels_by_group)} 个分组，{total_channels} 个频道")
    
    # 写入 M3U 文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # EPG 信息行
        f.write('#EXTM3U x-tvg-url="' + '","'.join(EPG_URLS) + '"\n')
        
        # 按分组写入
        for group, channels in channels_by_group.items():
            f.write(f'\n# 分组：{group}\n')
            for idx, ch in enumerate(channels, 1):
                tvg_id = str(abs(hash(ch['name'])) % 10000)
                extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}" group-title="{group}",{ch["name"]}'
                f.write(extinf + '\n')
                f.write(ch['url'] + '\n')
    
    print(f"\n✅ 转换完成！输出文件: {OUTPUT_FILE}")
    print(f"   - 分组数: {len(channels_by_group)}")
    print(f"   - 频道数: {total_channels}")

if __name__ == "__main__":
    main()
