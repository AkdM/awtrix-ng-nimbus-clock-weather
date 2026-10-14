"""Nimbus on the TC002 against the TC002's own clock app (the TC002 simulator, see sim/Dockerfile)."""
import time
import unittest

from simlib import CHUNKY, FONT, ROOT, diff, dot, glyphs, held, need, pair, pub, region

W = 52
BASE = dict(t24=True, tlz=True, tsep="steady", tcol=0xFFFFFF, face="sheet", chc=0xFF0000, ctc=0x000000,
            cbc=0xFFFFFF, canim=False, dfmt="dd.mm.yy", wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666,
            wtw=0xFFFFFF, wow=0x666666, panels="date", ddur=10, pdur=3, tran="none", rtopic="", htopic="",
            rcol=0xFFFFFF, hcol=0x00AAFF, night=False, nauto=False, nbar=True, npause=False, nbri=0, ntopic="")
COLORS = {"tcol": 0x00FF00, "chc": 0x0000FF, "ctc": 0xFF00FF, "cbc": 0xFFFF00,
          "wtd": 0xFF0000, "wod": 0x00FFFF, "wtw": 0x0000FF, "wow": 0x804000}
FACES = {
    "sheet": [{}, {"t24": False}, {"t24": False, "tlz": False}, {"tlz": False}, {"wbar": False}, {"wmon": False},
              COLORS],
    "ring": [{}, {"wbar": False}, COLORS],
    "flap": [{}, {"t24": False, "tlz": False}, COLORS],
    "big": [{}, {"t24": False, "tlz": False}, {"dfmt": "mm/dd/yy"}, {"dfmt": "yy-mm-dd"}, COLORS],
}
# small icons of the big face's bottom row (src/nimbus.ax), by name
ICONS = {"thermometer": ".L/.L/.R/RRR/RRR", "house": "..O/.OOO/OOOOO/.WWW/.W.W", "drop": "..B/.BBB/BWBBB/BBBBB/.BBB"}
PALETTE = {"O": 0xFF7800, "W": 0xFFFFFF, "L": 0xB4B4B4, "B": 0x2890FF, "R": 0xFF3030}


def icon(name, x0, y0):
    return {(x0 + x, y0 + y): PALETTE[ch] for y, row in enumerate(ICONS[name].split("/"))
            for x, ch in enumerate(row) if ch in PALETTE}


def wait_for(sim, pred, seconds=15):
    t0 = time.time()
    while time.time() - t0 < seconds:
        f = sim.screen()[2]
        if pred(f):
            return f
    raise AssertionError("condition not met within %d s" % seconds)


class Faces(unittest.TestCase):
    def test_match_the_official_clock(self):
        sim = need("tc002")
        sim.install()
        for face, cases in FACES.items():
            for case in cases:
                cfg = dict(BASE, face=face, **case)
                sim.config(**cfg)
                a, b = pair(sim, cfg)
                self.assertEqual(diff(a, b, W), [], "%s %s" % (face, case))


class Night(unittest.TestCase):
    def test_big_red_time_centred_and_the_week_bar_on_every_face(self):
        sim = need("tc002")
        sim.install()
        for face, case in (("sheet", {}), ("flap", {"t24": False}), ("big", {"nbar": False})):
            cfg = dict(BASE, face=face, night=True, **case)
            sim.config(**cfg)
            a, b = pair(sim, cfg, red=True)
            # the official big face's time (its rows 0-9), centred on the display: rows 3-12
            self.assertEqual(diff(a[3 * W:13 * W], b[:10 * W], W), [], "%s %s" % (face, case))
            self.assertEqual(region(a, W, range(W), [0, 1, 2, 13, 14]), {}, face)
            bar = region(a, W, range(W), [15])
            if cfg["nbar"]:
                # 4 px segments from x 9 to 42: today red, the other days dark red
                self.assertEqual(sorted(x for x, _ in bar), [9 + 5 * i + k for i in range(7) for k in range(4)])
                self.assertEqual(sorted(bar.values()).count(0xFF0000), 4)
                self.assertEqual(set(bar.values()), {0xFF0000, 0xC00000})
            else:
                self.assertEqual(bar, {}, face)


def sheet_px(day, label, chc, cbc, ctc):
    """{(x, y): color} of the lit pixels of a `sheet` face's sheet: header rows 0-6, label ink
    from row 1 centred in 15 px, paper below, the chunky day number centred on rows 8-14."""
    g = {(x, y): chc if y < 7 else cbc for y in range(16) for x in range(15)}
    lw = sum(len(FONT[c][0]) + 1 for c in label) - 1
    g.update(glyphs(label, (15 - lw) // 2, 1, FONT, cbc))
    s = str(day)
    g.update(glyphs(s, (15 - (6 * len(s) - 1)) // 2, 8, CHUNKY, ctc))
    return {p: c for p, c in g.items() if c}


def lowest_header(f):
    """The lowest row with the header color in the sheet's 15 columns: below 6 while a sheet falls."""
    return max([y for y in range(16) for x in range(15) if f[y * W + x] == BASE["chc"]], default=-1)


class Animations(unittest.TestCase):
    def test_sheet_tears_off_when_nimbus_appears(self):
        sim = need("tc002")
        sim.install()
        sim.settings(transitionDurationMs=0)   # no app transition: Nimbus is on screen at once
        try:
            sim.config(**dict(BASE, canim=True))
            sim.only("Time")
            sim.req("PUT", "/apps/order", {"order": ["Nimbus"], "disabled": ["Time", "Status"]})
            sim.req("PUT", "/apps/active", {"name": "Nimbus"})
            frames = sim.frames(2.5)
        finally:
            sim.settings(transitionDurationMs=1000)

        # yesterday's sheet falls: its header (rows 0-6) goes below row 6, for at most 1.1 s
        falling = [t for t, f in frames if lowest_header(f) > 6]
        self.assertTrue(falling, "the sheet did not fall")
        self.assertLess(falling[-1] - falling[0], 1.2)
        sheet = [tuple(f[y * W + x] for y in range(16) for x in range(16)) for t, f in frames if t > falling[-1]]
        self.assertTrue(sheet and len(set(sheet)) == 1, "the sheet did not settle")

    def test_sheet_falls_once_the_app_transition_is_over(self):
        # the device's default transition takes 1 s; the sheet falls after it, like the official clock's
        sim = need("tc002")
        sim.install()
        sim.settings(transitionDurationMs=1000)
        sim.config(**dict(BASE, canim=True))
        sim.only("Time")
        sim.req("PUT", "/apps/order", {"order": ["Nimbus"], "disabled": ["Time", "Status"]})
        sim.req("PUT", "/apps/active", {"name": "Nimbus"})
        frames = sim.frames(3)
        falling = [t for t, f in frames if t > 1.2 and lowest_header(f) > 6]
        self.assertTrue(falling and falling[-1] > 1.6, "the sheet does not fall after the transition: %s" % falling[-1:])

    def test_sheet_tears_off_at_midnight(self):
        sim = need("tc002")
        sim.install()
        sim.config(**dict(BASE, canim=True, ctc=0x0000FF))
        sim.only("Nimbus")
        system = sim.req("GET", "/system")
        # a time zone whose midnight comes 6 s from now (east of UTC: positive)
        now = time.time()
        east = (86400 - 6 - int(now) % 86400) % 86400
        if east > 43200:
            east -= 86400
        a = abs(east)
        tz = "NMB%s%d:%02d:%02d" % ("-" if east >= 0 else "+", a // 3600, a % 3600 // 60, a % 60)
        tomorrow = time.gmtime(now + east + 10).tm_mday
        try:
            sim.req("PUT", "/system", {"tz": tz, "tzName": "Etc/Nimbus"})
            frames = sim.frames(9)
        finally:
            sim.req("PUT", "/system", {"tz": system["tz"], "tzName": system["tzName"]})

        falling = [t for t, f in frames if t > 3 and lowest_header(f) > 6]
        self.assertTrue(falling, "no tear-off at midnight")
        self.assertTrue(4 < falling[0] < 8, falling[0])
        s = str(tomorrow)
        digits = {p for p, c in region(frames[-1][1], W, range(15), range(8, 15)).items() if c == 0x0000FF}
        self.assertEqual(digits, set(glyphs(s, (15 - (6 * len(s) - 1)) // 2, 8, CHUNKY, 0)))

    def test_yesterday_across_month_and_year_ends(self):
        sim = need("tc002")
        real = (ROOT / "dist" / "nimbus-tc002.ax").read_text()
        cases = (((1, 3, 2024), (29, "FEB")), ((1, 3, 2023), (28, "FEB")), ((1, 1, 2025), (31, "DEC")),
                 ((1, 5, 2025), (30, "APR")), ((15, 10, 2026), (14, "OCT")))
        for (d, m, y), (yd, ym) in cases:
            # a copy on that date whose tear-off stays at its start: yesterday's sheet, whole
            demo = real
            for old, new in (("      var d = day()\n", "      var d = %d\n" % d),
                             ("        var mo = month()\n        var y = year()\n",
                              "        var mo = %d\n        var y = %d\n" % (m, y)),
                             ("        if e >= 1100\n", "        if false\n"),
                             ("          var q = e / 1100.0\n", "          var q = 0.0\n"),
                             ("    self.lk = [0, 0, 0, 0, 0]\n", "    self.lk = [0, 0, 0, 0, 0]\n    self.tear = 0\n")):
                self.assertEqual(demo.count(old), 1, old)
                demo = demo.replace(old, new)
            sim.install(demo)
            sim.config(**dict(BASE, canim=True, ctc=0x0000FF))
            sim.only("Nimbus")
            expected = sheet_px(yd, ym, BASE["chc"], BASE["cbc"], 0x0000FF)
            self.assertEqual(region(sim.screen()[2], W, range(15), range(16)), expected, "%d.%d.%d" % (d, m, y))
        sim.install()

    def test_flap_cards_fold_at_the_minute(self):
        sim = need("tc002")
        sim.install()
        sim.config(**dict(BASE, face="flap"))
        sim.only("Nimbus")
        while time.localtime().tm_sec != 58:
            time.sleep(0.2)
        frames = sim.frames(3.5)
        cards = [tuple(f[y * W + x] for y in range(16) for x in range(17, W)) for _, f in frames]
        before, after = cards[0], cards[-1]
        self.assertNotEqual(before, after, "the minute did not change")
        folding = [t for (t, _), c in zip(frames, cards) if c not in (before, after)]
        self.assertTrue(folding, "no fold")
        self.assertLess(folding[-1] - folding[0], 0.7)
        self.assertTrue(any(0x474747 in c for c in cards), "no moving flap (the time color at 28 %)")


class Boot(unittest.TestCase):
    def test_dashes_until_the_time_is_known(self):
        # right after a boot without network every time call answers -1 (now_ms() excepted): a copy
        # whose time calls always do
        sim = need("tc002")
        real = (ROOT / "dist" / "nimbus-tc002.ax").read_text()
        calls = "".join("def %s() return -1 end\n" % c
                        for c in ("hour", "minute", "second", "day", "month", "year", "weekday", "epoch_ms"))
        demo = real.replace("import string\n", "import string\n" + calls, 1)
        self.assertNotEqual(demo, real)
        sim.install(demo)
        try:
            for face in ("sheet", "flap", "big"):
                sim.config(**dict(BASE, face=face, panels="date,temp", ddur=1, pdur=1))
                sim.only("Nimbus")
                self.assertIsNone(sim.error(), face)
                f = sim.screen()[2]
                # the dashes of the face's time, nothing in the panel area (the bottom row on the big face)
                area = (range(W), range(10, 16)) if face == "big" else (range(16), range(16))
                self.assertEqual(region(f, W, *area), {}, face)
                lit = set(region(f, W, range(W), range(16)).values())
                self.assertTrue(lit and lit <= {0xFFFFFF, 0x2E2E2E}, "%s: %s" % (face, sorted(lit)))
        finally:
            sim.install()


class Panels(unittest.TestCase):
    def setUp(self):
        self.sim = need("tc002")
        self.sim.install()
        pub("nimbus/test/room", "", retain=True)
        pub("nimbus/test/hum", "", retain=True)

    def shows(self, xs, ys, expected, seconds=8):
        return wait_for(self.sim, lambda f: region(f, W, xs, ys) == expected, seconds)

    def test_values_in_the_sheet_column(self):
        self.sim.config(**dict(BASE, panels="room,humidity", rtopic="nimbus/test/room", htopic="nimbus/test/hum",
                               ddur=1, pdur=1))
        col = (range(16), range(16))
        pub("nimbus/test/room", "21.5")
        # chunky "22" (11 px), 1 px, the 2x2 dot: 14 px from x 1, rows 4-10
        self.shows(*col, {**glyphs("22", 1, 4, CHUNKY, 0xFFFFFF), **dot(13, 4, 0xFFFFFF)})
        pub("nimbus/test/hum", "45")
        # chunky "45", 1 px, the small "%" level with the digits' last five rows: 15 px from x 0
        self.shows(*col, {**glyphs("45", 0, 4, CHUNKY, 0x00AAFF), **glyphs("%", 12, 6, FONT, 0x00AAFF)})
        pub("nimbus/test/hum", "100")
        # chunky "100%" would take 21 px: the small font, 15 px from x 0, rows 5-9
        self.shows(*col, glyphs("100%", 0, 5, FONT, 0x00AAFF))
        pub("nimbus/test/room", "-12")
        # chunky "-12" would take 20 px: the small font, 14 px from x 1
        self.shows(*col, {**glyphs("-12", 1, 5, FONT, 0xFFFFFF), **dot(13, 5, 0xFFFFFF)})

    def test_a_value_too_wide_for_the_small_font_bounces_in_the_column(self):
        self.sim.config(**dict(BASE, panels="room", rtopic="nimbus/test/room"))
        pub("nimbus/test/room", "12345")
        wait_for(self.sim, lambda f: f[0] != BASE["chc"] and region(f, W, range(16), range(16)))
        for _, f in self.sim.frames(3):
            px = region(f, W, range(17), range(16))
            self.assertTrue(px and max(x for x, _ in px) <= 15, sorted(px))

    def test_weather_icon_at_double_size(self):
        self.sim.config(**dict(BASE, panels="weather"))
        f = wait_for(self.sim, lambda f: region(f, W, range(16), range(16)) and
                     0x666666 not in region(f, W, range(16), range(16)).values())
        for (x, y), c in region(f, W, range(16), range(16)).items():
            self.assertEqual(f[(y & ~1) * W + (x & ~1)], c, "not a 2x2 square at %d,%d" % (x, y))

    def test_bottom_row_of_the_big_face(self):
        self.sim.config(**dict(BASE, face="big", panels="room,humidity", rtopic="nimbus/test/room",
                               htopic="nimbus/test/hum", ddur=1, pdur=1))
        row = (range(W), range(10, 16))
        pub("nimbus/test/room", "21.5")
        # the house from x 1, "22" and the dot ending at x 50, rows 11-15
        self.shows(*row, {**icon("house", 1, 11), **glyphs("22", 41, 11, FONT, 0xFFFFFF), **dot(49, 11, 0xFFFFFF)})
        pub("nimbus/test/hum", "45")
        self.shows(*row, {**icon("drop", 1, 11), **glyphs("45%", 40, 11, FONT, 0x00AAFF)})

    def test_weather_condition_on_the_bottom_row(self):
        self.sim.config(**dict(BASE, face="big", panels="weather"))
        words = ["CLEAR", "PARTLY", "CLOUDY", "FOG", "RAIN", "SNOW", "STORM"]
        right = {w: glyphs(w, 51 - (sum(len(FONT[c][0]) + 1 for c in w) - 1), 11, FONT, 0xFFFFFF) for w in words}
        f = wait_for(self.sim, lambda f: region(f, W, range(12, W), range(10, 16)) in right.values())
        self.assertTrue(region(f, W, range(0, 9), range(11, 16)), "no icon")

    def test_condition_words_in_each_language_and_your_own(self):
        real = (ROOT / "dist" / "nimbus-tc002.ax").read_text()
        # rain from the start, whatever the weather and even when its answer is late
        demo = real.replace("    self.ico = n\n", "    self.ico = 5\n", 1)
        demo = demo.replace("    self.lk = [0, 0, 0, 0, 0]\n", "    self.lk = [0, 0, 0, 0, 0]\n    self.ico = 5\n", 1)
        self.assertEqual(demo.count("self.ico = 5"), 2)
        self.sim.install(demo)
        word = (range(9, W), range(10, 16))

        def ends(f, x0):
            px = region(f, W, *word)
            return bool(px) and min(x for x, _ in px) == x0 and max(x for x, _ in px) == 50
        # each language's word for rain (ink widths measured in the firmware's font), ending at x 50
        for lang, width in (("English", 14), ("Español", 21), ("Français", 17), ("Português", 19), ("Deutsch", 20)):
            self.sim.config(**dict(BASE, face="big", panels="weather", wlang=lang))
            f = wait_for(self.sim, lambda f: ends(f, 51 - width))
            self.assertEqual(set(region(f, W, *word).values()), {0xFFFFFF}, lang)
        # your own word for rain, the fifth; spaces around it are dropped, empty entries keep the language's
        self.sim.config(**dict(BASE, face="big", panels="weather", wlang="Français", wtext="SEC, , ,, WET "))
        self.shows(*word, glyphs("WET", 51 - (sum(len(FONT[c][0]) + 1 for c in "WET") - 1), 11, FONT, 0xFFFFFF))
        self.sim.config(**dict(BASE, face="big", panels="weather", wlang="Français", wtext="SEC"))
        wait_for(self.sim, lambda f: ends(f, 51 - 17))                       # PLUIE
        # too wide for x 9-50: it bounces there, next to the icon
        self.sim.config(**dict(BASE, face="big", panels="weather", wtext=",,,,HEAVY RAIN ALL DAY"))
        wait_for(self.sim, lambda f: region(f, W, *word) and not ends(f, 51 - 14))
        frames = [f for _, f in self.sim.frames(3)]
        for f in frames:
            px = region(f, W, range(8, W), range(10, 16))
            self.assertTrue(px and min(x for x, _ in px) >= 9 and max(x for x, _ in px) <= 50, sorted(px)[:3])
        self.assertGreater(len({tuple(sorted(region(f, W, *word))) for f in frames}), 1, "the word does not move")

    def test_placeholders_without_weather(self):
        real = (ROOT / "dist" / "nimbus-tc002.ax").read_text()
        demo = real.replace("http://api.open-meteo.com/v1/forecast", "http://127.0.0.1:9/v1/forecast", 1)
        self.assertNotEqual(demo, real)
        self.sim.install(demo)
        grey = 0x666666
        self.sim.config(**dict(BASE, panels="temp"))
        self.shows(range(16), range(16), {**glyphs("--", 1, 4, CHUNKY, grey), **dot(13, 4, grey)})
        self.sim.config(**dict(BASE, panels="weather"))
        self.shows(range(16), range(16), glyphs("?", 6, 5, FONT, grey))
        self.sim.config(**dict(BASE, face="big", panels="temp"))
        self.shows(range(W), range(10, 16), {**icon("thermometer", 1, 11), **glyphs("--", 41, 11, FONT, grey),
                                             **dot(49, 11, grey)})
        self.sim.config(**dict(BASE, face="big", panels="weather"))
        self.shows(range(W), range(10, 16), glyphs("?", 48, 11, FONT, grey))


TRANSITIONS = ["wipe", "fade", "morph", "down", "up", "left", "right", "none"]


class Transitions(unittest.TestCase):
    AREA = {"sheet": (range(16), range(16)), "big": (range(W), range(10, 16))}

    def check(self, face):
        sim = need("tc002")
        sim.install()
        xs, ys = self.AREA[face]
        inside = {(x, y) for x in xs for y in ys}

        def area(f):
            return tuple(f[y * W + x] for y in ys for x in xs)

        def outside(f):
            return [v for i, v in enumerate(f) if (i % W, i // W) not in inside]
        sim.config(**dict(BASE, face=face, panels="date"))
        date = area(sim.screen()[2])
        for tr in TRANSITIONS:
            sim.config(**dict(BASE, face=face, panels="date,temp", ddur=2, pdur=2, tran=tr))
            # each restart fetches the weather; until it answers the temperature is a grey "--"
            wait_for(sim, lambda f: area(f) != date and any(area(f)) and 0x666666 not in area(f))
            m = time.localtime().tm_min
            frames = sim.frames(6)
            if time.localtime().tm_min != m:
                frames = sim.frames(6)
            base = outside(frames[0][1])
            for _, f in frames:
                self.assertEqual(outside(f), base, "%s %s: pixels outside the panel area changed" % (face, tr))
            states = [area(f) for _, f in frames]
            # 16 captures (about 400 ms): a wipe over the big face's sparse bottom row can hold one
            # state for up to 180 ms
            still = held(states, 16) - {date}
            self.assertEqual(len(still), 1, "%s %s: still frames other than the date: %d" % (face, tr, len(still)))
            temp = still.pop()
            middle = set(states) - {date, temp}
            if tr == "none":
                self.assertEqual(middle, set(), tr)
            else:
                self.assertTrue(middle, "%s %s: no transition frame seen" % (face, tr))
            if tr == "morph":
                for s in middle:
                    self.assertTrue(all(v in (a, b) for v, a, b in zip(s, date, temp)), "morph pixel from neither panel")

    def test_sheet_faces(self):
        self.check("sheet")

    def test_big_face(self):
        self.check("big")

    def test_night_mode_during_a_transition(self):
        sim = need("tc002")
        sim.install()
        pub("nimbus/test/night", "", retain=True)
        sim.config(**dict(BASE, panels="date,temp", ddur=1, pdur=1, tran="morph", ntopic="nimbus/test/night"))
        time.sleep(1.7)
        pub("nimbus/test/night", "on")
        frames = sim.frames(3)
        pub("nimbus/test/night", "off")
        for t, f in frames:
            if t > 1.2:
                self.assertEqual(region(f, W, range(W), [0, 1, 2, 13, 14]), {})
                self.assertTrue(all(v & 0xFFFF == 0 for v in f if v), "a pixel that is not red")


if __name__ == "__main__":
    unittest.main()
