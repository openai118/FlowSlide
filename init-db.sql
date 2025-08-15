-- FlowSlide数据库初始化脚本
-- 创建必要的扩展和初始配置

-- 创建UUID扩展 (如果需要)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建全文搜索扩展 (如果需要)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置时区
SET timezone = 'UTC';

-- 创建应用用户的Schema (可选)
-- CREATE SCHEMA IF NOT EXISTS flowslide AUTHORIZATION flowslide_user;

-- 输出初始化完成信息
SELECT 'FlowSlide数据库初始化完成' as message;
