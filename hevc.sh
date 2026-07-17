#!/bin/bash
# ==========================================
# 视频硬件压制与字幕同步脚本
# ==========================================

IN_BASE="/data/nvme/unDecode"
OUT_DIR="/data/hdd/Decode"   # 压制后目标存放目录
GLOBAL_LOG="$HOME/encode/hevc_transcode.log"

mkdir -p "$(dirname "$GLOBAL_LOG")"

if [ -z "$1" ] || [ ! -f "$1" ]; then
    echo -e "\033[31m❌ 错误：未传入合法的待压制文件路径！\033[0m"
    exit 1
fi

video_path="$1"
file_name=$(basename "$video_path")
dir_name=$(dirname "$video_path")

# 计算相对路径并建立目标目录树
relative_dir=${dir_name#$IN_BASE}
target_dir="${OUT_DIR}${relative_dir}"

mkdir -p "$target_dir"
target_file=$(echo "$target_dir/$file_name" | sed 's#//#/#g')

if [ -f "$target_file" ]; then
    echo -e "\033[33m⏭️  目标路径已存在该文件，跳过: $file_name\033[0m"
    exit 0
fi

echo -e "\033[36m🎬 QSV 硬压启动: \033[0m$relative_dir/$file_name"
echo -e "\n=== START PROCESSING: $file_name ($(date '+%Y-%m-%d %H:%M:%S')) ===" >> "$GLOBAL_LOG"

# 智能音频探测与直通
audio_codec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$video_path" 2>/dev/null | tr -d '\r\n ')

if [ -z "$audio_codec" ]; then
    AUDIO_OPTS=""
elif [[ "$audio_codec" =~ ^(aac|opus|ac3|eac3|mp3)$ ]]; then
    AUDIO_OPTS="-c:a copy"
else
    AUDIO_OPTS="-c:a aac -b:a 192k"
fi

# QSV 10-bit 压制
ffmpeg -nostdin \
    -init_hw_device qsv=hw:/dev/dri/renderD128 -filter_hw_device hw \
    -hwaccel qsv -hwaccel_output_format qsv \
    -i "$video_path" \
    -map 0:v:0 -map 0:a:0? -map 0:s? -map 0:t? \
    -vf "vpp_qsv=format=p010le" \
    -c:v hevc_qsv \
    -profile:v main10 \
    -global_quality 21 \
    -look_ahead_depth 40 \
    -preset slower \
    $AUDIO_OPTS \
    -c:s copy \
    -c:t copy \
    -y "$target_file" -loglevel info >> "$GLOBAL_LOG" 2>&1

if [ $? -eq 0 ]; then
    echo -e "\033[32m   └─ ✅ 压制成功并已入库！\033[0m"
    echo "=== SUCCESS: $file_name ===" >> "$GLOBAL_LOG"

    # 同步搬运外部字幕文件
    base_no_ext="${video_path%.*}"
    find "$dir_name" -type f -name "$(basename "$base_no_ext").*" ! -name "$file_name" | while read -r sub_path; do
        sub_name=$(basename "$sub_path")
        cp "$sub_path" "$target_dir/$sub_name"
        echo "   └─ 📝 字幕已同步: $sub_name" >> "$GLOBAL_LOG"
        rm -f "$sub_path"
    done

    # PushPlus 推送通知
    PUSHPLUS_TOKEN="929d80a6bdfd412f93270a9e0b0addf1"
    curl -s -X POST "http://www.pushplus.plus/send" \
        -H "Content-Type: application/json" \
        -d '{
            "token": "'"${PUSHPLUS_TOKEN}"'",
            "title": "✅ '"$file_name"'",
            "content": "任务完成！<br><br><b>🎬 成功压制：</b> '"$file_name"'",
            "template": "html"
        }' > /dev/null 2>&1

    exit 0
else
    echo -e "\033[31m   └─ ❌ 压制失败，清理残留文件。\033[0m"
    rm -f "$target_file"
    echo "=== FAILED: $file_name ===" >> "$GLOBAL_LOG"
    exit 1
fi
