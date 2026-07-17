#!/usr/bin/env python3
import os
import re
import sys
import time
import shutil
import subprocess
import json
from pathlib import Path
import requests

# ==================== 配置区 ====================
TMDB_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIwZDg2OGI3MDdhYjFiZWE2NDg4YTgxMmZjZjg1MmNkZCIsIm5iZiI6MTc4MzYyNjc1My4zMTEsInN1YiI6IjZhNGZmYzAxODU1ZTIyZjA2M2Q5ZGFlNSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.Pj-GvRI3Sv7GKUbTOQh5JJmiU9r1hmlXH7b7VdJA4ts"
LANGUAGE = "zh-CN"
DOWNLOAD_DIR = Path("/data/hdd/downloads/unRename")

FINAL_LIBRARY_DIR = Path("/data/hdd/anime")
ENCODE_TARGET_DIR = Path("/data/nvme/unDecode")
ENCODE_LIST_PATH = Path("/data/nvme/encode_trigger.list")

BITRATE_THRESHOLD_KBPS = 3000
DRY_RUN = False
FILE_ACTION = "move"
# ================================================

def get_tmdb_session():
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {TMDB_API_KEY}"})
    session.params.update({"language": LANGUAGE})
    session.timeout = 10
    return session

def clean_for_search(filename):
    name = re.sub(r'^\[.*?\]', ' ', filename)
    name = re.sub(r'(?i)\[.*?(1080|720|2160|4k|rip|hevc|x264|x265|flac|aac|opus|av1|ma10p|bit).*?\]', ' ', name)
    name = re.sub(r'\(.*?\)', ' ', name)
    name = re.sub(r'[\[\]]', ' ', name)
    
    name = re.sub(r'\b(19|20)\d{2}\b', ' ', name)
    name = re.sub(r'(?i)Season\s*\d+|S\d{1,2}|第[一二三四五六七八九十\d]+季', ' ', name)
    name = re.sub(r'(?i)(?:\bEP?|第|-)\s*\d{1,3}\s*(?:话|集|v\d)?', ' ', name)
    name = re.sub(r'(?i)\b(?:SP|OVA|OAD)\s*\d{0,2}\b', ' ', name)
    name = re.sub(r'\b[IVXLCDM]{1,4}\b', ' ', name)
    name = re.sub(r'[_\-\.]', ' ', name).strip()
    
    return re.sub(r'\s+', ' ', name)

def search_tmdb(session, query):
    clean_query = clean_for_search(query)
    if not clean_query: return None
    try:
        resp = session.get("https://api.themoviedb.org/3/search/tv", params={"query": clean_query}).json()
        if resp.get("results"): return resp["results"][0]
    except Exception as e:
        print(f"  ❌ TMDB搜索失败 ({clean_query}): {e}")
    return None

def parse_season_episode(file_path):
    filename = file_path.stem
    search_target = f"{file_path.parent.name} {filename}"

    # 🌟 核心补丁 1：绝对的 SxxExx 霸权
    std_match = re.search(r'(?i)S(\d{1,2})E(\d{1,3})', filename) 
    if std_match:
        return int(std_match.group(1)), int(std_match.group(2))

    if re.search(r'(?i)(NCOP|NCED|Menu)', filename): return None, None
    
    # 🌟 核心补丁 2：原生态 OVA 抓取
    sp_match = re.search(r'(?i)\b(?:SP|OVA|OAD)\s*(\d{1,2})?\b', filename)
    if sp_match:
        episode_num = int(sp_match.group(1)) if sp_match.group(1) else 1
        return 0, episode_num

    season_patterns = [
        r'第([一二三四五六七八九十\d]+)季',
        r'(?i)Season\s*(\d+)',
        r'(?i)(\d+)\s*(?:st|nd|rd|th)\s*Season', 
        r'(?i)S(\d{1,2})',
        r'\s([IVXLCDM]+)\s',
        r'\s(0?[2-9])\s*(?=\[|-)'
    ]
    season_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    season = 1
    
    for pattern in season_patterns:
        match = re.search(pattern, search_target, re.IGNORECASE)
        if match:
            season_str = match.group(1).upper()
            if season_str in season_map: season = season_map[season_str]
            elif re.match(r'^[IVXLCDM]+$', season_str):
                season = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10}.get(season_str, 1)
            else: season = int(season_str)
            break

    temp_name = re.sub(r'(?i)1080p|720p|2160p|4k|x264|x265|hevc|ma10p|h264|h265|20\d{2}', '', filename)
    
    ep_patterns = [
        r'\[(\d{2,3})(?:v\d)?\]', 
        r'(?:EP?|第)\s*(\d{1,3})\s*(?:话|集|v\d)?', 
        r'-\s*(\d{2,3})\s',
        r'\s(\d{2,3})\b'
    ]
    
    episode = None
    for pattern in ep_patterns:
        ep_match = re.search(pattern, temp_name, re.IGNORECASE)
        if ep_match:
            episode = int(ep_match.group(1))
            break
            
    return season, episode

def get_base_stem(filename):
    name = filename
    if name.lower().endswith(('.ass', '.srt', '.mkv', '.mp4')): name = name.rsplit('.', 1)[0]
    lang_tags = ['.jpsc', '.jptc', '.sc', '.tc', '.chs', '.cht', '.zh-cn', '.zh-tw', '.cn', '.tw']
    for tag in lang_tags:
        if name.lower().endswith(tag):
            name = name[:-len(tag)]
            break
    return name

def get_video_info(file_path):
    try:
        size_kb = os.path.getsize(file_path) * 8 / 1000
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration:stream=codec_name",
            "-of", "json", str(file_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        info = json.loads(result.stdout)

        duration = float(info.get('format', {}).get('duration', 0))
        codec = info.get('streams', [{}])[0].get('codec_name', '').lower()

        bitrate = (size_kb / duration) if duration > 0 else 9999
        return bitrate, codec
    except Exception:
        return 9999, "unknown"

def process_file_group(session, base_stem, files):
    print(f"\n📁 处理系列: {base_stem}")
    files.sort(key=lambda x: 0 if x.suffix.lower() in {'.mkv', '.mp4'} else 1)

    group_tmdb_info = None  

    for file_path in files:
        season, episode = parse_season_episode(file_path)
        
        # 🌟 修复陷阱：严谨判断 None，强力放行第 0 季！
        if season is None or episode is None:
            print(f"  ⏭️ {file_path.name}: 无法解析常规季/集信息，跳过")
            continue

        tv_id = cn_name = ""
        cache_file = file_path.parent.joinpath(f".tmdb_{base_stem}.cache")

        if file_path.suffix.lower() in {'.mkv', '.mp4'}:
            if group_tmdb_info is None:
                group_tmdb_info = search_tmdb(session, file_path.stem)
                if not group_tmdb_info:
                    print(f"  🔍 [触发备用搜索] 子文件名未匹配，正在尝试通过父文件夹名搜索...")
                    group_tmdb_info = search_tmdb(session, file_path.parent.name)
            
            tmdb_info = group_tmdb_info
            
            if not tmdb_info:
                print(f"  ❌ {file_path.name}: TMDB未找到匹配，跳过")
                continue
            tv_id, cn_name = tmdb_info["id"], tmdb_info["name"]

            bitrate, codec = get_video_info(file_path)

            if codec == "av1":
                print(f"  🌟 编码特权: 探测到 {codec.upper()} 格式 | 免检直通，送入【HDD免压直通库】")
                target_base = FINAL_LIBRARY_DIR
            elif bitrate < BITRATE_THRESHOLD_KBPS:
                print(f"  ⏩ 码率安检: {bitrate:.0f} kbps < {BITRATE_THRESHOLD_KBPS} ({codec.upper()}) | 送入【HDD免压直通库】")
                target_base = FINAL_LIBRARY_DIR
            else:
                print(f"  🏋️ 码率超标: {bitrate:.0f} kbps ≥ {BITRATE_THRESHOLD_KBPS} ({codec.upper()}) | 送入【NVMe压制加工厂】")
                target_base = ENCODE_TARGET_DIR

            cache_file.write_text(f"{tv_id}|{cn_name}|{target_base}", encoding="utf-8")
        else:
            if not cache_file.exists(): continue
            cache_data = cache_file.read_text(encoding="utf-8").split("|")
            tv_id, cn_name = cache_data[0], cache_data[1]
            target_base = Path(cache_data[2]) if len(cache_data) > 2 else ENCODE_TARGET_DIR

        safe_cn_name = re.sub(r'[\\/*?:"<>|]', '-', cn_name)
        season_dir = target_base / safe_cn_name / f"Season {str(season).zfill(2)}"

        if not DRY_RUN: season_dir.mkdir(parents=True, exist_ok=True)

        new_stem = f"{safe_cn_name} S{str(season).zfill(2)}E{str(episode).zfill(2)}"
        final_suffix = file_path.suffix
        name_lower = file_path.name.lower()
        if '.ass' in name_lower or '.srt' in name_lower:
            if 'jpsc' in name_lower or '.sc' in name_lower or 'chs' in name_lower or 'zh-cn' in name_lower: final_suffix = '.zh-CN' + file_path.suffix
            elif 'jptc' in name_lower or '.tc' in name_lower or 'cht' in name_lower or 'zh-tw' in name_lower: final_suffix = '.zh-TW' + file_path.suffix

        target_path = season_dir / f"{new_stem}{final_suffix}"
        if target_path.exists(): continue
        if DRY_RUN: print(f"  🔍 [测试] {file_path.name} -> {target_path}"); continue

        try:
            if FILE_ACTION == "copy": shutil.copy2(file_path, target_path)
            else: shutil.move(file_path, target_path)
            print(f"  ✅ 分拣成功: {target_path.name}")

            if target_base == ENCODE_TARGET_DIR and file_path.suffix.lower() in {'.mkv', '.mp4'}:
                with open(ENCODE_LIST_PATH, "a", encoding="utf-8") as f:
                    f.write(str(target_path) + "\n")
        except Exception as e:
            print(f"  ❌ 操作失败: {e}")

        if file_path.suffix.lower() in {'.mkv', '.mp4'}: time.sleep(0.3)

def main():
    if len(sys.argv) < 2: sys.exit(1)
    args = sys.argv[1:]
    if "--dry-run" in args:
        global DRY_RUN
        DRY_RUN = True
        args.remove("--dry-run")
    session = get_tmdb_session()
    files_to_process = []
    valid_exts = {'.mkv', '.mp4', '.ass', '.srt'}
    for arg in args:
        path = Path(arg)
        if path.is_file() and path.suffix.lower() in valid_exts: files_to_process.append(path)
        elif path.is_dir():
            for file in path.rglob('*'):
                if file.is_file() and file.suffix.lower() in valid_exts: files_to_process.append(file)
    groups = {}
    for f in files_to_process:
        base_stem = get_base_stem(f.name)
        groups.setdefault(base_stem, []).append(f)
    for base_stem, files in groups.items(): process_file_group(session, base_stem, files)
    for arg in args:
        path = Path(arg)
        search_dir = path if path.is_dir() else path.parent
        for cache in search_dir.rglob(".tmdb_*.cache"): cache.unlink(missing_ok=True)
    print("\n===== 所有任务处理完成 =====")

if __name__ == "__main__": main()
