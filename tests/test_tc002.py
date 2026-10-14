"""Nimbus on the TC002 against the TC002's own clock app (the TC002 simulator, see sim/Dockerfile)."""
import time
import unittest

from simlib import CHUNKY, FONT, ROOT, diff, glyphs, need, pair, region

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
    def test_big_red_time_and_a_centred_week_bar_on_every_face(self):
        sim = need("tc002")
        sim.install()
        for face, case in (("sheet", {}), ("flap", {"t24": False}), ("big", {"nbar": False})):
            cfg = dict(BASE, face=face, night=True, **case)
            sim.config(**cfg)
            a, b = pair(sim, cfg, red=True)
            self.assertEqual([d for d in diff(a, b, W) if d[1] < 10], [], "%s %s" % (face, case))
            self.assertEqual(region(a, W, range(W), range(10, 15)), {}, face)
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

        def lowest_header(f):
            return max([y for y in range(16) for x in range(15) if f[y * W + x] == BASE["chc"]], default=-1)
        # yesterday's sheet falls: its header (rows 0-6) goes below row 6, for at most 1.1 s
        falling = [t for t, f in frames if lowest_header(f) > 6]
        self.assertTrue(falling, "the sheet did not fall")
        self.assertLess(falling[-1] - falling[0], 1.2)
        sheet = [tuple(f[y * W + x] for y in range(16) for x in range(16)) for t, f in frames if t > falling[-1]]
        self.assertTrue(sheet and len(set(sheet)) == 1, "the sheet did not settle")

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

        def lowest_header(f):
            return max([y for y in range(16) for x in range(15) if f[y * W + x] == BASE["chc"]], default=-1)
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


if __name__ == "__main__":
    unittest.main()
