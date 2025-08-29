# FlowSlide 智能数据同步策略

## 概述

FlowSlide 采用分层数据同步策略，根据数据类型、访问频率和重要性实现差异化同步，确保系统在各种部署环境下都能达到最佳性能和可靠性。

## 设计理念

### 1. 数据分层管理

- **关键数据**：用户认证、项目基本信息 - 实时同步
- **高频数据**：TODO工作流、活跃项目内容 - 定期同步
- **低频数据**：历史版本、模板数据 - 按需同步
- **临时数据**：用户会话 - 仅本地存储

### 2. 智能同步机制

- **增量同步**：只同步变更数据，减少网络开销
- **按需同步**：活跃数据优先同步，提高响应速度
- **批量处理**：合理批处理大小，平衡性能和内存使用
- **容错设计**：同步失败不影响系统运行

### 3. 四种部署模式支持

#### 模式1：只有本地 (LOCAL_ONLY)

```text
┌─────────────┐
│   本地SQLite  │ ← 所有数据存储在这里
└─────────────┘
```

**适用场景**：单机部署、开发环境
**同步策略**：所有数据仅本地存储，无同步开销
**优势**：最快响应速度，最简单部署

#### 模式2：本地+外部数据库 (LOCAL_EXTERNAL)

```text
┌─────────────┐    双向同步    ┌─────────────────┐
│   本地SQLite  │ ◄──────────► │ 外部数据库      │
│ (主数据库)   │               │ (备份/同步)     │
└─────────────┘               └─────────────────┘
```

**适用场景**：团队协作、多服务器部署
**同步策略**：智能双向同步，核心数据实时同步
**优势**：数据可靠性高，协作顺畅

#### 模式3：本地+R2云存储 (LOCAL_R2)

```text
┌─────────────┐    定期备份    ┌─────────────────┐
│   本地SQLite  │ ───────────► │   Cloudflare R2 │
│ (主数据库)   │               │   (云备份)      │
└─────────────┘               └─────────────────┘
```

**适用场景**：个人使用、数据备份需求
**同步策略**：定期备份重要数据到云端
**优势**：成本低，云端数据安全

#### 模式4：本地+外部数据库+R2 (LOCAL_EXTERNAL_R2)

```text
┌─────────────┐    双向同步    ┌─────────────────┐    定期备份
│   本地SQLite  │ ◄──────────► │ 外部数据库      │ ───────────►
│ (主数据库)   │               │ (实时同步)      │             │
└─────────────┘               └─────────────────┘             │
                                                              ▼
                                                      ┌─────────────────┐
                                                      │   Cloudflare R2 │
                                                      │   (最终保障)    │
                                                      └─────────────────┘
```

**适用场景**：企业级部署、高可用性需求
**同步策略**：三层数据保护，最大化可靠性
**优势**：最高可靠性，最强容灾能力

## 数据同步策略详解

### 1. 用户数据 (Users)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external", "external_to_local"],
  "interval_seconds": 60,
  "batch_size": 50,
  "strategy": "full_duplex"
}
```
**同步频率**：每1分钟
**策略说明**：
- 关键数据，必须实时同步
- 支持双向同步和删除同步
- 用于用户认证和权限管理

### 2. 项目数据 (Projects)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external", "external_to_local"],
  "interval_seconds": 300,
  "batch_size": 20,
  "strategy": "full_duplex"
}
```
**同步频率**：每5分钟
**策略说明**：
- 项目基本信息和元数据
- 双向同步，支持协作编辑
- 包含项目状态、所有者等信息

### 3. TODO工作流数据 (Todo Data)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external", "external_to_local"],
  "interval_seconds": 300,
  "batch_size": 30,
  "strategy": "full_duplex"
}
```
**同步频率**：每5分钟
**策略说明**：
- 项目工作流和任务管理
- 实时协作支持
- 包含TODO看板和阶段信息

### 4. 幻灯片数据 (Slide Data)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external"],
  "interval_seconds": 1800,
  "batch_size": 10,
  "strategy": "on_demand"
}
```
**同步频率**：每30分钟（按需）
**策略说明**：
- 幻灯片详细内容和样式
- 按需同步活跃项目
- 大文件内容，减少同步频率

### 5. PPT模板数据 (PPT Templates)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external", "external_to_local"],
  "interval_seconds": 1800,
  "batch_size": 15,
  "strategy": "master_slave"
}
```
**同步频率**：每30分钟
**策略说明**：
- 项目特定的模板
- 主从同步策略
- 支持模板共享和重用

### 6. 全局模板 (Global Templates)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external", "external_to_local"],
  "interval_seconds": 3600,
  "batch_size": 10,
  "strategy": "master_slave"
}
```
**同步频率**：每1小时
**策略说明**：
- 全局母版模板
- 低频同步，减少网络开销
- 主要用于模板分发

### 7. 项目版本 (Project Versions)
```json
{
  "sync_enabled": true,
  "directions": ["local_to_external"],
  "interval_seconds": 3600,
  "batch_size": 5,
  "strategy": "backup_only"
}
```
**同步频率**：每1小时
**策略说明**：
- 版本历史记录
- 仅备份到外部，不双向同步
- 用于数据恢复和审计

### 8. 用户会话 (User Sessions)
```json
{
  "sync_enabled": false,
  "directions": [],
  "interval_seconds": 0,
  "batch_size": 0,
  "strategy": "local_only"
}
```
**同步频率**：不同步
**策略说明**：
- 临时会话数据
- 仅保存在本地
- 提高性能和隐私保护

## 性能优化策略

### 1. 多层同步间隔
- **快速同步** (60秒)：关键数据 (用户)
- **定期同步** (5分钟)：高频数据 (项目、TODO)
- **慢速同步** (30分钟-1小时)：低频数据 (模板、版本)

### 2. 智能批处理
- **大批量** (50)：用户数据，高频小记录
- **中批量** (20-30)：项目和TODO数据
- **小批量** (5-15)：大文件内容和版本数据

### 3. 按需同步机制
- **热点数据检测**：跟踪最近访问的项目
- **智能预加载**：提前同步可能需要的数据
- **延迟同步**：非活跃数据延迟同步

### 4. 容错和恢复
- **断点续传**：支持同步中断后继续
- **版本控制**：数据冲突时的版本管理
- **回滚机制**：同步失败时的自动回滚

## 配置方法

### 环境变量配置

```bash
# 启用数据同步
ENABLE_DATA_SYNC=true

# 同步方向 (可选)
SYNC_DIRECTIONS="local_to_external,external_to_local"

# 同步间隔 (可选)
SYNC_INTERVAL=300
FAST_SYNC_INTERVAL=60
SLOW_SYNC_INTERVAL=3600

# 外部数据库
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# R2云存储
R2_ACCESS_KEY_ID="your_access_key"
R2_SECRET_ACCESS_KEY="your_secret_key"
R2_ENDPOINT="https://your-account.r2.cloudflarestorage.com"
R2_BUCKET_NAME="your-bucket"
```

### 程序化配置

```python
from flowslide.core.sync_strategy_config import sync_strategy_config

# 获取当前部署模式
deployment_info = sync_strategy_config.get_deployment_info()

# 获取特定数据类型的同步策略
user_strategy = sync_strategy_config.get_strategy_for_data_type("users")

# 检查同步是否启用
is_sync_enabled = sync_strategy_config.is_sync_enabled_for_type("projects")
```

## 监控和维护

### 同步状态监控
```python
from flowslide.services.smart_data_sync_service import get_smart_sync_status

# 获取同步状态
status = await get_smart_sync_status()
print(f"同步运行状态: {status['running']}")
print(f"最后同步时间: {status['last_sync']}")
print(f"热点项目数量: {status['hot_projects_count']}")
```

### 性能指标
- **同步延迟**：数据变更到同步完成的平均时间
- **同步成功率**：同步操作的成功率统计
- **网络开销**：同步产生的网络流量统计
- **存储效率**：数据压缩和去重效果

## 最佳实践

### 1. 部署建议
- **开发环境**：使用LOCAL_ONLY模式
- **生产环境**：推荐LOCAL_EXTERNAL_R2模式
- **团队协作**：使用LOCAL_EXTERNAL模式
- **个人使用**：使用LOCAL_R2模式

### 2. 性能调优
- 根据实际负载调整同步间隔
- 监控网络延迟和数据库性能
- 定期清理过期数据和日志
- 优化数据库索引和查询

### 3. 故障处理
- 设置监控告警，及时发现同步异常
- 准备数据恢复预案和备份策略
- 定期测试同步功能和数据一致性
- 建立故障升级和处理流程

## 总结

FlowSlide的智能数据同步策略通过：
- **分层同步**：根据数据重要性和访问频率分层处理
- **差异化策略**：不同数据类型采用最适合的同步方式
- **多模式支持**：适配各种部署场景和资源条件
- **性能优化**：智能调度和批量处理提高效率
- **容错设计**：确保系统稳定性和数据可靠性

实现了在保证数据一致性的同时，最大化系统性能和用户体验的目标。
