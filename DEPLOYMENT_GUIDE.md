# Land### 核心文件
- `Dockerfile` - Docker 镜像构建文件，集成数据库检测工具
- `docker-compose.yml` - Docker Compose 配置
- `docker-healthcheck.sh` - 健康检查脚本
- `docker-entrypoint.sh` - 启动脚本cker 部署指南

这个增强版的 Docker 配置集成了数据库健康检查功能，确保 LandPPT 应用在生产环境中稳定运行�?

## 📋 文件清单

### 核心文件
- `Dockerfile.enhanced` - 增强�?Dockerfile，集成数据库检测工�?
- `docker-compose.yml` - Docker Compose 配置
- `docker-healthcheck-enhanced.sh` - 增强健康检查脚�?
- `docker-entrypoint-enhanced.sh` - 增强启动脚本
- `landppt-deploy.sh` - 部署管理脚本

### 数据库工�?
- `database_health_check.py` - 完整数据库健康检�?
- `quick_db_check.py` - 快速数据库检�?
- `database_diagnosis.py` - 数据库诊断工�?
- `simple_performance_test.py` - 性能测试工具

## 🚀 快速开�?

### 1. 准备环境

确保系统已安装：
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ （用于本地测试）

### 2. 克隆并配�?

```bash
# 克隆项目
git clone <your-repo>
cd landppt

# 复制数据库检测工具到项目目录
cp database_health_check.py database_diagnosis.py ./

# 配置文件已经是最新版本，无需复制
# Dockerfile, docker-healthcheck.sh, docker-entrypoint.sh 已经是增强版本

# 设置执行权限
chmod +x docker-healthcheck.sh docker-entrypoint.sh
```

### 3. 部署服务

使用管理脚本进行部署�?

```bash
# 运行数据库预检�?
./landppt-deploy.sh db-check

# 构建镜像
./landppt-deploy.sh build

# 启动服务
./landppt-deploy.sh start

# 查看状�?
./landppt-deploy.sh status
```

或者直接使�?Docker Compose�?

```bash
# 构建并启�?
docker-compose up -d --build

# 查看日志
docker-compose logs -f
```

## 🔧 配置说明

### 环境变量

�?`docker-compose.yml` 中已预配置了以下环境变量�?

#### 数据库配�?
```yaml
- DB_HOST=your-supabase-host
- DB_PORT=5432
- DB_NAME=postgres
- DB_USER=your_db_user
- DB_PASSWORD=your_secure_password
```

#### Supabase 配置
```yaml
- SUPABASE_URL=https://your-project.supabase.co
- SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
- SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 健康检查配�?
```yaml
- SKIP_DB_CHECK=false          # 是否跳过数据库检�?
- REQUIRE_DB=true              # 是否要求数据库连接成�?
- RUN_DB_SCHEMA_CHECK=true     # 是否运行 Schema 检�?
```

### 卷挂�?

持久化数据通过以下卷挂载：
- `landppt_data` - 应用数据
- `landppt_uploads` - 上传文件
- `landppt_temp` - 临时文件
- `landppt_logs` - 日志文件
- `playwright_cache` - Playwright 浏览器缓�?

## 🏥 健康检�?

### 多层健康检�?

1. **应用层检�?* - 检�?HTTP 端点响应
2. **数据库层检�?* - 验证数据库连接和基本查询
3. **系统层检�?* - 监控磁盘空间、内存使用率
4. **文件系统检�?* - 验证关键目录权限

### 健康检查时�?

- **检查间�?*: 30�?
- **超时时间**: 15�?
- **启动�?*: 60�?
- **重试次数**: 3�?

## 📊 监控和管�?

### 使用管理脚本

```bash
# 查看服务状�?
./landppt-deploy.sh status

# 查看实时日志
./landppt-deploy.sh logs

# 运行数据库健康检�?
./landppt-deploy.sh db-check

# 运行性能测试
./landppt-deploy.sh db-test

# 重启服务
./landppt-deploy.sh restart

# 备份数据
./landppt-deploy.sh backup

# 清理资源
./landppt-deploy.sh cleanup
```

### 监控服务

启动独立的数据库监控服务�?

```bash
# 启动监控服务
./landppt-deploy.sh monitor

# 或使�?Docker Compose
docker-compose --profile monitoring up -d db-monitor
```

## 🔍 故障排除

### 常见问题

#### 1. 数据库连接失�?

**症状**: 容器启动失败，日志显示数据库连接错误

**解决方案**:
```bash
# 运行数据库诊�?
python3 database_diagnosis.py

# 检查网络连�?
docker-compose exec landppt ping your-supabase-host

# 验证环境变量
docker-compose exec landppt env | grep DB_
```

#### 2. 健康检查失�?

**症状**: 容器显示 unhealthy 状�?

**解决方案**:
```bash
# 查看健康检查日�?
docker-compose logs landppt | grep health

# 手动运行健康检�?
docker-compose exec landppt ./docker-healthcheck-enhanced.sh

# 检查应用状�?
curl http://localhost:8000/health
```

#### 3. 性能问题

**症状**: 应用响应缓慢

**解决方案**:
```bash
# 运行性能测试
./landppt-deploy.sh db-test

# 检查资源使�?
docker stats

# 查看详细日志
docker-compose logs --tail=100 landppt
```

### 调试模式

启用详细日志记录�?

```bash
# 修改 docker-compose.yml
environment:
  - DEBUG=true
  - LOG_LEVEL=DEBUG

# 重启服务
./landppt-deploy.sh restart
```

## 🔒 安全注意事项

### 生产环境配置

1. **更换默认密码**
   ```bash
   # 生成新密�?
   openssl rand -base64 32
   
   # �?Supabase 控制台更�?your_db_user 密码
   # 更新 docker-compose.yml 中的 DB_PASSWORD
   ```

2. **使用环境文件**
   ```bash
   # 创建 .env 文件
   cat > .env << EOF
   DB_PASSWORD=your_secure_password
   SUPABASE_SERVICE_KEY=your_service_key
   EOF
   
   # 修改 docker-compose.yml 使用 env_file
   env_file:
     - .env
   ```

3. **限制网络访问**
   ```bash
   # 使用防火墙限制端口访�?
   sudo ufw allow from trusted_ip to any port 8000
   ```

### 备份和恢�?

#### 自动备份

```bash
# 创建定时备份脚本
cat > backup-cron.sh << 'EOF'
#!/bin/bash
cd /path/to/landppt
./landppt-deploy.sh backup
find backup_* -type d -mtime +7 -exec rm -rf {} \;
EOF

# 添加�?crontab
echo "0 2 * * * /path/to/backup-cron.sh" | crontab -
```

#### 恢复数据

```bash
# 列出备份
ls -la backup_*/

# 恢复指定备份
./landppt-deploy.sh restore backup_20241213_020000/landppt_data.tar.gz
```

## 📈 性能优化

### 资源限制

根据服务器配置调整资源限制：

```yaml
deploy:
  resources:
    limits:
      memory: 4G      # 根据需要调�?
      cpus: '2.0'     # 根据需要调�?
    reservations:
      memory: 1G
      cpus: '0.5'
```

### 缓存优化

```yaml
environment:
  - PYTHONOPTIMIZE=2          # 启用最大优�?
  - PYTHONHASHSEED=random     # 随机哈希种子
  - PYTHONGC=1               # 启用垃圾回收
```

## 🎯 生产部署检查清�?

- [ ] 数据库初始化脚本已运�?
- [ ] 数据库健康检查通过
- [ ] 环境变量已正确配�?
- [ ] 存储桶权限已设置
- [ ] 默认密码已更�?
- [ ] 防火墙规则已配置
- [ ] 监控告警已设�?
- [ ] 备份策略已实�?
- [ ] SSL 证书已配置（如需要）
- [ ] 日志轮转已设�?

---

🎉 **恭喜！您�?LandPPT 应用现在具备了企业级的数据库健康检查和监控能力�?*
