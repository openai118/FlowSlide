# FlowSlide 部署指南（增强版节选）

- Dockerfile - Docker 镜像构建文件，集成数据库检测工具
- docker-compose.yml - Docker Compose 配置
- docker-healthcheck.sh - 健康检查脚本
- docker-entrypoint.sh - 启动脚本

本增强版 Docker 配置集成了数据库健康检查功能，确保 FlowSlide 应用在生产环境中稳定运行。

## 📋 文件清单

### 核心文件
- Dockerfile - 标准 Dockerfile（已集成健康检查钩子）
- docker-compose.yml - Docker Compose 配置
- docker-healthcheck.sh - 健康检查脚本
- docker-entrypoint.sh - 启动脚本

### 数据库工具
- database_health_check.py - 完整数据库健康检查
- quick_db_check.py - 快速数据库检查
- database_diagnosis.py - 数据库诊断工具
- simple_performance_test.py - 性能测试工具

## 🚀 快速开始

### 1. 准备环境
确保系统已安装：
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+（用于本地测试）

### 2. 克隆并配置
```bash
# 克隆项目
git clone <your-repo>
cd flowslide

# 复制数据库检测工具到项目目录
cp database_health_check.py database_diagnosis.py ./

# 配置文件已是增强版
# Dockerfile, docker-healthcheck.sh, docker-entrypoint.sh

# 设置执行权限
chmod +x docker-healthcheck.sh docker-entrypoint.sh
```

### 3. 部署服务
使用 Docker Compose：
```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f
```

## 🔧 配置说明

### 环境变量
在 docker-compose.yml 中已预配置以下环境变量：

#### 数据库配置
```yaml
- DB_HOST=your-supabase-host
- DB_PORT=5432
- DB_NAME=postgres
- DB_USER=your_db_user
- DB_PASSWORD=your_secure_password
```

#### API/Supabase 配置
```yaml
- API_URL=https://your-project.supabase.co
- API_ANON_KEY=...
- API_SERVICE_KEY=...
```

#### 健康检查配置
```yaml
- SKIP_DB_CHECK=false          # 是否跳过数据库检查
- REQUIRE_DB=true              # 是否要求数据库连接成功
- RUN_DB_SCHEMA_CHECK=true     # 是否运行 Schema 检查
```

### 卷挂载
持久化数据通过以下卷挂载：
- flowslide_data - 应用数据
- flowslide_uploads - 上传文件
- flowslide_temp - 临时文件
- flowslide_logs - 日志文件
- playwright_cache - Playwright 浏览器缓存

## 🏥 健康检查

### 多层健康检查
1. 应用层检查 - 检查 HTTP 端点响应
2. 数据库层检查 - 验证数据库连接和基本查询
3. 系统层检查 - 监控磁盘空间、内存使用率
4. 文件系统检查 - 验证关键目录权限

### 健康检查时序
- 检查间隔：30 秒
- 超时时间：15 秒
- 启动等待：60 秒
- 重试次数：3 次

## 📈 监控和管理

### 使用管理脚本
```bash
# 查看服务状态
./flowslide-deploy.sh status

# 查看实时日志
./flowslide-deploy.sh logs

# 运行数据库健康检查
./flowslide-deploy.sh db-check

# 运行性能测试
./flowslide-deploy.sh db-test

# 重启服务
./flowslide-deploy.sh restart

# 备份数据
./flowslide-deploy.sh backup

# 清理资源
./flowslide-deploy.sh cleanup
```

### 监控服务
```bash
# 启动监控服务
./flowslide-deploy.sh monitor

# 或使用 Docker Compose
docker-compose --profile monitoring up -d db-monitor
```

## 🔍 故障排除

### 常见问题

#### 1. 数据库连接失败
症状：容器启动失败，日志显示数据库连接错误
```bash
# 运行数据库诊断
python3 database_diagnosis.py

# 检查网络连接
docker-compose exec flowslide ping your-supabase-host

# 验证环境变量
docker-compose exec flowslide env | grep DB_
```

#### 2. 健康检查失败
症状：容器显示 unhealthy 状态
```bash
# 查看健康检查日志
docker-compose logs flowslide | grep health

# 手动运行健康检查
docker-compose exec flowslide ./docker-healthcheck.sh

# 检查应用状态
curl http://localhost:8000/health
```

#### 3. 性能问题
症状：应用响应缓慢
```bash
# 运行性能测试
./flowslide-deploy.sh db-test

# 检查资源使用
docker stats

# 查看详细日志
docker-compose logs --tail=100 flowslide
```

### 调试模式
启用详细日志记录：
```bash
# 修改 docker-compose.yml
environment:
  - DEBUG=true
  - LOG_LEVEL=DEBUG

# 重启服务
./flowslide-deploy.sh restart
```

## 🔒 安全注意事项

### 生产环境配置
1. 更换默认密码
```bash
# 生成新密码
openssl rand -base64 32

# 在 Supabase 控制台更改 your_db_user 密码
# 更新 docker-compose.yml 中的 DB_PASSWORD
```

2. 使用环境文件
```bash
# 创建 .env 文件
cat > .env << EOF
DB_PASSWORD=your_secure_password
API_SERVICE_KEY=your_service_key
EOF

# 修改 docker-compose.yml 使用 env_file
env_file:
  - .env
```

3. 限制网络访问
```bash
# 使用防火墙限制端口访问
sudo ufw allow from trusted_ip to any port 8000
```

### 备份和恢复

#### 自动备份
```bash
# 创建定时备份脚本
cat > backup-cron.sh << 'EOF'
#!/bin/bash
cd /path/to/flowslide
./flowslide-deploy.sh backup
find backup_* -type d -mtime +7 -exec rm -rf {} \;
EOF

# 添加到 crontab
echo "0 2 * * * /path/to/backup-cron.sh" | crontab -
```

#### 恢复数据
```bash
# 列出备份
ls -la backup_*/

# 恢复指定备份
./flowslide-deploy.sh restore backup_20241213_020000/flowslide_data.tar.gz
```

## 📈 性能优化

### 资源限制
根据服务器配置调整资源限制：
```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2.0'
    reservations:
      memory: 1G
      cpus: '0.5'
```

### 缓存优化
```yaml
environment:
  - PYTHONOPTIMIZE=2          # 启用最大优化
  - PYTHONHASHSEED=random     # 随机哈希种子
  - PYTHONGC=1                # 启用垃圾回收
```

## 🎯 生产部署检查清单
- [ ] 数据库初始化脚本已运行
- [ ] 数据库健康检查通过
- [ ] 环境变量已正确配置
- [ ] 存储桶权限已设置
- [ ] 默认密码已更改
- [ ] 防火墙规则已配置
- [ ] 监控告警已设置
- [ ] 备份策略已实施
- [ ] SSL 证书已配置（如需要）
- [ ] 日志轮转已设置

---

🎉 恭喜！FlowSlide 应用现在具备了企业级的数据库健康检查和监控能力。

## 🚪 访问入口
- 🏠 首页(公共): http://localhost:8000/home
- 🌐 Web界面(控制台): http://localhost:8000/web
- 📚 API 文档: http://localhost:8000/docs
- 🩺 健康检查: http://localhost:8000/health
