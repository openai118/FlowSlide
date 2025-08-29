# FlowSlide 动态部署模式切换系统

## 概述

FlowSlide 动态部署模式切换系统支持在四种部署模式之间进行无缝切换：

- **LOCAL_ONLY**: 本地SQLite数据库，无云存储
- **LOCAL_EXTERNAL**: 外部PostgreSQL/MySQL数据库，无云存储
- **LOCAL_R2**: 本地SQLite数据库 + Cloudflare R2云存储
- **LOCAL_EXTERNAL_R2**: 外部数据库 + Cloudflare R2云存储

## 核心组件

### 1. 部署模式管理器 (DeploymentModeManager)
- 自动检测当前部署模式
- 管理模式切换流程
- 提供安全切换机制
- 支持回滚和错误恢复

### 2. 配置管理器 (DeploymentConfigManager)
- 验证模式配置
- 管理切换参数
- 提供配置模板

### 3. REST API接口
- 模式状态查询
- 手动模式切换
- 配置验证
- 系统监控

## 快速开始

### 1. 环境配置

根据目标模式设置环境变量：

```bash
# LOCAL_ONLY模式
export DATABASE_URL="sqlite:///./data/flowslide.db"
unset R2_ACCESS_KEY_ID

# LOCAL_EXTERNAL模式
export DATABASE_URL="postgresql://user:pass@host:5432/db"
unset R2_ACCESS_KEY_ID

# LOCAL_R2模式
export DATABASE_URL="sqlite:///./data/flowslide.db"
export R2_ACCESS_KEY_ID="your_key"
export R2_SECRET_ACCESS_KEY="your_secret"

# LOCAL_EXTERNAL_R2模式
export DATABASE_URL="postgresql://user:pass@host:5432/db"
export R2_ACCESS_KEY_ID="your_key"
export R2_SECRET_ACCESS_KEY="your_secret"
```

### 2. 启动服务

```bash
python -m src.flowslide.main
```

### 3. 验证模式

```bash
curl http://localhost:8000/api/deployment/mode
```

## API 端点

### 获取当前模式
```http
GET /api/deployment/mode
```

响应：
```json
{
  "mode": "local_external_r2",
  "status": "active",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 验证配置
```http
POST /api/deployment/validate
Content-Type: application/json

{
  "mode": "LOCAL_R2",
  "config": {
    "database_url": "sqlite:///./data/flowslide.db",
    "r2_access_key_id": "your_key",
    "r2_secret_access_key": "your_secret"
  }
}
```

### 切换模式
```http
POST /api/deployment/switch
Content-Type: application/json

{
  "target_mode": "LOCAL_EXTERNAL_R2",
  "config": {
    "database_url": "postgresql://...",
    "r2_access_key_id": "your_key"
  },
  "reason": "升级到生产环境"
}
```

### 获取系统状态
```http
GET /api/deployment/status
```

## 模式切换流程

1. **环境变量配置**: 设置目标模式的必需环境变量
2. **配置验证**: 使用API验证新配置的有效性
3. **安全切换**: 执行模式切换，系统会自动处理数据迁移
4. **状态确认**: 验证切换成功，服务正常运行

## 安全特性

- **配置验证**: 切换前验证所有必需配置
- **数据迁移**: 自动处理数据一致性
- **回滚机制**: 切换失败时自动回滚
- **健康检查**: 实时监控系统状态
- **日志记录**: 详细记录所有操作

## 测试和验证

运行完整测试套件：

```bash
python scripts/test_deployment_mode_switching.py
```

查看演示：

```bash
python scripts/demo_deployment_mode_switching.py
```

## 故障排除

### 常见问题

1. **模式检测失败**
   - 检查环境变量是否正确设置
   - 验证数据库连接字符串格式

2. **切换失败**
   - 查看详细错误日志
   - 确认目标模式配置完整
   - 检查系统资源是否充足

3. **数据不一致**
   - 系统会自动处理数据迁移
   - 如有问题，检查迁移日志

### 日志位置

- 应用日志: 查看控制台输出
- 切换历史: `/api/deployment/history`
- 错误详情: 应用程序日志文件

## 最佳实践

1. **生产环境**: 使用LOCAL_EXTERNAL_R2模式获得最佳性能和可靠性
2. **开发环境**: 使用LOCAL_ONLY模式快速启动
3. **测试环境**: 使用LOCAL_R2模式验证云存储功能
4. **备份**: 定期备份数据，切换前创建快照

## 技术支持

如需技术支持，请：
1. 查看详细日志
2. 运行测试脚本验证功能
3. 访问API文档: `http://localhost:8000/docs`
4. 查看项目文档中的故障排除章节
