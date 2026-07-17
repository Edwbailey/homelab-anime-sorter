#!/bin/bash
# 监听由 Python 发来的高码率视频压制任务
ENCODE_LIST="/data/nvme/encode_trigger.list"

touch "$ENCODE_LIST"
chmod 666 "$ENCODE_LIST"

echo "=== 🎬 13500T 硬件压制排队系统已启动 ==="

tail -F "$ENCODE_LIST" | while read -r filepath; do
    if [ -n "$filepath" ]; then
        echo "----------------------------------------"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 监听到高码率新番，唤醒核显..."
        
        # 调用改造后的单集精确硬压脚本
        /bin/bash /home/bailey/encode/hevc.sh "$filepath"
        
        if [ $? -eq 0 ]; then
            echo "🗑️ 压制成功且已安全入库，销毁 NVMe 原盘: $filepath"
            rm -f "$filepath"
        else
            echo "❌ 压制失败，保留原盘供排查。"
        fi
        echo "✅ 处理完毕，等待下一集排队任务..."
    fi
done
