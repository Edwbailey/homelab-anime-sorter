#!/bin/bash
# 宿主机上看到的触发文件路径
TRIGGER_FILE="/data/hdd/downloads/anime_trigger.list"

# 如果文件不存在则创建，并赋予读写权限
touch "$TRIGGER_FILE"
chmod 666 "$TRIGGER_FILE"

echo "=== 动漫重命名监听服务已启动 ==="
echo "监听目标: $TRIGGER_FILE"

# 持续监听文件末尾新增的内容
tail -F "$TRIGGER_FILE" | while read filepath; do
    # 排除空行
    if [ -n "$filepath" ]; then
        # 【核心翻译】将容器路径转为宿主机物理路径
        real_path=$(echo "$filepath" | sed 's|^/downloads|/data/hdd/downloads|')
        
        echo "----------------------------------------"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 新番下载完成！"
        echo "收到容器路径: $filepath"
        echo "转换物理路径: $real_path"
        
        # 执行 Python 脚本，并传入精准的文件路径
        /usr/bin/python3 /home/bailey/rename_anime.py "$real_path"
        
        echo "处理完毕等待下一次任务..."
    fi
done
