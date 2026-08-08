"""python -m pigpet 入口。

解析 --selftest（P2 自动化验证，跑完自动退出）；其余参数透传给 Qt。
"""

import sys

from .main import run

if __name__ == "__main__":
    selftest = "--selftest" in sys.argv
    if selftest:
        sys.argv = [a for a in sys.argv if a != "--selftest"]
    raise SystemExit(run(selftest=selftest))
