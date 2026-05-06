"""
让 tests/ 直接 import 仓库根目录下的 nsz 包，无需 pip install。

另外：上游 nicoboss/nsz 的 nsz.nut.Print 在 import 时会读 sys.argv 并跑
ParseArguments.parse()，pytest 的命令行参数会让它直接 SystemExit。这里在
import 任何 nsz 子模块之前先把 argv 清成只有程序名。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 隔离 pytest argv 不让 nsz.ParseArguments 在 import 副作用里炸掉
_real_argv = sys.argv
sys.argv = [_real_argv[0]] if _real_argv else ["pytest"]
try:
    import nsz  # noqa: F401  触发并完成模块级初始化
finally:
    sys.argv = _real_argv
