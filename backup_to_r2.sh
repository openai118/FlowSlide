#!/bin/bash
# LandPPT 自动备份到 Cloudflare R2

set -e
echo "🔄 开始备份 LandPPT 数据到 Cloudflare R2..."

# 检查必要的环境变量
if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ] || [ -z "$R2_ENDPOINT" ] || [ -z "$R2_BUCKET_NAME" ]; then
    echo "⚠️ R2 环境变量未完整配置，跳过备份"
    exit 0
fi

# 配置 rclone for Cloudflare R2
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY
export RCLONE_CONFIG_R2_ENDPOINT=$R2_ENDPOINT

# 生成备份时间戳
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# 备份应用数据
if [ -d "/app/data" ]; then
    echo "📦 备份应用数据..."
    rclone sync /app/data r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/data \
        --progress --log-level INFO \
        --exclude "*.tmp" --exclude "cache/**" --exclude "*.lock"
fi

# 备份研究报告
if [ -d "/app/research_reports" ]; then
    echo "📊 备份研究报告..."
    rclone sync /app/research_reports r2:${R2_BUCKET_NAME}/backups/${BACKUP_DATE}/research_reports \
        --progress --log-level INFO
fi

echo "✅ 备份完成！备份路径: backups/${BACKUP_DATE}/"
