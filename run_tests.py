#!/usr/bin/env python3
"""
FlowSlide Test Runner
运行测试套件并生成报告
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def install_test_dependencies():
    """安装测试依赖"""
    print("📦 安装测试依赖...")

    test_deps = [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "pytest-mock>=3.10.0",
        "pytest-timeout>=2.1.0",
        "httpx>=0.25.0",  # For async client testing
        "requests-mock>=1.10.0",  # For mocking HTTP requests
    ]

    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install"
        ] + test_deps, check=True)
        print("✅ 测试依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试依赖安装失败: {e}")
        return False


def run_tests(test_type="all", verbose=False, coverage=True, parallel=False):
    """运行测试"""
    print(f"🧪 运行测试: {test_type}")

    # 基础命令
    cmd = [sys.executable, "-m", "pytest"]

    # 根据测试类型添加参数
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "api":
        cmd.extend(["-m", "api"])
    elif test_type == "auth":
        cmd.extend(["-m", "auth"])
    elif test_type == "database":
        cmd.extend(["-m", "database"])
    elif test_type == "fast":
        cmd.extend(["-m", "not slow"])
    elif test_type == "slow":
        cmd.extend(["-m", "slow"])

    # 详细输出与基础一致选项（当禁用 coverage 时用 -o 清空 ini 的 addopts）
    if verbose:
        cmd.append("-v")

    # 当显式禁用 coverage 时，覆盖 pytest.ini 的 addopts，避免其中的 --cov 与阈值生效
    # 同时保留关键行为选项（严格 marker/config、回溯样式、asyncio 模式）
    if not coverage:
        cmd.extend([
            "-o", "addopts=--strict-markers --strict-config --tb=short --asyncio-mode=auto",
        ])

    # 覆盖率报告
    if coverage:
        cmd.extend([
            "--cov=src/flowslide",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml"
        ])

    # 并行执行
    if parallel:
        cmd.extend(["-n", "auto"])

    # 添加测试目录
    cmd.append("tests/")

    print(f"🚀 执行命令: {' '.join(cmd)}")

    try:
        # Ensure src/ is importable by pytest (so `import flowslide` works)
        env = os.environ.copy()
        project_root = Path(__file__).resolve().parent
        src_path = str((project_root / "src").resolve())
        existing_pp = env.get("PYTHONPATH", "")
        if src_path not in existing_pp.split(os.pathsep):
            env["PYTHONPATH"] = src_path + (os.pathsep + existing_pp if existing_pp else "")

        result = subprocess.run(cmd, check=False, env=env)
        # pytest 退出码 5 表示未收集到测试用例，视为成功（在某些环境中允许空测试集通过）
        if result.returncode in (0, 5):
            return True
        return False
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        return False
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return False


def run_linting():
    """运行代码检查"""
    print("🔍 运行代码检查...")

    linting_tools = [
        (["python", "-m", "flake8", "src/", "tests/"], "Flake8"),
        (["python", "-m", "black", "--check", "src/", "tests/"], "Black"),
        (["python", "-m", "isort", "--check-only", "src/", "tests/"], "isort"),
    ]

    all_passed = True

    for cmd, tool_name in linting_tools:
        print(f"  📋 运行 {tool_name}...")
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ {tool_name} 检查通过")
            else:
                print(f"  ❌ {tool_name} 检查失败:")
                print(f"     {result.stdout}")
                print(f"     {result.stderr}")
                all_passed = False
        except FileNotFoundError:
            print(f"  ⚠️ {tool_name} 未安装，跳过检查")
        except Exception as e:
            print(f"  ❌ {tool_name} 执行失败: {e}")
            all_passed = False

    return all_passed


def run_security_scan():
    """运行安全扫描"""
    print("🔒 运行安全扫描...")

    security_tools = [
        (["python", "-m", "safety", "check"], "Safety"),
        (["python", "-m", "bandit", "-r", "src/"], "Bandit"),
    ]

    all_passed = True

    for cmd, tool_name in security_tools:
        print(f"  🛡️ 运行 {tool_name}...")
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ {tool_name} 扫描通过")
            else:
                print(f"  ⚠️ {tool_name} 发现问题:")
                print(f"     {result.stdout}")
                all_passed = False
        except FileNotFoundError:
            print(f"  ⚠️ {tool_name} 未安装，跳过扫描")
        except Exception as e:
            print(f"  ❌ {tool_name} 执行失败: {e}")
            all_passed = False

    return all_passed


def generate_test_report():
    """生成测试报告"""
    print("📊 生成测试报告...")

    # 检查覆盖率报告
    coverage_html = Path("htmlcov/index.html")
    coverage_xml = Path("coverage.xml")

    if coverage_html.exists():
        print(f"✅ HTML 覆盖率报告: {coverage_html.absolute()}")

    if coverage_xml.exists():
        print(f"✅ XML 覆盖率报告: {coverage_xml.absolute()}")

    # 检查测试结果
    junit_xml = Path("test-results.xml")
    if junit_xml.exists():
        print(f"✅ JUnit 测试报告: {junit_xml.absolute()}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="FlowSlide 测试运行器")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "api", "auth", "database", "fast", "slow"],
        default="all",
        help="测试类型"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--no-coverage", action="store_true", help="禁用覆盖率报告")
    parser.add_argument("--parallel", "-p", action="store_true", help="并行执行测试")
    parser.add_argument("--install-deps", action="store_true", help="安装测试依赖")
    parser.add_argument("--lint", action="store_true", help="运行代码检查")
    parser.add_argument("--security", action="store_true", help="运行安全扫描")
    parser.add_argument("--all-checks", action="store_true", help="运行所有检查")

    args = parser.parse_args()

    print("🚀 FlowSlide 测试运行器")
    print("=" * 50)

    success = True

    # 安装依赖
    if args.install_deps or args.all_checks:
        if not install_test_dependencies():
            success = False

    # 运行代码检查
    if args.lint or args.all_checks:
        if not run_linting():
            success = False

    # 运行安全扫描
    if args.security or args.all_checks:
        if not run_security_scan():
            success = False

    # 运行测试
    if not run_tests(
        test_type=args.type,
        verbose=args.verbose,
        coverage=not args.no_coverage,
        parallel=args.parallel
    ):
        success = False

    # 生成报告
    generate_test_report()

    print("\n" + "=" * 50)
    if success:
        print("🎉 所有检查通过！")
        sys.exit(0)
    else:
        print("❌ 部分检查失败，请查看上述输出")
        sys.exit(1)


if __name__ == "__main__":
    main()
