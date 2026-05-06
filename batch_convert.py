#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量NSZ转NSP转换脚本
自动将input文件夹中的所有NSZ文件转换为NSP文件并保存到output文件夹
"""

import os
import sys
from pathlib import Path
import subprocess

def find_nsz_files(input_dir):
    """
    递归查找input目录中的所有nsz文件
    """
    nsz_files = []
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"错误：输入目录 {input_dir} 不存在")
        return nsz_files
    
    # 递归查找所有.nsz文件
    for file_path in input_path.rglob("*.nsz"):
        nsz_files.append(file_path)
    
    return nsz_files

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='批量NSZ转NSP转换工具')
    parser.add_argument('--auto', '-y', action='store_true', help='自动确认，不询问用户')
    parser.add_argument('--verify', action='store_true', help='启用完整文件验证（最慢但最严格，验证 NSP SHA256 与原 NSZ 对齐）')
    # 默认开启 quick-verify + fix-padding：
    # - quick-verify 让 NCA hash 不一致时直接 [CORRUPTED] 落到日志，方便定位坏包
    # - fix-padding 把 PFS0 header padding 拉到 nxdumptool / no-intro 标准，Ryujinx 兼容性最佳
    parser.add_argument('--quick-verify', dest='quick_verify', action='store_true', default=True, help='启用快速验证（默认开启，验证NCA哈希）')
    parser.add_argument('--no-quick-verify', dest='quick_verify', action='store_false', help='关闭快速验证')
    parser.add_argument('--fix-padding', dest='fix_padding', action='store_true', default=True, help='修复PFS0填充以提高模拟器兼容性（默认开启）')
    parser.add_argument('--no-fix-padding', dest='fix_padding', action='store_false', help='关闭PFS0填充修复（不推荐）')
    parser.add_argument('--verbose', '-v', action='store_true', help='转换成功时也打印 nsz.py 的完整日志')
    args = parser.parse_args()
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    
    print("=" * 60)
    print("           NSZ批量转换工具 v1.1")
    print("=" * 60)
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    if args.verify:
        print("验证模式: 🔍 完整文件验证（较慢但最安全）")
    elif args.quick_verify:
        print("验证模式: ⚡ 快速验证（推荐，验证NCA哈希）")
    else:
        print("验证模式: ⚠️  无验证（最快但不推荐用于重要文件）")
    
    if args.fix_padding:
        print("填充修复: 🔧 已启用（提高模拟器兼容性）")
    
    print()
    
    # 确保output目录存在
    output_dir.mkdir(exist_ok=True)
    
    # 查找所有nsz文件
    nsz_files = find_nsz_files(input_dir)
    
    if not nsz_files:
        print("在input目录中没有找到任何.nsz文件")
        return
    
    print(f"找到 {len(nsz_files)} 个NSZ文件:")
    for i, file_path in enumerate(nsz_files, 1):
        relative_path = file_path.relative_to(input_dir)
        print(f"  {i}. {relative_path}")
    print()
    
    # 询问用户是否继续
    if args.auto:
        print("自动模式：跳过用户确认")
        confirm = 'y'
    else:
        try:
            confirm = input("是否开始转换? (y/n): ").lower().strip()
        except EOFError:
            print("检测到非交互环境，使用自动模式")
            confirm = 'y'
    
    if confirm not in ['y', 'yes', '是']:
        print("已取消转换")
        return
    
    print("\n开始批量转换...")
    print("=" * 60)
    
    success_count = 0
    failed_files = []
    suspicious_files = []  # 进程退出码 0，但日志里有 [CORRUPTED]/[MISSMATCH]/missing key 的"灰色"产物

    # nsz.py 自身打日志时常用的失败/告警关键字
    SUSPICIOUS_PATTERNS = (
        '[CORRUPTED]',
        '[MISMATCH]',
        '[MISSMATCH]',  # 上游 typo，保留兼容
        'missing from',
        'crc32 missmatch',
        'Failed to load default keys',
    )

    for i, nsz_file in enumerate(nsz_files, 1):
        try:
            relative_path = nsz_file.relative_to(input_dir)
            print(f"\n[{i}/{len(nsz_files)}] 正在转换: {relative_path}")
            
            # 获取文件夹路径（保持目录结构）
            relative_dir = relative_path.parent
            target_output_dir = output_dir / relative_dir
            
            # 创建目标目录（如果不存在）
            target_output_dir.mkdir(parents=True, exist_ok=True)
            print(f"  输出到: {target_output_dir}")
            
            # 构建NSZ命令行，使用虚拟环境中的Python
            venv_python = script_dir / "venv" / "bin" / "python"
            if venv_python.exists():
                python_executable = str(venv_python)
            else:
                python_executable = sys.executable
            
            cmd = [
                python_executable,  # Python解释器路径
                str(script_dir / "nsz.py"),  # nsz.py脚本路径
                "-D",  # 解压缩选项
                "-o", str(target_output_dir),  # 输出到对应的子目录
            ]
            
            # 添加验证选项
            if args.verify:
                cmd.append("--verify")
                print("  🔍 启用完整文件验证")
            elif args.quick_verify:
                cmd.append("--quick-verify")
                print("  ⚡ 启用快速验证")
            
            # 添加填充修复选项
            if args.fix_padding:
                cmd.append("--fix-padding")
                print("  🔧 启用填充修复")
            
            cmd.append(str(nsz_file))  # 输入文件
            
            # 执行转换命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

            combined_log = (result.stdout or '') + (result.stderr or '')
            hits = [p for p in SUSPICIOUS_PATTERNS if p in combined_log]

            if result.returncode == 0 and not hits:
                print(f"  ✓ 转换成功")
                if args.verbose and combined_log.strip():
                    print(combined_log.rstrip())
                success_count += 1
            elif result.returncode == 0 and hits:
                # 工具说成功，但日志里有 hash 不一致 / 缺 key 之类的硬伤
                # 不能再当成功——这种 NSP 装到 Ryujinx 里大概率挂载失败或进游戏崩
                print(f"  ⚠ 转换看似成功但日志里有可疑信号: {', '.join(hits)}")
                print(combined_log.rstrip())
                suspicious_files.append(str(relative_path))
            else:
                print(f"  ✗ 转换失败 (exit={result.returncode})")
                # 失败时把 stdout / stderr 都倒出来，nsz.py 的关键诊断（缺 key / corrupted / NCZSECTN 错）通常在 stdout
                if combined_log.strip():
                    print(combined_log.rstrip())
                failed_files.append(str(relative_path))
                
        except Exception as e:
            print(f"  ✗ 转换失败: {e}")
            failed_files.append(str(nsz_file.relative_to(input_dir)))
    
    # 显示转换结果
    print("\n" + "=" * 60)
    print("转换完成!")
    print(f"成功转换: {success_count} 个文件")
    if failed_files:
        print(f"转换失败: {len(failed_files)} 个文件")
        print("失败的文件:")
        for failed_file in failed_files:
            print(f"  - {failed_file}")
    if suspicious_files:
        print(f"⚠ 可疑产物（退出码0但日志有 corrupted/missing key 等告警）: {len(suspicious_files)} 个")
        print("   建议先别拷进 Ryujinx，对照上面输出排查 prod.keys / title.keys 或换源:")
        for f in suspicious_files:
            print(f"  - {f}")

    print(f"\n转换后的NSP文件已保存到: {output_dir}")
    print("=" * 60)

if __name__ == "__main__":
    main()
