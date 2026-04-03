#!/bin/bash
# ================================================
# 爬虫逆向框架 - 容器启动脚本
# ================================================

set -e

# -------- 颜色定义 --------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# -------- 日志函数 --------
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# -------- 环境检测 --------
log_info "检测环境配置..."

# 检查环境模式
ENV=${ENV:-development}
log_info "运行环境: $ENV"

# -------- 依赖检查 --------
log_info "检查依赖服务..."

# 检查 Redis
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_AUTH="-a $REDIS_PASSWORD"
fi

until redis-cli -h "$REDIS_HOST" -p "${REDIS_PORT:-6379}" $REDIS_AUTH ping &>/dev/null; do
    log_warn "等待 Redis 启动..."
    sleep 2
done
log_info "Redis 连接成功"

# 检查 MongoDB
until mongosh --host "$MONGODB_HOST" --port "${MONGODB_PORT:-27017}" \
    $([ -n "$MONGODB_USER" ] && echo "--username $MONGODB_USER --password $MONGODB_PASSWORD") \
    --eval "db.adminCommand('ping')" &>/dev/null; do
    log_warn "等待 MongoDB 启动..."
    sleep 2
done
log_info "MongoDB 连接成功"

# -------- 初始化操作 --------
log_info "执行初始化操作..."

# 创建必要目录
mkdir -p /app/logs /app/data

# 设置日志目录权限
chown -R crawler:crawler /app/logs /app/data 2>/dev/null || true

# -------- Playwright 浏览器检查 --------
log_info "检查 Playwright 浏览器..."

if [ ! -d "$PLAYWRIGHT_BROWSERS_PATH" ]; then
    log_warn "未找到浏览器，将安装..."
    playwright install --with-deps chromium
else
    log_info "浏览器已安装"
fi

# -------- 生产模式特殊处理 --------
if [ "$ENV" = "production" ]; then
    log_info "生产模式配置..."

    # 禁用调试
    export PYTHONDONTWRITEBYTECODE=1
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

    # 设置严格日志级别
    export LOG_LEVEL=${LOG_LEVEL:-WARNING}
fi

# -------- 启动应用 --------
log_info "启动应用: $@"

exec "$@"
