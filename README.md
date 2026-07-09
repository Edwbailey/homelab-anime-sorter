# Homelab Anime Sorter

这是一个基于 Linux 原生环境的自动化动漫分拣与处理流水线。
设计初衷是保护机械硬盘寿命，通过独立缓存盘下载，利用 Docker + Systemd + Python 实现全自动刮削、重命名与归档。

## 核心架构


## 特性
- **全自动处理**: qBittorrent 下载完成后秒级触发。
- **环境隔离**: 逻辑运行在宿主机，Docker 更新不影响环境。
- **IO 保护**: 支持缓存盘与大容量机械盘的跨文件系统分拣。
- **精准匹配**: 深度适配 VCB/7ACG 等命名格式，自动对接 TMDB。

## 快速部署

1. **准备环境**: 确保宿主机已安装 `python3` 及 `requests` 库。
2. **下载项目**:
   ```bash
   git clone [https://github.com/Edwbailey/homelab-anime-sorter.git](https://github.com/Edwbailey/homelab-anime-sorter.git)
   cd homelab-anime-sorter
   sudo cp -a anime-watcher.service /etc/systemd/system/anime-watcher.service 
   sudo systemctl damon-reload
   sudo systemctl enable --now anime-watchersudo
   cp -a trigger.sh /opt/docker/qbittorrent/config/trigger.sh
   配置 Systemd: 将仓库内的 watcher.sh 配置为守护进程，确保 WorkingDirectory 指向此目录。
