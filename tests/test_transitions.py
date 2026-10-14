import time
import unittest

from simlib import need, region

BASE = dict(t24=True, tlz=True, tampm=False, tsep="steady", tcol=0xFFFFFF, tright=True, chc=0xFF0000,
            ctc=0x000000, cbc=0xFFFFFF, wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666, wtw=0xFFFFFF,
            wow=0x666666, ddur=1, pdur=1, night=False, nauto=False, rtopic="", htopic="")
BASE_HEADER = 0xFF0000
TRANSITIONS = ["wipe", "fade", "morph", "down", "up", "left", "right", "none"]


def outside(sim, f):
    """Every pixel except the 11 px panel area on rows 0-7."""
    ax = sim.fx
    return [v for i, v in enumerate(f) if not (ax <= i % sim.w < ax + 11 and i // sim.w < 8)]


def area(sim, f):
    return tuple(f[y * sim.w + x] for y in range(8) for x in range(sim.fx, sim.fx + 11))


def label_colors(a):
    """Colors lit in the panel area's rows 0-6 (row 7 holds a week-bar segment on the TC001)."""
    return {v for i, v in enumerate(a) if v and i < 7 * 11}


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
    def wait_for_weather(self, sim):
        """Each restart fetches the weather; until it answers the temperature is a grey "--"."""
        t0 = time.time()
        while time.time() - t0 < 15:
            colors = label_colors(area(sim, sim.screen()[2]))
            if colors and 0x666666 not in colors and BASE_HEADER not in colors:
                return
        raise AssertionError("no weather answer within 15 s")

    def check(self, clock):
        sim = need(clock)
        sim.install()
        sim.config(**dict(BASE, panels="date", tran="none"))
        date = area(sim, sim.screen()[2])
        for tr in TRANSITIONS:
            sim.config(**dict(BASE, panels="date,temp", tran=tr))
            self.wait_for_weather(sim)
            m = time.localtime().tm_min
            frames = sim.frames(5)
            if time.localtime().tm_min != m:
                frames = sim.frames(5)
            base = outside(sim, frames[0][1])
            for _, f in frames:
                self.assertEqual(outside(sim, f), base, "%s %s: pixels outside the panel area changed" % (clock, tr))
            states = [area(sim, f) for _, f in frames]
            still = held(states)
            # the still frames: the date, and the temperature label (one color) taken from this run,
            # since the weather can change between runs
            labels = still - {date}
            self.assertEqual(len(labels), 1, "%s %s: still frames other than the date: %d" % (clock, tr, len(labels)))
            temp = labels.pop()
            self.assertEqual(len(label_colors(temp)), 1, "%s %s: the still label has several colors" % (clock, tr))
            middle = set(states) - {date, temp}
            if tr == "none":
                self.assertEqual(middle, set(), tr)
            else:
                self.assertTrue(middle, "%s %s: no transition frame seen" % (clock, tr))
            if tr == "morph":
                for s in middle:
                    self.assertTrue(all(v in (a, b) for v, a, b in zip(s, date, temp)), "morph pixel from neither panel")

    def test_tc001(self):
        self.check("tc001")


if __name__ == "__main__":
    unittest.main()
