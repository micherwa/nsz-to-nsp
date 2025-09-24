#!/bin/bash

# 批量NSZ转NSP转换脚本
# 自动将input文件夹中的所有NSZ文件转换为NSP文件并保存到output文件夹

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="$SCRIPT_DIR/input"
OUTPUT_DIR="$SCRIPT_DIR/output"

echo "============================================================"
echo "                NSZ批量转换工具 v1.0"
echo "============================================================"
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 检查input目录是否存在
if [ ! -d "$INPUT_DIR" ]; then
    echo "错误：input目录不存在！"
    exit 1
fi

# 创建output目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 查找所有nsz文件
NSZ_FILES=()
while IFS= read -r -d '' file; do
    NSZ_FILES+=("$file")
done < <(find "$INPUT_DIR" -name "*.nsz" -type f -print0 2>/dev/null)

if [ ${#NSZ_FILES[@]} -eq 0 ]; then
    echo "在input目录中没有找到任何.nsz文件"
    exit 0
fi

echo "找到 ${#NSZ_FILES[@]} 个NSZ文件："

# 显示找到的文件
for i in "${!NSZ_FILES[@]}"; do
    RELATIVE_PATH="${NSZ_FILES[$i]#$INPUT_DIR/}"
    echo "  $((i+1)). $RELATIVE_PATH"
done
echo ""

# 询问用户是否继续
read -p "是否开始转换? (y/n): " CONFIRM
case "$CONFIRM" in
    [yY]|[yY][eE][sS]|是)
        ;;
    *)
        echo "已取消转换"
        exit 0
        ;;
esac

echo ""
echo "开始批量转换..."
echo "============================================================"

SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_FILES=()

for i in "${!NSZ_FILES[@]}"; do
    NSZ_FILE="${NSZ_FILES[$i]}"
    RELATIVE_PATH="${NSZ_FILE#$INPUT_DIR/}"
    
    echo ""
    echo "[$((i+1))/${#NSZ_FILES[@]}] 正在转换: $RELATIVE_PATH"
    
    # 获取文件夹路径（保持目录结构）
    RELATIVE_DIR=$(dirname "$RELATIVE_PATH")
    TARGET_OUTPUT_DIR="$OUTPUT_DIR/$RELATIVE_DIR"
    
    # 创建目标目录（如果不存在）
    mkdir -p "$TARGET_OUTPUT_DIR"
    echo "  输出到: $TARGET_OUTPUT_DIR"
    
    # 执行转换命令（使用虚拟环境）
    if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
        PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    else
        PYTHON_CMD="python3"
    fi
    
    if "$PYTHON_CMD" "$SCRIPT_DIR/nsz.py" -D -o "$TARGET_OUTPUT_DIR" "$NSZ_FILE" >/dev/null 2>&1; then
        echo "  ✓ 转换成功"
        ((SUCCESS_COUNT++))
    else
        echo "  ✗ 转换失败"
        ((FAILED_COUNT++))
        FAILED_FILES+=("$RELATIVE_PATH")
    fi
done

# 显示转换结果
echo ""
echo "============================================================"
echo "转换完成！"
echo "成功转换: $SUCCESS_COUNT 个文件"
echo "转换失败: $FAILED_COUNT 个文件"

if [ ${#FAILED_FILES[@]} -gt 0 ]; then
    echo "失败的文件："
    for FAILED_FILE in "${FAILED_FILES[@]}"; do
        echo "  - $FAILED_FILE"
    done
fi

echo ""
echo "转换后的NSP文件已保存到: $OUTPUT_DIR"
echo "============================================================"
