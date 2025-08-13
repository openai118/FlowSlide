# LandPPT - AI-Powered Presentation Generator

![LandPPT Logo](https://img.shields.io/badge/LandPPT-AI%20Presentation-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-2.0.0-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> 🚀 **Enterprise-ready AI presentation generator with database monitoring and automated backup**

一个功能强大的 AI 演示文稿生成器，集成了企业级数据库监控和自动备份功能。支持多�?AI 模型，自动图像配图，智能研究功能，并提供完整的运维监控体系�?

## �?主要特�?

### 🎯 AI 演示文稿生成
- **�?AI 模型支持**: OpenAI GPT-4, Anthropic Claude, Google Gemini, Ollama 本地模型
- **智能图像配图**: 集成 Pixabay, Unsplash API 自动匹配图片
- **智能研究功能**: 使用 Tavily API 进行实时信息搜索
- **多格式导�?*: HTML, PDF, PPTX 等多种格�?
- **丰富模板系统**: 内置多种专业演示模板

### 🛡️ 企业级监控 (新增)
- **通用 PostgreSQL 监控**: 支持 PostgreSQL 及其衍生产品（Supabase、Neon、AWS RDS 等）
- **实时数据库健康检查**: 连接、权限、性能全面监控
- **性能诊断工具**: 连接池、查询性能、资源使用监控
- **自动化健康报告**: JSON 格式详细报告生成
- **压力测试工具**: 数据库负载能力评估

### 💾 自动化备份系�?(新增)
- **Cloudflare R2 集成**: 企业级对象存储备�?
- **定时备份调度**: 可配置的自动备份策略
- **增量备份支持**: 高效的存储空间利�?
- **一键恢复功�?*: 快速灾难恢复能�?

### 🐳 容器化部�?
- **Docker 多阶段构�?*: 优化的镜像大小和安全�?
- **健康检查机�?*: 自动监控和故障恢�?
- **企业级配�?*: 生产环境就绪的配置管�?

## 🚀 快速开�?

### 环境要求

- Python 3.11+
- Git (用于版本控制)
- Supabase 数据�?(用于监控功能)
- Cloudflare R2 存储 (用于备份功能，可�?

### 1. 克隆项目

```bash
git clone https://github.com/your-username/landppt-integrated.git
cd landppt-integrated
```

### 2. 配置环境

```bash
# 复制环境配置模板
copy .env.example .env

# 编辑配置文件
notepad .env
```

### 2. `quick_db_check.py` - 快速检�?
**用�?*: 日常快速验证数据库基本功能
**特点**:
- 🚀 快速执行（30秒内完成�?
- �?管理员和应用用户连接测试
- �?基本读写权限验证
- �?存储桶状态检�?
- 📊 简洁的输出格式

**使用方法**:
```bash
python quick_db_check.py
```

### 3. `database_stress_test.py` - 压力测试
**用�?*: 模拟高并发场景下的数据库性能测试
**特点**:
- 🔥 多线程并发测�?
- 📊 连接池管�?
- 🔍 读取、写入、存储操作模�?
- 📈 详细性能分析
- 📄 结果导出�?JSON

**使用方法**:
```bash
python database_stress_test.py
```

## 🛠�?安装依赖

在运行任何脚本之前，请确保安装必要的 Python 依赖�?

```bash
pip install psycopg2-binary requests
```

或者如果您使用 conda�?

```bash
conda install psycopg2 requests
```

## 🔧 配置说明

所有脚本都已经预配置了您的 Supabase 数据库信息：

- **数据库主�?*: `your-supabase-host`
- **应用用户**: `your_db_user`
- **存储�?*: `your-storage-bucket`
- **API 密钥**: 已内置（请保密）

运行时只需要输入您�?postgres 用户密码�?

## 📊 使用建议

### 1. 首次部署检�?
```bash
# 1. 先运行完整健康检�?
python database_health_check.py

# 2. 如果有问题，查看生成的报告文�?
# supabase_health_report_*.json
```

### 2. 日常监控
```bash
# 快速检查（推荐每日使用�?
python quick_db_check.py
```

### 3. 性能评估
```bash
# 在应用上线前或性能调优时使�?
python database_stress_test.py
```

## 📋 测试覆盖范围

### 数据库层�?
- [x] 基本连接�?
- [x] 认证和授�?
- [x] Schema 和表权限
- [x] 函数执行权限
- [x] 搜索路径配置
- [x] 读写性能
- [x] 并发处理能力

### 存储层面
- [x] Storage API 访问
- [x] 存储桶配�?
- [x] 文件上传/下载
- [x] 权限验证
- [x] 文件删除

### 性能层面
- [x] 查询响应时间
- [x] 连接延迟
- [x] 并发处理能力
- [x] 连接池效�?
- [x] 错误率统�?

## 🔍 结果解读

### 健康检查结�?
- **HEALTHY**: 所有测试通过，可以部�?
- **UNHEALTHY**: 存在问题，需要修�?

### 快速检查结�?
- **所�?�?*: 基本功能正常
- **任何 �?*: 需要进一步调�?

### 压力测试结果
- **优秀 🌟**: 成功�?�?95%
- **良好 👍**: 成功�?�?90%
- **一�?⚠️**: 成功�?�?80%
- **需要优�?�?*: 成功�?< 80%

## 🚨 常见问题

### 1. 连接失败
```
�?数据库连接失�? connection to server at "your-supabase-host" failed
```
**解决方案**: 检查网络连接和密码是否正确

### 2. 权限错误
```
�?Schema 访问失败: permission denied for schema landppt
```
**解决方案**: 重新运行初始�?SQL 脚本

### 3. 存储访问失败
```
�?存储 API 访问失败: 401
```
**解决方案**: 检�?SERVICE_KEY 是否正确

### 4. 应用用户登录失败
```
�?应用用户权限问题: password authentication failed for user "your_db_user"
```
**解决方案**: 确认 your_db_user 角色已正确创�?

## 📞 技术支�?

如果遇到问题�?

1. 首先运行完整健康检查获取详细错误信�?
2. 检�?Supabase 控制台的日志
3. 确认所有初始化 SQL 脚本都已正确执行
4. 验证网络连接和防火墙设置

## 🔄 更新日志

- **v1.0**: 初始版本，包含基本检查功�?
- **v1.1**: 添加压力测试和性能分析
- **v1.2**: 改进错误处理和报告格�?

---

🎯 **目标**: 确保 LandPPT 应用的数据库环境稳定可靠�?
