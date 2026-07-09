#!/bin/sh
# 接收 qB 传过来的分类名和文件路径
CATEGORY="$1"
FILEPATH="$2"

# 记录一条日志到 config 目录，方便排错
echo "[$(date)] 收到下载完成通知: 分类=$CATEGORY, 路径=$FILEPATH" >> /config/trigger_debug.log

# 判断分类是否匹配（注意：这里的 unRename 必须和你在 qB 里建的分类名一模一样）
if [ "$CATEGORY" = "unRename" ]; then
    echo "$FILEPATH" >> /downloads/anime_trigger.list
    echo "  -> 分类匹配，已写入 trigger.list" >> /config/trigger_debug.log
else
    echo "  -> 分类不匹配，忽略" >> /config/trigger_debug.log
fi
