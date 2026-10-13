import time
import unittest

from simlib import need, region

BASE = dict(t24=True, tlz=True, tampm=False, tsep="steady", tcol=0xFFFFFF, tright=True, chc=0xFF0000,
            ctc=0x000000, cbc=0xFFFFFF, wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666, wtw=0xFFFFFF,
            wow=0x666666, ddur=1, pdur=1, night=False, nauto=False, rtopic="", htopic="")
TRANSITIONS = ["wipe", "fade", "morph", "down", "up", "left", "right", "none"]


def outside(sim, f):
    """Every pixel except the 11 px panel area on rows 0-7."""
    ax = sim.fx
    return [v for i, v in enumerate(f) if not (ax <= i % sim.w < ax + 11 and i // sim.w < 8)]


def area(sim, f):
    return tuple(f[y * sim.w + x] for y in range(8) for x in range(sim.fx, sim.fx + 11))


def held(states, n=8):
    """States that stay on screen for at least n captures in a row (about 200 ms): the still
    panels; a transition frame never lasts that long."""
    out, run = set(), 1
    for a, b in zip(states, states[1:]):
        run = run + 1 if a == b else 1
        if run >= n:
            out.add(a)
    return out


class Transitions(unittest.TestCase):
    def references(self, sim):
        refs = []
        for p in ("date", "temp"):
            sim.config(**dict(BASE, panels=p, tran="none"))
            t0 = time.time()
            while True:   # the temperature shows "--" in grey until the weather answer arrives
                a = area(sim, sim.screen()[2])
                if 0x666666 not in a or time.time() - t0 > 15:
                    break
            refs.append(a)
        return refs

    def check(self, clock):
        sim = need(clock)
        sim.install()
        refs = self.references(sim)
        for tr in TRANSITIONS:
            sim.config(**dict(BASE, panels="date,temp", tran=tr))
            time.sleep(3)   # the weather answer arrives after the restart
            m = time.localtime().tm_min
            frames = sim.frames(5)
            if time.localtime().tm_min != m:
                frames = sim.frames(5)
            base = outside(sim, frames[0][1])
            for _, f in frames:
                self.assertEqual(outside(sim, f), base, "%s %s: pixels outside the panel area changed" % (clock, tr))
            states = [area(sim, f) for _, f in frames]
            steady = held(states)
            self.assertTrue(steady <= set(refs), "%s %s: a still frame is neither panel" % (clock, tr))
            middle = set(states) - set(refs)
            if tr == "none":
                self.assertEqual(middle, set(), tr)
            else:
                self.assertTrue(middle, "%s %s: no transition frame seen" % (clock, tr))
            if tr == "morph":
                d, t = refs
                for s in middle:
                    self.assertTrue(all(v in (a, b) for v, a, b in zip(s, d, t)), "morph pixel from neither panel")

    def test_tc001(self):
        self.check("tc001")

    def test_tc002_keeps_rows_8_to_14_black(self):
        self.check("tc002")   # outside() covers rows 8-15; row 15 is the week bar, unchanged


if __name__ == "__main__":
    unittest.main()
