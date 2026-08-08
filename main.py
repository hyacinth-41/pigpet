"""根目录 shim：python main.py 也可启动（等价于 python -m pigpet）。

支持 --selftest（P2 自动化验证，跑完自动退出）。
"""

import sys

from pigpet.main import run

if __name__ == "__main__":
    selftest = "--selftest" in sys.argv
    if selftest:
        sys.argv = [a for a in sys.argv if a != "--selftest"]
    raise SystemExit(run(selftest=selftest))
