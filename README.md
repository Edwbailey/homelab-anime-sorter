# Homelab Anime Sorter

这是一个基于 Linux 原生环境的自动化动漫分拣与处理流水线。利用 Docker + Systemd + Python 实现全自动刮削、重命名与归档。



## 核心架构
1. **下载层**: qBittorrent (Docker) 将文件下载至独立 NVMe 缓存盘。
2. **信号层**: 完成后通过 shell 脚本触发 `anime_trigger.list` 信号。
3. **监控层**: Systemd 守护进程 (watcher.sh) 实时监听信号并完成物理路径映射。
4. **处理层**: Python 脚本调用 TMDB API 进行刮削，并将文件处理至 SSD 暂存区。

## 特性
- **全自动处理**: 种子下载完成秒级触发，无需人工介入。
- **环境解耦**: 逻辑完全运行在宿主机，不受 Docker 容器更新影响。
- **精准匹配**: 适配 VCB/7ACG 等复杂命名，支持多季、剧场版。

## 快速部署

### 1. 准备工作
确保宿主机已安装 Python 环境：
```bash
sudo apt update && sudo apt install python3 python3-pip
pip3 install requests
2. 初始化项目
Bash
git clone [https://github.com/Edwbailey/homelab-anime-sorter.git](https://github.com/Edwbailey/homelab-anime-sorter.git)
cd homelab-anime-sorter
3. 配置守护服务
Bash
# 安装 Systemd 服务
sudo cp anime-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now anime-watcher

# 部署中转脚本（请根据你的实际配置路径修改）
sudo cp trigger.sh /opt/docker/qbittorrent/config/trigger.sh
sudo chmod +x /opt/docker/qbittorrent/config/trigger.sh
4. qBittorrent 设置
在 WebUI 设置 -> 下载 -> “下载完成后运行外部程序”中填入：

Bash
sh /config/trigger.sh "%L" "%F" 

同时在 qB 中新建分类 unRename，下载任务时务必选择该分类。

