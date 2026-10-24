"""Drive the AWTRIX NG simulators (sim/sim.sh) over their HTTP API for the Nimbus tests."""
import json
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLOCKS = {"tc001": {"port": 8080, "fx": 0, "by": 7}, "tc002": {"port": 8081}}
SWITCH = 2.5  # seconds to let the device's app transition finish after switching apps

# The firmware's small font as text(x, 6, ...) draws it: rows 1-5, "#" lit, 4 px advance
FONT = {
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
    "-": ["...", "...", "###", "...", "..."], "%": ["#.#", "..#", ".#.", "#..", "#.#"],
    "?": ["###", "..#", ".#.", "...", ".#."], ":": [".", "#", ".", "#", "."], ".": [".", ".", ".", ".", "#"],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
}
# its capitals: one art string per letter ("#" lit, "/" next row), widths from 1 to 5
CAPS = ("##/#.#/###/#.#/#.#", "##/#.#/##/#.#/##", ".#/#.#/#/#.#/.#", "##/#.#/#.#/#.#/##", "###/#/###/#/###",
        "###/#/###/#/#", ".##/#/#.#/#.#/.##", "#.#/#.#/###/#.#/#.#", "#/#/#/#/#", "..#/..#/..#/#.#/.#",
        "#.#/#.#/##/#.#/#.#", "#/#/#/#/###", "#...#/##.##/#.#.#/#...#/#...#", "#..#/##.#/#.##/#..#/#..#",
        ".#/#.#/#.#/#.#/.#", "###/#.#/##/#/#", ".#/#.#/#.#/#.#/.###", "###/#.#/##/#.#/#.#", "###/#/###/..#/###",
        "###/.#/.#/.#/.#", "#.#/#.#/#.#/#.#/###", "#.#/#.#/#.#/#.#/.#", "#...#/#...#/#...#/#.#.#/.#.#",
        "#.#/#.#/.#/#.#/#.#", "#.#/#.#/###/..#/##", "###/..#/.#/#/###")
for _i, _art in enumerate(CAPS):
    _rows = _art.split("/")
    FONT[chr(65 + _i)] = [r.ljust(max(map(len, _rows)), ".") for r in _rows]
# matrix-chunky8x6, the TC002's big digits: 7 rows, 5 px wide
CHUNKY = {
    "0": ["#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#####"],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "2": ["#####", "....#", "....#", "#####", "#....", "#....", "#####"],
    "3": ["#####", "....#", "....#", "#####", "....#", "....#", "#####"],
    "4": ["#...#", "#...#", "#...#", "#####", "....#", "....#", "....#"],
    "5": ["#####", "#....", "#....", "#####", "....#", "....#", "#####"],
    "6": ["#####", "#....", "#....", "#####", "#...#", "#...#", "#####"],
    "7": ["#####", "....#", "....#", "....#", "....#", "....#", "....#"],
    "8": ["#####", "#...#", "#...#", "#####", "#...#", "#...#", "#####"],
    "9": ["#####", "#...#", "#...#", "#####", "....#", "....#", "#####"],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
}


def hexcolor(c):
    return "#%06X" % c


class Sim:
    def __init__(self, clock):
        self.clock = clock
        self.base = "http://localhost:%d/api/v1" % CLOCKS[clock]["port"]
        self.fx = CLOCKS[clock].get("fx")   # TC001 only: x of the 32 px frame, row of the week bar
        self.by = CLOCKS[clock].get("by")
        self.w, self.h = (32, 8) if clock == "tc001" else (52, 16)

    def req(self, method, path, body=None, raw=None, timeout=40):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        ctype = "text/plain" if raw is not None else "application/json"
        r = urllib.request.Request(self.base + path, method=method, data=data, headers={"Content-Type": ctype})
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            text = resp.read().decode()
        return json.loads(text) if text else None

    def up(self):
        try:
            self.req("GET", "/version", timeout=3)
            return True
        except Exception:
            return False

    def install(self, text=None):
        # a fresh app for every test: deleting it also clears its store, where Nimbus keeps
        # state across restarts (night mode switch, saved brightness); text: a modified copy
        try:
            self.req("DELETE", "/apps/Nimbus")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        raw = text.encode() if text is not None else (ROOT / "dist" / ("nimbus-%s.ax" % self.clock)).read_bytes()
        res = self.req("PUT", "/apps/script/Nimbus", raw=raw)
        assert res.get("error") is None, res
        self.only("Nimbus")
        return res

    def only(self, app):
        names = [a["name"] for a in self.req("GET", "/apps")]
        self.req("PUT", "/apps/order", {"order": [app], "disabled": [n for n in names if n != app]})
        self.req("PUT", "/apps/active", {"name": app})
        time.sleep(SWITCH)

    def config(self, **values):
        self.req("PATCH", "/apps/Nimbus/config", values)
        time.sleep(2.0)  # saving settings restarts the app

    def config_values(self):
        return {f["key"]: f["value"] for f in self.req("GET", "/apps/Nimbus/config")["fields"]}

    def config_defaults(self):
        return {f["key"]: f.get("default") for f in self.req("GET", "/apps/Nimbus/config")["fields"]}

    def settings(self, **values):
        return self.req("PATCH", "/settings", values)

    def screen(self):
        s = self.req("GET", "/display/screen")
        return s["width"], s["height"], s["pixels"]

    def frames(self, seconds):
        out, t0 = [], time.time()
        while time.time() - t0 < seconds:
            out.append((time.time() - t0, self.screen()[2]))
        return out

    def error(self):
        return next(a.get("error") for a in self.req("GET", "/apps") if a["name"] == "Nimbus")

    def official(self, **settings):
        """The official Time app's frame with these device settings."""
        self.settings(**settings)
        self.only("Time")
        return self.screen()[2]

    def nimbus(self):
        self.only("Nimbus")
        return self.screen()[2]


def script(clock, edits=()):
    """The script build.py makes for clock, with each exact (old, new) replacement made in its
    readable form first, then minified like the files in dist/."""
    sys.path.insert(0, str(ROOT))
    import build
    layouts = json.loads((ROOT / "src" / "layouts.json").read_text())
    plain = build.render((ROOT / "src" / "nimbus.ax").read_text(), clock, layouts[clock], layouts, minified=False)
    for old, new in edits:
        assert plain.count(old) == 1, (plain.count(old), old)
        plain = plain.replace(old, new)
    return build.minify(plain)


def need(clock):
    """The simulator for this clock, or skip the test when it is not running."""
    s = Sim(clock)
    if not s.up():
        raise unittest.SkipTest("%s simulator not running: sim/sim.sh start %s" % (clock, clock))
    return s


def pub(topic, payload, retain=False):
    subprocess.run([str(ROOT / "sim" / "sim.sh"), "pub", topic, payload] + (["-r"] if retain else []), check=True)


def official_settings(cfg, mode=1, red=False):
    """Device settings that make the official Time app draw what Nimbus should draw for cfg.
    mode 1 = calendar (Nimbus by day), mode 0 = plain (Nimbus at night, red=True)."""
    if red:
        tc, act, inact = "#FF0000", "#FF0000", "#C00000"
        wact, winact, show = act, inact, cfg["nbar"]
    else:
        tc = hexcolor(cfg["tcol"])
        act, inact, wact, winact = (hexcolor(cfg[k]) for k in ("wtd", "wod", "wtw", "wow"))
        show = cfg["wbar"]
    return {
        "timeMode": mode, "time24h": cfg["t24"], "timeLeadingZero": cfg["tlz"],
        "timeShowAmPm": cfg["tampm"] if mode == 0 else False, "timeSeparatorMode": cfg["tsep"],
        "timeColor": tc, "calendarHeaderColor": hexcolor(cfg["chc"]),
        "calendarTextColor": hexcolor(cfg["ctc"]), "calendarBodyColor": hexcolor(cfg["cbc"]),
        "weekdayBar": {"show": show, "startOnMonday": cfg["wmon"], "weekendDays": ["saturday", "sunday"],
                       "activeColor": act, "inactiveColor": inact,
                       "weekendActiveColor": wact, "weekendInactiveColor": winact},
    }


# Nimbus's date formats as the official date settings
DATE_FORMATS = {"dd.mm.yy": ("dayMonthYear", "dot"), "mm/dd/yy": ("monthDayYear", "slash"),
                "yy-mm-dd": ("yearMonthDay", "dash")}


def tc002_settings(cfg, red=False):
    """Device settings that make the TC002's clock draw what Nimbus should draw for cfg; red=True:
    the big face with a red time, which Nimbus shows at night on every face."""
    order, sep = DATE_FORMATS[cfg["dfmt"]]
    return {
        "clockFace": "big" if red else cfg["face"], "calendarAnimation": False,
        "time24h": cfg["t24"], "timeLeadingZero": cfg["tlz"], "timeShowSeconds": False,
        "timeSeparatorMode": cfg["tsep"], "timeColor": "#FF0000" if red else hexcolor(cfg["tcol"]),
        "dateColor": hexcolor(cfg["tcol"]), "dateOrder": order, "dateSeparator": sep,
        "dateYearMode": "twoDigit", "dateMonthNames": False,
        "calendarHeaderColor": hexcolor(cfg["chc"]), "calendarTextColor": hexcolor(cfg["ctc"]),
        "calendarBodyColor": hexcolor(cfg["cbc"]),
        "weekdayBar": {"show": cfg["wbar"], "startOnMonday": cfg["wmon"], "weekendDays": ["saturday", "sunday"],
                       "activeColor": hexcolor(cfg["wtd"]), "inactiveColor": hexcolor(cfg["wod"]),
                       "weekendActiveColor": hexcolor(cfg["wtw"]), "weekendInactiveColor": hexcolor(cfg["wow"])},
    }


def pair(sim, cfg, mode=1, red=False):
    """A Nimbus frame and the official clock's frame for the same configuration and minute."""
    if sim.clock == "tc002":
        want = tc002_settings(cfg, red)
        # the flap cards turn in the first 600 ms of a minute: both frames are taken after that
        while not 2 <= time.localtime().tm_sec <= 50:
            time.sleep(0.5)
    else:
        want = official_settings(cfg, mode, red)
    for _ in range(3):
        m = time.localtime().tm_min
        a = sim.nimbus()
        b = sim.official(**want)
        if time.localtime().tm_min == m:
            return a, b
    raise AssertionError("the minute changed during every attempt")


def diff(a, b, w):
    return [(i % w, i // w, hex(x), hex(y)) for i, (x, y) in enumerate(zip(a, b)) if x != y]


def mirrored(frame, w, h, fx):
    """An official calendar-mode frame rearranged like Nimbus with the clock on the left:
    the calendar box x 0-8 moves to 23-31, the time and week bar x 9-31 move to 0-22."""
    out = [0] * (w * h)
    for y in range(h):
        for x in range(9):
            out[y * w + fx + 23 + x] = frame[y * w + fx + x]
        for x in range(9, 32):
            out[y * w + fx + x - 9] = frame[y * w + fx + x]
    return out


def label(s, x0, color, dot=True):
    """{(x, y): color} of a Nimbus label: the font's characters from x0 on rows 1-5, then the
    2x2 degree dot on rows 1-2 after a 1 px gap."""
    px = {}
    for i, ch in enumerate(s):
        for r, row in enumerate(FONT[ch]):
            for c, v in enumerate(row):
                if v == "#":
                    px[(x0 + 4 * i + c, 1 + r)] = color
    if dot:
        d = x0 + 4 * len(s)
        for p in ((d, 1), (d + 1, 1), (d, 2), (d + 1, 2)):
            px[p] = color
    return px


def region(frame, w, xs, ys):
    """{(x, y): color} of the lit pixels of frame inside the x and y ranges."""
    return {(x, y): frame[y * w + x] for y in ys for x in xs if frame[y * w + x]}


def glyphs(s, x0, y0, font, color):
    """{(x, y): color} of s drawn from a glyph table (FONT or CHUNKY) with its ink from (x0, y0):
    each glyph, then 1 px."""
    px, x = {}, x0
    for ch in s:
        rows = font[ch]
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v == "#":
                    px[(x + c, y0 + r)] = color
        x += len(rows[0]) + 1
    return px


def dot(x, y, color):
    """The 2x2 degree dot."""
    return {(x, y): color, (x + 1, y): color, (x, y + 1): color, (x + 1, y + 1): color}


def held(states, n=8):
    """States that stay on screen for at least n captures in a row (8: about 200 ms): the still
    panels; a transition frame does not last that long."""
    out, run = set(), 1
    for a, b in zip(states, states[1:]):
        run = run + 1 if a == b else 1
        if run >= n:
            out.add(a)
    return out
