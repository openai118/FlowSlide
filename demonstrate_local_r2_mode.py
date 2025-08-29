#!/usr/bin/env python3
"""
LOCAL_R2模式演示脚本
展示单向备份机制和数据处理方式
"""

import sys
import os
sys.path.append('src')

from flowslide.core.sync_strategy_config import DataSyncStrategy, DeploymentMode


def demonstrate_local_r2_mode():
    """演示LOCAL_R2模式的同步策略"""
    print("🔍 LOCAL_R2模式同步策略演示")
    print("=" * 50)

    # 模拟LOCAL_R2环境
    original_env = dict(os.environ)
    os.environ["R2_ACCESS_KEY_ID"] = "demo_access_key"
    os.environ["R2_SECRET_ACCESS_KEY"] = "demo_secret_key"
    os.environ["R2_ENDPOINT"] = "https://demo.r2.cloudflarestorage.com"
    os.environ["R2_BUCKET_NAME"] = "demo-bucket"

    # 清除外部数据库配置
    os.environ.pop("DATABASE_URL", None)

    try:
        # 创建策略配置实例
        strategy = DataSyncStrategy()

        print(f"📊 检测到的部署模式: {strategy.deployment_mode.value}")
        print()

        # 展示各数据类型的同步策略
        print("📋 数据同步策略详情:")
        print("-" * 40)

        for data_type, config in strategy.sync_strategies.items():
            print(f"\n🔹 {data_type.upper()}:")
            print(f"   同步启用: {'✅ 是' if config['sync_enabled'] else '❌ 否'}")
            print(f"   同步方向: {config['directions']}")
            print(f"   同步间隔: {config['interval_seconds']}秒 ({config['interval_seconds']//60}分钟)")
            print(f"   批处理大小: {config['batch_size']}")
            print(f"   同步策略: {config['strategy']}")

            # 解释策略含义
            if config['strategy'] == 'backup_only':
                print("   💡 策略说明: 仅备份到R2，不进行双向同步")
            elif config['strategy'] == 'local_only':
                print("   💡 策略说明: 仅保存在本地，不同步")
            else:
                print(f"   💡 策略说明: {config['strategy']}策略")

        print("\n" + "=" * 50)
        print("🎯 LOCAL_R2模式特点总结:")
        print()
        print("1️⃣ 单向备份机制:")
        print("   • 所有数据只从本地备份到R2")
        print("   • 不从R2同步数据到本地")
        print("   • 避免了双向同步的复杂性")
        print()
        print("2️⃣ 用户数据处理:")
        print("   • 用户数据定期备份到R2（10分钟间隔）")
        print("   • 本地修改立即生效，无需等待同步")
        print("   • R2备份用于灾难恢复")
        print()
        print("3️⃣ 项目数据处理:")
        print("   • 项目基本信息定期备份（10分钟）")
        print("   • 幻灯片内容按需备份（30分钟）")
        print("   • 模板数据定期备份（1小时）")
        print()
        print("4️⃣ 数据恢复机制:")
        print("   • 可从R2恢复历史备份")
        print("   • 恢复操作需要手动执行")
        print("   • 恢复时会覆盖本地数据")

    finally:
        # 恢复环境变量
        os.environ.clear()
        os.environ.update(original_env)


def demonstrate_backup_operations():
    """演示备份操作流程"""
    print("\n🔄 备份操作流程演示")
    print("=" * 50)

    print("📦 本地数据备份到R2的流程:")
    print()
    print("1️⃣ 定时触发备份任务")
    print("   • 每10分钟检查用户/项目数据变更")
    print("   • 每30分钟检查幻灯片内容变更")
    print("   • 每1小时检查模板数据变更")
    print()
    print("2️⃣ 数据准备阶段")
    print("   • 从本地SQLite提取变更数据")
    print("   • 压缩数据以减少传输量")
    print("   • 生成备份清单和元数据")
    print()
    print("3️⃣ R2上传阶段")
    print("   • 使用rclone工具上传到R2")
    print("   • 上传路径: r2://bucket/backups/YYYYMMDD_HHMMSS/")
    print("   • 包含: 数据库、文件、配置、日志")
    print()
    print("4️⃣ 备份验证阶段")
    print("   • 验证上传文件完整性")
    print("   • 更新备份清单")
    print("   • 发送备份完成通知")
    print()
    print("5️⃣ 清理阶段")
    print("   • 删除本地临时备份文件")
    print("   • 清理超过30天的旧备份")


def demonstrate_data_recovery():
    """演示数据恢复流程"""
    print("\n🔄 数据恢复流程演示")
    print("=" * 50)

    print("📥 从R2恢复数据的流程:")
    print()
    print("1️⃣ 选择恢复点")
    print("   • 列出R2中的所有备份版本")
    print("   • 选择要恢复的备份日期时间")
    print("   • 确认恢复范围（全部/数据库/文件/配置）")
    print()
    print("2️⃣ 恢复准备")
    print("   • 备份当前本地数据（安全起见）")
    print("   • 停止相关服务进程")
    print("   • 准备恢复环境")
    print()
    print("3️⃣ 数据下载")
    print("   • 从R2下载选定的备份文件")
    print("   • 验证下载文件完整性")
    print("   • 解压备份文件")
    print()
    print("4️⃣ 数据恢复")
    print("   • 恢复数据库（覆盖现有数据）")
    print("   • 恢复应用文件和配置")
    print("   • 恢复日志文件")
    print()
    print("5️⃣ 恢复验证")
    print("   • 检查数据库完整性")
    print("   • 验证应用功能")
    print("   • 重启相关服务")
    print()
    print("6️⃣ 清理工作")
    print("   • 删除下载的临时文件")
    print("   • 记录恢复操作日志")


def show_user_data_handling():
    """展示用户数据处理方式"""
    print("\n👤 LOCAL_R2模式下的用户数据处理")
    print("=" * 50)

    print("🔐 用户认证和数据处理:")
    print()
    print("1️⃣ 用户注册/登录:")
    print("   • 在本地SQLite中立即创建/验证用户")
    print("   • 用户可以立即使用系统")
    print("   • 无需等待任何同步操作")
    print()
    print("2️⃣ 用户数据变更:")
    print("   • 密码修改、邮箱更新等立即生效")
    print("   • 本地数据库实时更新")
    print("   • 用户体验与纯本地模式相同")
    print()
    print("3️⃣ 定期备份:")
    print("   • 每10分钟自动备份用户数据到R2")
    print("   • 备份包含所有用户账户信息")
    print("   • 用于灾难恢复和数据安全")
    print()
    print("4️⃣ 灾难恢复:")
    print("   • 从R2恢复用户数据")
    print("   • 恢复后用户可以继续使用")
    print("   • 恢复期间服务可能短暂中断")
    print()
    print("💡 关键优势:")
    print("   • 用户体验与纯本地模式无差异")
    print("   • 数据安全性通过云备份得到保证")
    print("   • 成本低廉（仅备份，不同步）")
    print("   • 适合个人用户和小型团队")


def show_backup_data_access():
    """展示备份数据的访问方式"""
    print("\n📂 备份数据的访问和查看")
    print("=" * 50)

    print("🔍 R2备份数据的访问方式:")
    print()
    print("1️⃣ 备份清单查看:")
    print("   • 使用 restore_from_r2.sh -l 查看所有备份")
    print("   • 显示备份时间、大小、包含的内容")
    print("   • 备份路径格式: YYYYMMDD_HHMMSS")
    print()
    print("2️⃣ 备份内容预览:")
    print("   • 使用 restore_from_r2.sh -i <日期> 查看详情")
    print("   • 显示备份清单JSON文件")
    print("   • 包含数据库、文件、配置等信息")
    print()
    print("3️⃣ 选择性恢复:")
    print("   • -d: 只恢复数据库")
    print("   • -f: 只恢复文件")
    print("   • -c: 只恢复配置")
    print("   • 无参数: 完整恢复")
    print()
    print("4️⃣ 前端查看历史PPT:")
    print("   • 恢复备份到本地后可正常查看")
    print("   • 备份中的PPT文件可直接打开")
    print("   • 历史版本可通过项目版本管理查看")
    print()
    print("⚠️ 重要说明:")
    print("   • R2中的备份数据不会直接在前端显示")
    print("   • 需要先恢复到本地才能查看和使用")
    print("   • 恢复操作会覆盖当前本地数据")
    print("   • 建议在恢复前备份当前数据")


def main():
    """主演示函数"""
    print("🎬 FlowSlide LOCAL_R2模式详细演示")
    print("=" * 60)

    demonstrate_local_r2_mode()
    demonstrate_backup_operations()
    demonstrate_data_recovery()
    show_user_data_handling()
    show_backup_data_access()

    print("\n" + "=" * 60)
    print("🎯 LOCAL_R2模式总结:")
    print()
    print("✅ 优点:")
    print("   • 性能最优：本地操作无延迟")
    print("   • 成本控制：仅备份不双向同步")
    print("   • 数据安全：云端备份保障")
    print("   • 简单可靠：单向备份逻辑简单")
    print()
    print("⚠️ 限制:")
    print("   • 无实时数据同步")
    print("   • 备份数据需手动恢复查看")
    print("   • 不适合多设备协作场景")
    print()
    print("🎯 适用场景:")
    print("   • 个人用户数据备份")
    print("   • 单机使用环境")
    print("   • 对成本敏感的应用")
    print("   • 数据安全性要求高但协作需求低的场景")


if __name__ == "__main__":
    main()
