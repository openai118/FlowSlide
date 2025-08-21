#!/usr/bin/env python3
"""
性能测试运行脚本
运行Locust性能测试
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def main():
    """运行性能测试"""
    parser = argparse.ArgumentParser(description='运行FlowSlide性能测试')
    parser.add_argument('--host', default='http://localhost:8000', 
                       help='测试目标主机 (默认: http://localhost:8000)')
    parser.add_argument('--users', type=int, default=10, 
                       help='并发用户数 (默认: 10)')
    parser.add_argument('--spawn-rate', type=int, default=2, 
                       help='用户生成速率 (默认: 2)')
    parser.add_argument('--time', default='60s', 
                       help='测试持续时间 (默认: 60s)')
    
    args = parser.parse_args()
    
    # 获取当前脚本目录
    current_dir = Path(__file__).parent
    locustfile_path = current_dir / 'locustfile.py'
    
    if not locustfile_path.exists():
        print(f"错误: 找不到locustfile.py在 {locustfile_path}")
        sys.exit(1)
    
    # 构建Locust命令
    cmd = [
        'locust',
        '-f', str(locustfile_path),
        '--host', args.host,
        '--users', str(args.users),
        '--spawn-rate', str(args.spawn_rate),
        '--run-time', args.time,
        '--headless'
    ]
    
    print(f"运行性能测试: {' '.join(cmd)}")
    
    try:
        # 运行Locust测试
        result = subprocess.run(cmd, check=True)
        print("性能测试完成")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"性能测试失败: {e}")
        return e.returncode
    except FileNotFoundError:
        print("错误: 找不到locust命令。请确保已安装locust: pip install locust")
        return 1


if __name__ == '__main__':
    sys.exit(main())
