# 数据库读写检测系统部署指南

## 概览
本增强版 FlowSlide 集成了全面的数据库健康检查功能，用于监控 PostgreSQL（含 Supabase、Neon、RDS 等）的读写性能和连接状态。

## 🔧 系统组件

### 数据库监控工具
1. database_health_check.py - 全面健康检查
   - 基础连接测试
   - 模式访问验证
   - 应用用户连接测试
   - 存储 API 验证
   - 性能基准测试

2. quick_db_check.py - 快速日常监控
   - 轻量级连接验证
   - 读写操作测试
   - 存储服务检查

3. database_diagnosis.py - 详细诊断工具
   - 深度连接分析
   - 错误诊断
   - 配置验证

4. simple_performance_test.py - 性能验证
   - 查询响应时间
   - 数据传输速度
   - 并发连接测试

### Docker 集成
- Dockerfile.ci-compatible - CI/CD 兼容的生产镜像
- docker-compose.yml - 完整的部署配置
- Health Check Scripts - 智能健康检查系统

## 🚀 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <your-repo>
cd FlowSlide

# 复制环境配置
cp .env.example .env
```

### 2. 配置数据库连接
编辑 .env 文件：
```env
# 数据库配置
DB_HOST=your-supabase-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your-secure-password

# 通用 API（如使用 Supabase，可将 API_URL 设置为项目 URL）
API_URL=https://your-project.supabase.co
API_ANON_KEY=your-anon-key
API_SERVICE_KEY=your-service-role-key
```

### 3. 本地运行数据库检查
```bash
# 快速检查
python quick_db_check.py

# 全面健康检查
python database_health_check.py

# 诊断问题
python database_diagnosis.py

# 性能测试
python simple_performance_test.py
```

### 4. Docker 部署
```bash
# 构建增强版镜像
# 使用标准 Dockerfile 构建
docker build -t flowslide-enhanced .

# 使用 docker-compose 部署
docker-compose up -d

# 检查服务状态
docker-compose ps
docker-compose logs flowslide
```

## 📊 监控功能

### 健康检查指标
1. 连接状态
   - 数据库连接可用
   - 认证状态验证
   - 网络延迟测试

2. 数据操作
   - 读取操作响应时间
   - 写入操作成功率
   - 事务完整性验证

3. 存储服务
   - 文件上传/下载功能
   - 存储配额检查
   - API 响应状态

4. 性能指标
   - 查询执行时间
   - 并发连接处理
   - 内存使用率

### 监控频率建议
- 生产环境：每 30 分钟执行一次 quick_db_check.py
- 开发环境：每次部署后执行 database_health_check.py
- 故障排查：使用 database_diagnosis.py 进行详细分析

## 🔄 CI/CD 集成

### GitHub Actions 工作流
系统包含专用的工作流（.github/workflows/database-health-check.yml）：
1. 自动化测试
   - 数据库工具功能验证
   - Docker 镜像构建测试
   - 安全漏洞扫描

2. 多环境部署
   - 开发分支、预发布环境
   - 主分支、生产环境
   - 自动化健康检查

3. 质量保证
   - 代码安全扫描
   - 容器镜像验证
   - 部署后健康检查

### 触发条件
- 推送到 main/develop 分支
- 数据库相关文件修改
- Docker 配置文件变更

## 🛠️ 故障排查

### 常见问题

1. 连接失败
```bash
# 检查数据库配置
python database_diagnosis.py

# 验证网络连接
telnet your-supabase-host 5432
```

2. 认证错误
```bash
# 验证用户权限
python -c "
import psycopg2
conn = psycopg2.connect(host='$DB_HOST', database='$DB_NAME', user='$DB_USER', password='$DB_PASSWORD')
print('认证成功')
"
```

3. 性能问题
```bash
# 执行性能基准测试
python simple_performance_test.py

# 分析慢查询
python database_diagnosis.py
```

### 日志分析
```bash
# 查看应用日志
docker-compose logs flowslide

# 查看健康检查日志
docker exec flowslide-container cat /app/logs/health-check.log

# 实时监控
docker-compose logs -f flowslide
```

## 📈 性能优化

### 数据库优化建议
1. 连接池配置
   - 最大连接数：20
   - 连接超时：30 秒
   - 空闲连接回收：10 分钟

2. 查询优化
   - 使用索引优化查询
   - 批量操作减少往返
   - 缓存频繁查询结果

3. 监控指标
   - 平均响应时间 < 100ms
   - 连接成功率 > 99.9%
   - 存储 API 响应 < 500ms

### Docker 资源配置
```yaml
services:
  flowslide:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

## 🔒 安全考虑
1. 环境变量
   - 使用 Docker secrets 管理敏感信息
   - 定期轮换数据库密码
   - 限制 API 密钥权限

2. 网络安全
   - 使用 SSL/TLS 连接数据库
   - 配置防火墙规则
   - 限制数据库访问 IP

3. 监控告警
   - 异常连接尝试告警
   - 性能指标阈值告警
   - 安全事件记录

## 📞 支持与维护

### 定期维护任务
- 每周检查数据库性能指标
- 每月更新依赖包版本
- 每季度进行安全审计

### 监控仪表板
- Grafana + Prometheus（性能监控）
- ELK Stack（日志分析）
- Supabase Dashboard（数据库监控）

---

## 📋 检查清单

部署前确认：
- [ ] 数据库连接配置正确
- [ ] 环境变量设置完整
- [ ] Docker 镜像构建成功
- [ ] 健康检查脚本可执行
- [ ] 监控工具正常运行
- [ ] 备份策略已配置
- [ ] 告警规则已设置

部署后验证：
- [ ] 应用服务正常启动
- [ ] 数据库连接测试通过
- [ ] 存储 API 功能正常
- [ ] 性能指标符合预期
- [ ] 健康检查定期执行
- [ ] 日志记录正常
- [ ] 监控告警生效
