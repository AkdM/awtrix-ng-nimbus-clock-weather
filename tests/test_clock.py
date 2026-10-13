import time
import unittest

from simlib import diff, mirrored, need, pair

BASE = dict(t24=True, tlz=True, tampm=False, tsep="steady", tcol=0xFFFFFF, tright=True, chc=0xFF0000,
            ctc=0x000000, cbc=0xFFFFFF, wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666, wtw=0xFFFFFF,
            wow=0x666666, panels="date", night=False, nauto=False, nbar=True)
CASES = [{}, {"t24": False}, {"t24": False, "tlz": False}, {"tlz": False}, {"wbar": False}, {"wmon": False},
         {"tcol": 0x00FF00, "chc": 0x0000FF, "ctc": 0xFF00FF, "cbc": 0xFFFF00,
          "wtd": 0xFF0000, "wod": 0x00FFFF, "wtw": 0x0000FF, "wow": 0x804000}]


def colon_x(frame, w, xs):
    """x of the colon: the column whose rows 1-5 are lit only on rows 2 and 4."""
    for x in xs:
        col = [frame[y * w + x] != 0 for y in range(1, 6)]
        if col == [False, True, False, True, False]:
            return x
    return None


class Parity(unittest.TestCase):
    def check(self, clock):
        sim = need(clock)
        sim.install()
        for case in CASES:
            cfg = dict(BASE, **case)
            sim.config(**cfg)
            a, b = pair(sim, cfg)
            self.assertEqual(diff(a, b, sim.w), [], "%s %s" % (clock, case))

    def test_tc001_matches_the_official_app(self):
        self.check("tc001")

    def test_tc002_matches_the_official_app(self):
        self.check("tc002")

    def test_clock_on_the_left_mirrors_the_layout(self):
        for clock in ("tc001", "tc002"):
            sim = need(clock)
            sim.install()
            cfg = dict(BASE, tright=False)
            sim.config(**cfg)
            a, b = pair(sim, cfg)
            self.assertEqual(diff(a, mirrored(b, sim.w, sim.h, sim.fx), sim.w), [], clock)


class Colon(unittest.TestCase):
    def colon_states(self, sim, seconds):
        frames = sim.frames(seconds)
        x = None
        for _, f in frames:
            x = x or colon_x(f, sim.w, range(sim.fx + 9, sim.fx + 32))
        self.assertIsNotNone(x, "colon not found")
        return [(t, max((f[2 * sim.w + x] >> s) & 0xFF for s in (0, 8, 16))) for t, f in frames]

    def test_steady_is_always_lit(self):
        sim = need("tc001")
        sim.install()
        sim.config(**dict(BASE, tsep="steady"))
        sim.only("Nimbus")
        self.assertTrue(all(v == 0xFF for _, v in self.colon_states(sim, 2.5)))

    def test_blink_alternates_every_second(self):
        sim = need("tc001")
        sim.install()
        sim.config(**dict(BASE, tsep="blink"))
        sim.only("Nimbus")
        states = [(t, v > 0) for t, v in self.colon_states(sim, 4.5)]
        changes = [t for (t, a), (_, b) in zip(states, states[1:]) if a != b]
        self.assertGreaterEqual(len(changes), 3)
        gaps = [b - a for a, b in zip(changes, changes[1:])]
        self.assertTrue(all(0.7 < g < 1.3 for g in gaps), gaps)

    def test_pulse_fades_in_and_out(self):
        sim = need("tc001")
        sim.install()
        sim.config(**dict(BASE, tsep="pulse"))
        sim.only("Nimbus")
        levels = [v for _, v in self.colon_states(sim, 3.0)]
        self.assertLess(min(levels), 0x30)
        self.assertGreater(max(levels), 0xE0)
        self.assertGreater(len({v for v in levels if 0x40 < v < 0xC0}), 2)


if __name__ == "__main__":
    unittest.main()
