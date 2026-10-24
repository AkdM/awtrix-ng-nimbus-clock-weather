#!/usr/bin/env python3
"""Generate dist/nimbus-<clock>.ax from src/nimbus.ax and src/layouts.json.

Lines between `# @if <clock>` and `# @end` go only into that clock's file, and the marker lines
into none. Each clock gets its own `# @display` line and the layout constants its layout lists
(FX: x of the 32 px frame, BY: row of the week bar; the TC001's). The files are minified, made for
the clock and not for people: the clock holds a script's whole source in memory to install it, to
update it and to list its settings. src/nimbus.ax is the readable source. `--check` exits with 1
when a file in dist/ is out of date.
"""
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINES = (("display", r"^# @display .*$", "# @display %s"),
         ("fx", r"^var FX = \d+", "var FX = %d"),
         ("by", r"^var BY = \d+", "var BY = %d"))


def strip(src):
    """The script without comments, blank lines and indentation (Berry needs none). A # outside a
    string starts a comment; the header's "# @" lines stay whole."""
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
            out.append(line.strip())
    return "\n".join(out) + "\n"


KEYWORDS = {"if", "elif", "else", "while", "for", "def", "end", "class", "break", "continue", "return",
            "true", "false", "nil", "var", "do", "import", "as", "try", "except", "raise", "static", "self",
            "super"}
# the methods the firmware calls by name
HOOKS = {"init", "setup", "loop", "draw", "on_show", "on_hide", "on_button", "on_button_event", "on_knob",
         "should_show", "duration"}
# built-in calls and modules a local must not hide
BUILTINS = {"clear", "pixel", "line", "rect", "rect_fill", "circle", "circle_fill", "text", "text_width",
            "text_ink_width", "font", "ramp_text", "scroll_text", "icon", "bar_chart", "line_chart",
            "progress", "effect", "overlay", "rgb", "hsv", "width", "height", "hour", "minute", "second",
            "weekday", "day", "month", "year", "now_ms", "epoch_ms", "size", "str", "int", "real", "num",
            "round", "clamp", "bytes", "list", "map", "log", "print", "type", "classname", "store",
            "settings", "mqtt", "http", "re", "json", "math", "string", "gc", "sensor", "rotation", "timer",
            "shared", "sound", "global", "introspect"}
OPS = ("<<=", ">>=", "..", "==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "+=", "-=", "*=", "/=", "%=",
       "&=", "|=", "^=", "->", ":=")
TOKEN = re.compile(r'\s+|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|0x[0-9A-Fa-f]+|\d+\.\d+|\d+|[A-Za-z_]\w*|'
                   + "|".join(re.escape(o) for o in OPS) + r"|.")


def _names(avoid):
    """Short names in order: a-z, A-Z, then two characters, skipping the ones in avoid."""
    first = string.ascii_lowercase + string.ascii_uppercase
    for a in first:
        if a not in avoid:
            yield a
    for a in first:
        for b in first + string.digits:
            if a + b not in avoid:
                yield a + b


def minify(src, width=200):
    """The script for the clock only: the header's "# @" lines whole, then the code without optional
    spaces, on lines of at most width characters, with short names for the class's members and
    methods (except the hooks the firmware calls) and for each function's parameters, locals and
    loop variables. Globals, the class, built-in calls, setting keys and strings stay as they are.
    Members are renamed where written self.<name>, the only way the script uses them."""
    lines = src.split("\n")
    n_header = 0
    while n_header < len(lines) and lines[n_header].startswith("# @"):
        n_header += 1
    toks, spaced, ws = [], [], True
    for m in TOKEN.finditer("\n".join(lines[n_header:])):
        t = m.group(0)
        if t.isspace():
            ws = True
            continue
        if t == "#":
            sys.exit("src/nimbus.ax: a comment or a misplaced header line is left in the code")
        word = t[0].isalnum() or t[0] == "_"
        toks.append(["word" if word else ("str" if t[0] in "\"'" else "op"), t])
        spaced.append(ws)     # whitespace before it in the source: it matters before "("
        ws = False
    n = len(toks)

    def after_dot(i):
        return i > 0 and toks[i - 1][1] == "."

    # scopes: members and methods of the class, and the names each outermost function binds
    stack, funcs, owner, member_at = [], [], [None] * n, set()
    members = set()

    def outer():
        return next((f for kind, f in stack if kind == "func"), None)

    def names_from(i, stop):
        """Words from token i on, separated by commas, up to the first token in stop."""
        out = []
        while i < n and toks[i][1] not in stop:
            if toks[i][0] == "word":
                out.append(toks[i][1])
            elif toks[i][1] != ",":
                return None
            i += 1
        return out if i < n else None

    i = 0
    while i < n:
        kind, t = toks[i]
        f = outer()
        owner[i] = f
        if kind == "word" and not after_dot(i):
            top = stack[-1][0] if stack else None
            if t == "class":
                stack.append(("class", None))
            elif t == "def":
                named = toks[i + 1][0] == "word"
                if top == "class":
                    if toks[i + 1][1] not in HOOKS:
                        members.add(toks[i + 1][1])
                        member_at.add(i + 1)
                    g = {"locals": set()}
                    funcs.append(g)
                    stack.append(("func", g))
                elif f is None:
                    g = {"locals": set()}           # a module-level function: its name is a global
                    funcs.append(g)
                    stack.append(("func", g))
                else:
                    if named:
                        f["locals"].add(toks[i + 1][1])
                    stack.append(("block", None))
                j = i + 1 + (1 if named else 0)
                params = names_from(j + 1, (")",))
                outer()["locals"].update(params or [])
            elif t in ("if", "while", "for", "do", "try"):
                stack.append(("block", None))
                if t == "for" and f is not None:
                    f["locals"].add(toks[i + 1][1])
            elif t == "end":
                stack.pop()
            elif t == "var":
                j, declared = i + 1, []
                while j < n and toks[j][0] == "word":
                    declared.append(toks[j][1])
                    if j + 2 < n and toks[j + 1][1] == "," and toks[j + 2][0] == "word" and top == "class":
                        j += 2
                    else:
                        break
                if top == "class":
                    members.update(declared)
                    member_at.update(range(i + 1, j + 1, 2))
                elif f is not None:
                    f["locals"].update(declared)
        elif kind == "op" and t == "/" and f is not None:
            params = names_from(i + 1, ("->",))
            if params is not None:
                f["locals"].update(params)
        i += 1

    # names nobody declares: built-in calls, modules, globals, the class
    free = {t for i, (k, t) in enumerate(toks) if k == "word" and not after_dot(i) and i not in member_at
            and not (owner[i] and t in owner[i]["locals"])} - KEYWORDS
    for f in funcs:
        hidden = f["locals"] & (BUILTINS | free)
        if hidden:
            sys.exit("src/nimbus.ax: a local hides a built-in or global name: %s" % ", ".join(sorted(hidden)))

    def ranked(counts):
        return sorted(counts, key=lambda name: (-counts[name][0], counts[name][1]))

    # members by use, the most used get the shortest names
    counts = {}
    for i, (k, t) in enumerate(toks):
        if k == "word" and t in members and (i in member_at or (after_dot(i) and toks[i - 2][1] == "self")):
            c = counts.setdefault(t, [0, i])
            c[0] += 1
    member_map = dict(zip(ranked(counts), _names(KEYWORDS | HOOKS)))
    # each function's names the same way
    local_maps = {}
    for f in funcs:
        counts = {}
        for i, (k, t) in enumerate(toks):
            if owner[i] is f and k == "word" and t in f["locals"] and not after_dot(i):
                c = counts.setdefault(t, [0, i])
                c[0] += 1
        local_maps[id(f)] = dict(zip(ranked(counts), _names(KEYWORDS | free)))

    out_lines, line, prev = lines[:n_header], "", None
    for i, (k, t) in enumerate(toks):
        if k == "word":
            if i in member_at or (t in member_map and after_dot(i) and toks[i - 2][1] == "self"):
                t = member_map[t]
            elif owner[i] is not None and not after_dot(i):
                t = local_maps[id(owner[i])].get(t, t)
        sep, breakable = "", True
        if prev is not None:
            pk, pt = prev
            if pk == "word" and k == "word":
                sep = " "
            elif pk == "word" and pt[0].isdigit() and t[0] == ".":
                sep = " "     # 0..E-1 would read as a real number with an exponent
            elif pk == "op" and k == "op" and any(o.startswith(pt + t[0]) for o in OPS):
                sep = " "
            elif t == "(":
                # "f(x)" is a call only without whitespace before "(": keep the source's choice
                # after anything that ends an expression, and never break a line before a call
                ends = pt in (")", "]") or pk == "str" or (pk == "word" and (pt not in KEYWORDS or pt in ("nil", "true", "false", "self")))
                if not spaced[i]:
                    breakable = ends is False
                elif ends:
                    sep = " "
        if line and breakable and len(line) + len(sep) + len(t) > width:
            out_lines.append(line)
            line = t
        else:
            line += sep + t
        prev = (k, t)
    if line:
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def render(src, clock, layout, clocks, minified=True):
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
    return minify(out) if minified else out


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
