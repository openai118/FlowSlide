# FlowSlide 项目结构

## 📁 目录结构

```
FlowSlide/
├── 📄 README.md                    # 项目主文档
├── 📄 CHANGELOG.md                 # 版本更新日志
├── 📄 LICENSE                      # 开源许可证
├── 📄 requirements.txt             # Python依赖
├── 📄 requirements-dev.txt         # 开发依赖
├── 📄 pyproject.toml              # 项目配置
├── 📄 pytest.ini                  # 测试配置
├── 📄 docker-compose.yml          # Docker编排
├── 📄 Dockerfile                  # Docker镜像构建
│
├── 🚀 启动脚本/
│   ├── start_flowslide.py         # Python启动脚本
│   ├── start.bat                  # Windows批处理启动
│   ├── start.ps1                  # PowerShell启动脚本
│   └── run.py                     # 简单启动脚本
│
├── 📂 src/                        # 源代码目录
│   ├── flowslide/                 # 主应用
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI应用入口
│   │   ├── core/                 # 核心配置
│   │   ├── api/                  # API路由
│   │   ├── auth/                 # 认证模块
│   │   ├── database/             # 数据库模型
│   │   ├── services/             # 业务服务
│   │   ├── web/                  # Web界面
│   │   └── monitoring/           # 监控模块
│   └── summeryanyfile/           # 文件处理模块
│
├── 📂 tests/                     # 测试目录
│   ├── conftest.py              # 测试配置
│   ├── test_*.py                # 单元测试
│   └── performance/             # 性能测试
│       ├── locustfile.py        # Locust性能测试
│       └── run_performance_tests.py
│
├── 📂 docs/                     # 文档目录
│   ├── api/                     # API文档
│   │   ├── README.md           # API使用指南
│   │   └── *.postman_collection.json
│   └── index.html              # 文档首页
│
├── 📂 monitoring/               # 监控配置
│   ├── prometheus.yml          # Prometheus配置
│   ├── alert_rules.yml         # 告警规则
│   ├── alertmanager.yml        # 告警管理
│   └── grafana/                # Grafana仪表板
│
├── 📂 security/                # 安全工具
│   └── security_scan.py        # 安全扫描脚本
│
├── 📂 scripts/                 # 工具脚本
│   └── verify-deployment.sh    # 部署验证
│
├── 📂 template_examples/       # 模板示例
│   ├── 商务.json
│   ├── 简约答辩风.json
│   └── ...
│
├── 📂 data/                    # 数据目录
│   └── flowslide.db           # SQLite数据库
│
└── 📂 temp/                   # 临时文件
    ├── ai_responses_cache/    # AI响应缓存
    ├── images_cache/          # 图片缓存
    └── templates_cache/       # 模板缓存
```

## 🔧 核心模块说明

### 🎯 主应用 (src/flowslide/)

- **main.py**: FastAPI应用入口，路由注册
- **core/**: 配置管理、数据库连接
- **api/**: RESTful API端点
- **auth/**: 用户认证、权限管理
- **database/**: SQLAlchemy模型定义
- **services/**: 业务逻辑服务
- **web/**: Jinja2模板和静态文件
- **monitoring/**: Prometheus指标收集

### 🧪 测试框架 (tests/)

- **单元测试**: 覆盖核心功能模块
- **集成测试**: API端点测试
- **性能测试**: Locust负载测试
- **安全测试**: 漏洞扫描和安全检查

### 📊 监控系统 (monitoring/)

- **Prometheus**: 指标收集和存储
- **Grafana**: 可视化仪表板
- **AlertManager**: 告警通知管理
- **自定义指标**: 应用性能监控

### 🔒 安全工具 (security/)

- **依赖扫描**: 检查已知漏洞
- **代码扫描**: 静态安全分析
- **配置检查**: 安全配置验证
- **密钥检测**: 防止密钥泄露

## 🚀 启动方式

### 开发环境

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动应用
python start_flowslide.py
```

### 生产环境

```bash
# Docker方式
docker-compose up -d

# 或直接运行
docker run -p 8000:8000 openai118/flowslide:latest
```

## 📝 配置文件

### 环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL=postgresql://user:pass@host:port/db

# AI服务配置
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# 图片服务配置
PIXABAY_API_KEY=your_pixabay_key
UNSPLASH_ACCESS_KEY=your_unsplash_key

# 研究服务配置
TAVILY_API_KEY=your_tavily_key

# 应用配置
SECRET_KEY=your_secret_key
DEBUG=false
```

### Docker配置

- **Dockerfile**: 多阶段构建，优化镜像大小
- **docker-compose.yml**: 完整的服务编排
- **健康检查**: 自动监控和重启

## 🔄 开发工作流

1. **代码开发**: 在src/目录下开发功能
2. **编写测试**: 在tests/目录下添加测试
3. **运行测试**: `python -m pytest`
4. **性能测试**: `python tests/performance/run_performance_tests.py`
5. **安全扫描**: `python security/security_scan.py`
6. **构建镜像**: `docker build -t flowslide .`
7. **部署应用**: `docker-compose up -d`

## 📚 相关文档

- [快速开始指南](QUICK_START_GUIDE.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [API文档](docs/api/README.md)
- [持续改进总结](CONTINUOUS_IMPROVEMENT_SUMMARY.md)
- [项目改进记录](PROJECT_IMPROVEMENTS.md)

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 📄 许可证

本项目采用 Apache 2.0 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
