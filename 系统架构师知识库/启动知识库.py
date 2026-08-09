#!/usr/bin/env python3
"""一键启动系统架构师知识库。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / "本地学习服务.py"


def main() -> None:
    try:
        import pypdf  # noqa: F401  # 启动前只检查依赖，不读取任何真题文件。
    except ModuleNotFoundError:
        print("提示：当前 Python 缺少 pypdf，真题仍可预览，但暂不能提取文字关联知识点。")
        print("如需启用关联，可用已安装 pypdf 的 Python 解释器重新启动。")
    print("正在启动知识库：http://127.0.0.1:8017/")
    try:
        subprocess.run([sys.executable, str(SERVICE), "--port", "8017"], check=False)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
