#!/usr/bin/env python3
"""
简单的项目验证脚本
"""

import sys
import os
from pathlib import Path

def check_project_structure():
    """检查项目结构"""
    print("🔍 检查项目结构...")
    
    required_files = [
        "run.py",
        "requirements.txt", 
        "pyproject.toml",
        "src/flowslide/__init__.py",
        "src/flowslide/main.py",
        "src/flowslide/core/simple_config.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")
    
    if missing_files:
        print(f"❌ 缺失文件: {missing_files}")
        return False
    
    print("✅ 项目结构完整")
    return True

def check_python_syntax():
    """检查主要Python文件的语法"""
    print("\n🔍 检查Python语法...")
    
    key_files = [
        "run.py",
        "src/flowslide/main.py",
        "src/flowslide/core/simple_config.py"
    ]
    
    for file_path in key_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), file_path, 'exec')
                print(f"✅ {file_path} 语法正确")
            except SyntaxError as e:
                print(f"❌ {file_path} 语法错误: {e}")
                return False
        else:
            print(f"⚠️ {file_path} 不存在")
    
    return True

def check_requirements():
    """检查requirements.txt"""
    print("\n🔍 检查依赖配置...")
    
    if not os.path.exists("requirements.txt"):
        print("❌ requirements.txt 不存在")
        return False
    
    with open("requirements.txt", 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    critical_deps = ["fastapi", "uvicorn", "pydantic", "sqlalchemy"]
    found_deps = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            dep_name = line.split('>=')[0].split('==')[0].split('[')[0]
            if dep_name in critical_deps:
                found_deps.append(dep_name)
    
    missing_deps = set(critical_deps) - set(found_deps)
    
    if missing_deps:
        print(f"❌ 缺失关键依赖: {missing_deps}")
        return False
    
    print(f"✅ 找到关键依赖: {found_deps}")
    return True

def create_missing_directories():
    """创建缺失的目录"""
    print("\n🔍 创建必要目录...")
    
    required_dirs = [
        "data",
        "temp", 
        "temp/images_cache",
        "temp/ai_responses_cache",
        "logs"
    ]
    
    created_dirs = []
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            created_dirs.append(dir_path)
            print(f"📁 创建目录: {dir_path}")
        else:
            print(f"✅ 目录已存在: {dir_path}")
    
    if created_dirs:
        print(f"✅ 创建了 {len(created_dirs)} 个目录")
    
    return True

def check_config_files():
    """检查配置文件"""
    print("\n🔍 检查配置文件...")
    
    # 检查是否有.env文件
    if os.path.exists(".env"):
        print("✅ .env 文件存在")
    else:
        print("⚠️ .env 文件不存在，将使用默认配置")
    
    # 检查.env.example
    if os.path.exists(".env.example"):
        print("✅ .env.example 文件存在")
    else:
        print("⚠️ .env.example 文件不存在")
    
    return True

def main():
    """主函数"""
    print("🚀 FlowSlide 项目验证")
    print("=" * 40)
    
    checks = [
        ("项目结构", check_project_structure),
        ("Python语法", check_python_syntax), 
        ("依赖配置", check_requirements),
        ("目录创建", create_missing_directories),
        ("配置文件", check_config_files)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed += 1
            else:
                print(f"❌ {check_name} 检查失败")
        except Exception as e:
            print(f"❌ {check_name} 检查异常: {e}")
    
    print("\n" + "=" * 40)
    print(f"🎯 验证结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 项目验证通过！")
        print("\n📋 下一步:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 配置环境: cp .env.example .env")
        print("3. 启动应用: python run.py")
    else:
        print("⚠️ 项目验证未完全通过，请检查上述问题")
    
    return passed == total

if __name__ == "__main__":
    main()
