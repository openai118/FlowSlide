# 数据库变量配置指南

## 🔒 重要安全提醒

**您在消息中提供的包含真实的敏感信息，包括：**
- 数据库密码
- JWT 密钥
- Supabase 服务密钥

**为了安全起见，建议您立即：**
1. 更改数据库密码
2. 重新生成 Supabase 密钥
3. 使用本文档的脱敏模板配置环境变量

## 📝 环境变量配置

### 方式一：使用 DATABASE_URL（推荐）

```bash
# 完整的数据库连接 URL（脱敏示例）
DATABASE_URL="postgresql://username:password@your-host.supabase.co:5432/postgres?sslmode=require&options=-c%20search_path%3Dyour_schema,public"

# Supabase API 配置
SUPABASE_URL="https://your-project-id.supabase.co"
SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-anon-key-payload.signature"
SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-service-key-payload.signature"

# 存储配置
STORAGE_BUCKET="landppt-files"
STORAGE_PROVIDER="supabase"
```

### 方式二：使用分离的环境变量

```bash
# 数据库配置
DB_HOST="your-host.supabase.co"
DB_PORT="5432"
DB_NAME="postgres"
DB_USER="your_username"
DB_PASSWORD="your_secure_password"

# Supabase API 配置
SUPABASE_URL="https://your-project-id.supabase.co"
SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-anon-key-payload.signature"
SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-service-key-payload.signature"

# 存储配置
STORAGE_BUCKET="landppt-files"
STORAGE_PROVIDER="supabase"
```

## 🚀 使用方法

### 1. 创建 .env 文件

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入您的实际配置
# 注意：.env 文件已在 .gitignore 中，不会被提交到 Git
```

### 2. Docker Compose 部署

```bash
# 使用环境变量文件启动
docker-compose --env-file .env up -d

# 或者直接设置环境变量
DATABASE_URL="your-database-url" docker-compose up -d
```

### 3. 本地开发

```bash
# 设置环境变量后运行
export DATABASE_URL="your-database-url"
export SUPABASE_URL="your-supabase-url"
export SUPABASE_ANON_KEY="your-anon-key"

# 运行应用
python run.py
```

## 🔧 数据库工具使用

### 健康检查

```bash
# 使用 DATABASE_URL
DATABASE_URL="your-url" python database_health_check.py

# 使用分离变量
DB_HOST="host" DB_USER="user" DB_PASSWORD="pass" python database_health_check.py
```

### 数据库诊断

```bash
# 完整诊断
DATABASE_URL="your-url" python database_diagnosis.py

# 查看诊断报告
ls database_diagnosis_report_*.json
```

## 🛡️ 安全最佳实践

1. **永远不要在代码中硬编码敏感信息**
2. **使用环境变量或密钥管理服务**
3. **定期轮换密钥和密码**
4. **在生产环境使用强密码**
5. **限制数据库用户权限**
6. **启用 SSL/TLS 连接**

## ⚠️ 注意事项

- `DATABASE_URL` 优先级高于分离的环境变量
- JWT 密钥应该保密，不要在日志中输出
- 生产环境建议使用密钥管理服务（如 AWS Secrets Manager、Azure Key Vault）
- 定期检查和更新依赖包

## 📚 相关文档

- [Supabase 官方文档](https://supabase.com/docs)
- [PostgreSQL 连接字符串格式](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- [Docker Compose 环境变量](https://docs.docker.com/compose/environment-variables/)
