#!/usr/bin/env python3
"""Generate dist/nimbus-<clock>.ax from src/nimbus.ax and src/layouts.json.

Each clock gets its own `# @display` line and layout constants (FX: x of the 32 px frame,
BY: row of the week bar). `--check` exits with 1 when a file in dist/ is out of date.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def render(src, layout):
    out = src
    for pattern, value in ((r"^# @display .*$", "# @display %s" % layout["display"]),
                           (r"^var FX = \d+", "var FX = %d" % layout["fx"]),
                           (r"^var BY = \d+", "var BY = %d" % layout["by"])):
        out, n = re.subn(pattern, value, out, count=1, flags=re.M)
        if n != 1:
            sys.exit("src/nimbus.ax: no line matches %s" % pattern)
    return out


def main():
    src = (ROOT / "src" / "nimbus.ax").read_text()
    layouts = json.loads((ROOT / "src" / "layouts.json").read_text())
    check = "--check" in sys.argv[1:]
    stale = []
    for clock, layout in layouts.items():
        path = ROOT / "dist" / ("nimbus-%s.ax" % clock)
        out = render(src, layout)
        if check:
            if not path.exists() or path.read_text() != out:
                stale.append(path.name)
        else:
            path.parent.mkdir(exist_ok=True)
            path.write_text(out)
            print("wrote dist/%s" % path.name)
    if stale:
        print("out of date: %s (run python3 build.py)" % ", ".join(stale))
        sys.exit(1)


if __name__ == "__main__":
    main()
