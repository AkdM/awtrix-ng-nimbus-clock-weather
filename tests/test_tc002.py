"""Nimbus on the TC002 against the TC002's own clock app (the TC002 simulator, see sim/Dockerfile)."""
import time
import unittest

from simlib import diff, need, pair, region

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


# the time and the week bar: x 16-51 next to a sheet, rows 0-9 on the big face
TIME = {"sheet": (range(16, W), range(16)), "ring": (range(16, W), range(16)), "flap": (range(16, W), range(16)),
        "big": (range(W), range(10))}


class Time(unittest.TestCase):
    def test_matches_the_official_clock_on_every_face(self):
        sim = need("tc002")
        sim.install()
        for face, cases in FACES.items():
            for case in cases:
                cfg = dict(BASE, face=face, **case)
                sim.config(**cfg)
                a, b = pair(sim, cfg)
                xs, ys = TIME[face]
                self.assertEqual(region(a, W, xs, ys), region(b, W, xs, ys), "%s %s" % (face, case))


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


if __name__ == "__main__":
    unittest.main()
