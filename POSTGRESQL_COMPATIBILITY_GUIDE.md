# PostgreSQL 数据库配置指南

## 🎯 通用性说明

这些数据库工具专为 **PostgreSQL** 设计，可以用于：

✅ **原生 PostgreSQL** - 标准 PostgreSQL 数据库
✅ **Supabase** - 基于 PostgreSQL 的 BaaS 平台
✅ **Neon** - PostgreSQL 兼容的无服务器数据库
✅ **PlanetScale** - MySQL 兼容（需要适配）
✅ **AWS RDS PostgreSQL** - Amazon 托管 PostgreSQL
✅ **Google Cloud SQL PostgreSQL** - Google 托管 PostgreSQL
✅ **Azure Database for PostgreSQL** - Microsoft 托管 PostgreSQL

## 📝 环境变量配置

### 核心数据库配置

```bash
# 方式一：DATABASE_URL（推荐，通用格式）
DATABASE_URL="postgresql://username:password@host:port/database?sslmode=require"

# 方式二：分离的环境变量
DB_HOST="your-database-host"
DB_PORT="5432"
DB_NAME="your_database_name"
DB_USER="your_username"
DB_PASSWORD="your_secure_password"
```

### API 配置（可选）

```bash
# 如果您的 PostgreSQL 服务提供 REST API（如 Supabase）
API_URL="https://your-api-endpoint"
API_ANON_KEY="your-api-anonymous-key"
API_SERVICE_KEY="your-api-service-key"
```

### 存储配置（可选）

```bash
# 如果需要测试文件存储功能
STORAGE_BUCKET="your-storage-bucket"
STORAGE_PROVIDER="postgresql"  # 或 "supabase", "aws-s3" 等
```

## 🔧 不同平台的配置示例

### 1. 标准 PostgreSQL

```bash
DATABASE_URL="postgresql://myuser:mypass@localhost:5432/mydb?sslmode=require"
# API 相关配置可以留空
API_URL=""
API_ANON_KEY=""
API_SERVICE_KEY=""
STORAGE_PROVIDER="postgresql"
```

### 2. Supabase

```bash
DATABASE_URL="postgresql://postgres:yourpass@db.projectid.supabase.co:5432/postgres?sslmode=require&options=-c%20search_path%3Dpublic"
API_URL="https://projectid.supabase.co"
API_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
API_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
STORAGE_BUCKET="your-bucket"
STORAGE_PROVIDER="supabase"
```

### 3. AWS RDS PostgreSQL

```bash
DATABASE_URL="postgresql://username:password@your-rds-instance.region.rds.amazonaws.com:5432/dbname?sslmode=require"
# API 相关配置通常留空（除非有自定义 API）
API_URL=""
STORAGE_PROVIDER="aws-s3"  # 如果使用 S3 存储
```

### 4. Google Cloud SQL

```bash
DATABASE_URL="postgresql://username:password@your-instance-ip:5432/dbname?sslmode=require"
API_URL=""
STORAGE_PROVIDER="gcs"  # 如果使用 Google Cloud Storage
```

### 5. Neon

```bash
DATABASE_URL="postgresql://username:password@your-endpoint.neon.tech:5432/dbname?sslmode=require"
API_URL=""
STORAGE_PROVIDER="postgresql"
```

## 🚀 使用方法

### 健康检查

```bash
# 基本检查（适用于所有 PostgreSQL）
DATABASE_URL="your-url" python database_health_check.py

# 完整检查（包括 API 和存储测试）
DATABASE_URL="your-url" \
API_URL="your-api" \
API_ANON_KEY="your-key" \
python database_health_check.py
```

### 数据库诊断

```bash
# 性能诊断（适用于所有 PostgreSQL）
DATABASE_URL="your-url" python database_diagnosis.py
```

## 📊 功能支持矩阵

| 功能 | PostgreSQL | Supabase | Neon | AWS RDS | 其他托管服务 |
|------|------------|----------|------|---------|-------------|
| 基本连接测试 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 模式访问检查 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 表操作权限 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 性能分析 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 慢查询分析 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 索引分析 | ✅ | ✅ | ✅ | ✅ | ✅ |
| API 连接测试 | ❌ | ✅ | ❌ | ❌ | 看情况 |
| 存储测试 | ❌ | ✅ | ❌ | ❌ | 看情况 |

## 🔍 检查项说明

### 核心检查（所有 PostgreSQL 支持）
- **数据库连接** - 测试基本连接和认证
- **模式访问** - 检查可访问的数据库模式
- **表操作权限** - 测试 CRUD 操作权限
- **性能分析** - 数据库大小、连接数、缓存命中率
- **索引使用** - 索引效率和未使用索引

### 可选检查（取决于服务提供商）
- **API 连接** - 测试 REST API 可用性
- **存储访问** - 测试文件存储功能

## ⚠️ 注意事项

1. **权限要求**：确保数据库用户有足够权限进行测试
2. **网络访问**：确保防火墙允许数据库连接
3. **SSL/TLS**：生产环境建议启用 SSL 连接
4. **扩展支持**：某些功能需要特定的 PostgreSQL 扩展（如 `pg_stat_statements`）

## 🛠️ 故障排查

### 连接失败
```bash
# 检查网络连通性
telnet your-host 5432

# 检查 SSL 要求
psql "postgresql://user:pass@host:5432/db?sslmode=disable"
```

### 权限不足
```sql
-- 检查用户权限
SELECT * FROM information_schema.role_table_grants WHERE grantee = 'your_user';

-- 检查模式权限
SELECT schema_name FROM information_schema.schemata;
```

### 性能问题
```sql
-- 启用统计扩展（需要超级用户权限）
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 检查当前连接
SELECT * FROM pg_stat_activity;
```

## 📚 相关资源

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [psycopg2 连接参数](https://www.psycopg.org/docs/module.html#psycopg2.connect)
- [数据库连接字符串格式](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
