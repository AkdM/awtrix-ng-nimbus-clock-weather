#!/usr/bin/env python3
"""Generate dist/nimbus-<clock>.ax from src/nimbus.ax and src/layouts.json.

Lines between `# @if <clock>` and `# @end` go only into that clock's file, and the marker lines
into none. Each clock gets its own `# @display` line and the layout constants its layout lists
(FX: x of the 32 px frame, BY: row of the week bar; the TC001's). The files leave out comments and
blank lines: the clock holds a script's whole source in memory to install or update it, and the
comments were a third of it. `--check` exits with 1 when a file in dist/ is out of date.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINES = (("display", r"^# @display .*$", "# @display %s"),
         ("fx", r"^var FX = \d+", "var FX = %d"),
         ("by", r"^var BY = \d+", "var BY = %d"))


def strip(src):
    """The script without comments and blank lines. A # outside a string starts a comment; the
    header's "# @" lines stay whole."""
    out = []
    for line in src.split("\n"):
        if line.startswith("# @"):
            out.append(line)
            continue
        quote, i = None, 0
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "#":
                if line[i + 1:i + 2] == "-":
                    sys.exit("src/nimbus.ax: block comments (#- -#) are not supported: %s" % line.strip())
                line = line[:i]
                break
            i += 1
        if line.strip():
            out.append(line.rstrip())
    return "\n".join(out) + "\n"


def render(src, clock, layout, clocks):
    out, block = [], None
    for n, line in enumerate(src.split("\n"), 1):
        m = re.match(r"\s*# @if (\S+)\s*$", line)
        if m:
            if block is not None or m.group(1) not in clocks:
                sys.exit("src/nimbus.ax:%d: misplaced or unknown block: %s" % (n, line.strip()))
            block = m.group(1)
        elif re.match(r"\s*# @end\s*$", line):
            if block is None:
                sys.exit("src/nimbus.ax:%d: @end without @if" % n)
            block = None
        elif block is None or block == clock:
            out.append(line)
    if block is not None:
        sys.exit("src/nimbus.ax: @if %s is not closed" % block)
    out = strip("\n".join(out))
    for key, pattern, value in LINES:
        if key in layout:
            out, k = re.subn(pattern, value % layout[key], out, count=1, flags=re.M)
            if k != 1:
                sys.exit("src/nimbus.ax: no line matches %s" % pattern)
    return out


def main():
    src = (ROOT / "src" / "nimbus.ax").read_text()
    layouts = json.loads((ROOT / "src" / "layouts.json").read_text())
    check = "--check" in sys.argv[1:]
    stale = []
    for clock, layout in layouts.items():
        path = ROOT / "dist" / ("nimbus-%s.ax" % clock)
        out = render(src, clock, layout, layouts)
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
