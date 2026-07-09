#!/usr/bin/env python3
import os
import re
import sys
import time
import shutil
from pathlib import Path
import requests

# ==================== 配置区 ====================
TMDB_API_KEY = "" #填写tmdb api key
LANGUAGE = "zh-CN"  # 强制拉取中文译名/简介
DOWNLOAD_DIR = Path("/data/hdd/unRename")  # 你的下载目录
TARGET_BASE = Path("/data/hdd/unDecode")  # 送去压制前的暂存目录
DRY_RUN = False  # 测试模式：True=只打印不修改，False=实际执行
FILE_ACTION = "copy"  # 文件操作模式："move" 为直接移动，"copy" 为复制（如果不保留做种推荐 move）
# ================================================

def get_tmdb_session():
    """创建带超时和重试的TMDB会话（适配 v4 Bearer Token）"""
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {TMDB_API_KEY}"})
    session.params.update({"language": LANGUAGE})
    session.timeout = 10
    return session

def clean_for_search(filename):
    """清理文件名，提取纯粹的动漫名称供TMDB搜索"""
    name = re.sub(r'\[.*?\]', ' ', filename)
    name = re.sub(r'\(.*?\)', ' ', name)
    name = re.sub(r'(?i)Season\s*\d+|S\d{1,2}|第[一二三四五六七八九十\d]+季', ' ', name)
    name = re.sub(r'(?i)(?:EP?|第|-)\s*\d{1,3}\s*(?:话|集|v\d)?', ' ', name)
    name = re.sub(r'\b[IVXLCDM]{1,4}\b', ' ', name)
    name = re.sub(r'[_\-\.]', ' ', name).strip()
    return re.sub(r'\s+', ' ', name)

def search_tmdb(session, query):
    """搜索TMDB匹配动漫，获取标准中文剧名"""
    clean_query = clean_for_search(query)
    if not clean_query:
        return None
    
    try:
        resp = session.get("https://api.themoviedb.org/3/search/tv", params={"query": clean_query}).json()
        if resp.get("results"):
            return resp["results"][0]
    except Exception as e:
        print(f"  ❌ TMDB搜索失败 ({clean_query}): {e}")
    return None

def parse_season_episode(filename):
    """从文件名解析季数和集数（深度适配 VCB/7ACG）"""
    if re.search(r'(?i)(NCOP|NCED|Menu|SP\d+|OVA)', filename):
        return None, None
# ====== 解析季数 (Season) ======
    season_patterns = [
        r'第([一二三四五六七八九十\d]+)季',
        r'(?i)Season\s*(\d+)',
        r'(?i)(\d+)\s*(?:nd|rd|th)?\s*Season', # 适配 "2nd Season" 这种写法
        r'(?i)S(\d{1,2})',
        r'\s([IVXLCDM]+)\s',
        r'\s(0?[2-9])\s*(?=\[|-)'  # 🌟新增：针对 "Tawawa 2 [05]" 这种极简数字
    ]
    season_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    
    season = 1
    for pattern in season_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            season_str = match.group(1).upper()
            if season_str in season_map:
                season = season_map[season_str]
            elif re.match(r'^[IVXLCDM]+$', season_str):
                season = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10}.get(season_str, 1)
            else:
                season = int(season_str)
            break
    
    # ====== 解析集数 (Episode) ======
    temp_name = re.sub(r'(?i)1080p|720p|2160p|4k|x264|x265|hevc|ma10p|h264|h265|20\d{2}', '', filename)
    ep_patterns = [
        r'\[(\d{2,3})(?:v\d)?\]',
        r'(?:EP?|第)\s*(\d{1,3})\s*(?:话|集|v\d)?',
        r'-\s*(\d{2,3})\s'
    ]
    
    episode = None
    for pattern in ep_patterns:
        ep_match = re.search(pattern, temp_name, re.IGNORECASE)
        if ep_match:
            episode = int(ep_match.group(1))
            break
            
    return season, episode

def get_base_stem(filename):
    """获取无后缀、无语言标记的文件主名，用于将视频和字幕编组"""
    name = filename
    if name.lower().endswith(('.ass', '.srt', '.mkv', '.mp4')):
        name = name.rsplit('.', 1)[0]
        
    lang_tags = ['.jpsc', '.jptc', '.sc', '.tc', '.chs', '.cht', '.zh-cn', '.zh-tw', '.cn', '.tw']
    for tag in lang_tags:
        if name.lower().endswith(tag):
            name = name[:-len(tag)]
            break
            
    return name

def process_file_group(session, base_stem, files):
    """按组处理文件（确保视频先处理，建立TMDB缓存，再处理关联字幕）"""
    print(f"\n📁 处理系列: {base_stem}")
    
    files.sort(key=lambda x: 0 if x.suffix.lower() in {'.mkv', '.mp4'} else 1)
    
    for file_path in files:
        season, episode = parse_season_episode(file_path.stem)
        if not season or not episode:
            print(f"  ⏭️ {file_path.name}: 无法解析常规季/集信息(可能是SP/NCOP)，跳过")
            continue
        
        tv_id = cn_name = ""
        cache_file = file_path.parent.joinpath(f".tmdb_{base_stem}.cache")
        
        if file_path.suffix.lower() in {'.mkv', '.mp4'}:
            tmdb_info = search_tmdb(session, file_path.stem)
            if not tmdb_info:
                print(f"  ❌ {file_path.name}: TMDB未找到匹配动漫，跳过")
                continue
            
            tv_id = tmdb_info["id"]
            cn_name = tmdb_info["name"]
            cache_file.write_text(f"{tv_id}|{cn_name}", encoding="utf-8")
        else:
            if not cache_file.exists():
                print(f"  ❌ {file_path.name}: 未找到关联视频的TMDB缓存，跳过字幕")
                continue
            tv_id, cn_name = cache_file.read_text(encoding="utf-8").split("|")
        
        # 清除剧名中可能引发路径错误的非法字符
        safe_cn_name = re.sub(r'[\\/*?:"<>|]', '-', cn_name)
        show_dir = TARGET_BASE / safe_cn_name
        season_dir = show_dir / f"Season {str(season).zfill(2)}"
        
        if not DRY_RUN:
            season_dir.mkdir(parents=True, exist_ok=True)
        
        # 视频和字幕严格对齐命名：剧集名 S01E01 (移除副标题)
        new_stem = f"{safe_cn_name} S{str(season).zfill(2)}E{str(episode).zfill(2)}"
            
        final_suffix = file_path.suffix
        name_lower = file_path.name.lower()
        if '.ass' in name_lower or '.srt' in name_lower:
            if 'jpsc' in name_lower or '.sc' in name_lower or 'chs' in name_lower or 'zh-cn' in name_lower:
                final_suffix = '.zh-CN' + file_path.suffix
            elif 'jptc' in name_lower or '.tc' in name_lower or 'cht' in name_lower or 'zh-tw' in name_lower:
                final_suffix = '.zh-TW' + file_path.suffix

        target_path = season_dir / f"{new_stem}{final_suffix}"
        
        if target_path.exists():
            print(f"  ⏭️ 目标已存在: {target_path.name}")
            continue
            
        if DRY_RUN:
            print(f"  🔍 [测试] {file_path.name} -> {target_path}")
            continue
            
        try:
            if FILE_ACTION == "copy":
                shutil.copy2(file_path, target_path)
                print(f"  ✅ 复制成功: {target_path.name}")
            else:
                shutil.move(file_path, target_path)
                print(f"  ✅ 移动成功: {target_path.name}")
        except Exception as e:
            print(f"  ❌ 操作失败: {e}")
            continue

        # 处理完一部视频后稍微等待，避免触发 TMDB 限流
        if file_path.suffix.lower() in {'.mkv', '.mp4'}:
            time.sleep(0.3)

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  测试模式: python3 {sys.argv[0]} --dry-run /data/hdd/unRename")
        print(f"  批量处理: python3 {sys.argv[0]} /data/hdd/unRename")
        sys.exit(1)
        
    args = sys.argv[1:]
    if "--dry-run" in args:
        global DRY_RUN
        DRY_RUN = True
        args.remove("--dry-run")
        print("===== 测试模式启动（仅打印预览日志） =====")
        
    session = get_tmdb_session()
    
    files_to_process = []
    valid_exts = {'.mkv', '.mp4', '.ass', '.srt'}
    
    for arg in args:
        path = Path(arg)
        if path.is_file() and path.suffix.lower() in valid_exts:
            files_to_process.append(path)
        elif path.is_dir():
            # 这里使用了 rglob('*') 支持无限层级子目录扫描
            for file in path.rglob('*'):
                if file.is_file() and file.suffix.lower() in valid_exts:
                    files_to_process.append(file)

    groups = {}
    for f in files_to_process:
        base_stem = get_base_stem(f.name)
        groups.setdefault(base_stem, []).append(f)

    for base_stem, files in groups.items():
        process_file_group(session, base_stem, files)

    # 运行完毕清理临时缓存文件 (同样使用 rglob 扫描子目录)
    for arg in args:
        path = Path(arg)
        search_dir = path if path.is_dir() else path.parent
        for cache in search_dir.rglob(".tmdb_*.cache"):
            cache.unlink(missing_ok=True)
            
    print("\n===== 所有任务处理完成 =====")

if __name__ == "__main__":
    main()
