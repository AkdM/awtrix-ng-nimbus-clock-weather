import time
import unittest

from simlib import FONT, diff, need, pair, pub, region

BASE = dict(t24=True, tlz=True, tampm=False, tsep="steady", tcol=0xFFFFFF, tright=True, chc=0xFF0000,
            ctc=0x000000, cbc=0xFFFFFF, wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666, wtw=0xFFFFFF,
            wow=0x666666, panels="date", ddur=10, pdur=3, tran="wipe", night=False, nauto=False,
            nfrom=22, nto=7, nbar=True, npause=False, nbri=0, ntopic="", rtopic="", htopic="")
CASES = [{}, {"t24": False, "tampm": True}, {"t24": False, "tampm": False}, {"nbar": False}]


def red(f):
    lit = [v for v in f if v]
    return bool(lit) and all(v & 0xFFFF == 0 for v in lit)


class Layout(unittest.TestCase):
    def test_matches_the_official_plain_mode_in_red(self):
        sim = need("tc001")
        sim.install()
        for case in CASES:
            cfg = dict(BASE, night=True, **case)
            sim.config(**cfg)
            a, b = pair(sim, cfg, mode=0, red=True)
            self.assertEqual(diff(a, b, sim.w), [], str(case))


def bold(t):
    """{(x, y): red} of the big night time: the small font's digits at double width with their
    three bars doubled (glyph rows 0-4 on rows 0-1, 2, 3-4, 5, 6-7), 1 px apart, centred; the colon
    is two 2x1 dots on rows 2 and 5."""
    px, x = {}, (37 - 7 * len(t)) // 2
    for c in t:
        if c == ":":
            px.update({(x + dx, y): 0xFF0000 for dx in (0, 1) for y in (2, 5)})
            x += 3
            continue
        for gy, row in enumerate(FONT[c]):
            for gx, v in enumerate(row):
                if v == "#":
                    y0, h = (3 * gy + 1) // 2, 2 - gy % 2
                    px.update({(x + 2 * gx + dx, y0 + dy): 0xFF0000 for dx in (0, 1) for dy in range(h)})
        x += 7
    return px


class BigTime(unittest.TestCase):
    def test_fills_the_display_without_the_week_bar(self):
        sim = need("tc001")
        sim.install()
        for case in ({}, {"t24": False, "tlz": False}):
            cfg = dict(BASE, night=True, nbig=True, **case)
            sim.config(**cfg)
            for _ in range(3):
                now = time.localtime()
                f = sim.nimbus()
                if time.localtime().tm_min == now.tm_min:
                    break
            h = now.tm_hour if cfg["t24"] else (now.tm_hour % 12 or 12)
            t = ("%02d" if cfg["tlz"] else "%d") % h + ":%02d" % now.tm_min
            self.assertEqual(region(f, 32, range(32), range(8)), bold(t), "%s %s" % (case, t))


class Switching(unittest.TestCase):
    def setUp(self):
        self.sim = need("tc001")
        self.sim.install()
        pub("nimbus/test/night", "", retain=True)

    def is_night(self):
        return all(red(f) for _, f in self.sim.frames(1.5))

    def test_automatic_window(self):
        h = time.localtime().tm_hour
        self.sim.config(**dict(BASE, nauto=True, nfrom=h, nto=(h + 1) % 24))
        self.assertTrue(self.is_night())
        self.sim.config(**dict(BASE, nauto=True, nfrom=(h + 2) % 24, nto=(h + 3) % 24))
        self.assertFalse(self.is_night())

    def test_mqtt_and_the_retained_replay(self):
        self.sim.config(**dict(BASE, ntopic="nimbus/test/night"))
        pub("nimbus/test/night", "ON")
        time.sleep(2)
        self.assertTrue(self.is_night())
        pub("nimbus/test/night", "off", retain=True)
        time.sleep(2)
        self.assertFalse(self.is_night())
        # the setting changed after the retained "off": it wins over the replay at restart
        self.sim.config(**dict(BASE, ntopic="nimbus/test/night", night=True))
        self.assertTrue(self.is_night())
        self.sim.config(**dict(BASE, ntopic="nimbus/test/night", night=False))
        self.assertFalse(self.is_night())

    def test_switching_on_during_a_transition_leaves_no_panel_pixels(self):
        self.sim.config(**dict(BASE, panels="date,temp", ddur=1, pdur=1, ntopic="nimbus/test/night"))
        time.sleep(1.7)
        pub("nimbus/test/night", "on")
        frames = self.sim.frames(3)
        self.assertTrue(all(red(f) for t, f in frames if t > 1.2))

    def test_brightness_is_set_and_restored(self):
        self.sim.settings(autoBrightness=True, brightness=120)
        self.sim.config(**dict(BASE, nbri=20, ntopic="nimbus/test/night"))
        pub("nimbus/test/night", "on")
        time.sleep(2.5)
        s = self.sim.req("GET", "/settings")
        self.assertEqual((s["autoBrightness"], s["brightness"]), (False, 20))
        pub("nimbus/test/night", "off")
        time.sleep(2.5)
        s = self.sim.req("GET", "/settings")
        self.assertEqual((s["autoBrightness"], s["brightness"]), (True, 120))

    def test_auto_brightness_is_set_and_restored(self):
        self.sim.settings(autoBrightness=False, brightness=120)
        self.sim.config(**dict(BASE, nbri=20, nabri=True, ntopic="nimbus/test/night"))
        pub("nimbus/test/night", "on")
        time.sleep(2.5)
        s = self.sim.req("GET", "/settings")
        self.assertEqual((s["autoBrightness"], s["brightness"]), (True, 120))   # the light sensor decides
        pub("nimbus/test/night", "off")
        time.sleep(2.5)
        s = self.sim.req("GET", "/settings")
        self.assertEqual((s["autoBrightness"], s["brightness"]), (False, 120))

    def test_rotation_pause(self):
        sim = self.sim
        # the official Time app must not look like Nimbus at night: white time, calendar mode
        sim.settings(appDurationMs=3000, timeMode=1, timeColor="#FFFFFF")
        try:
            sim.config(**dict(BASE, npause=True, ntopic="nimbus/test/night"))
            sim.req("PUT", "/apps/order", {"order": ["Nimbus", "Time"], "disabled": ["Date"]})
            pub("nimbus/test/night", "on")
            time.sleep(2)
            self.assertTrue(all(red(f) for _, f in sim.frames(8)))       # Nimbus stays on screen
            pub("nimbus/test/night", "off")
            time.sleep(2)
            seen = {red(f) for _, f in sim.frames(8)}
            self.assertEqual(seen, {False})                               # day again, rotating
        finally:
            sim.settings(appDurationMs=5000)
            sim.only("Nimbus")


    def test_rotation_pause_ends_when_night_is_switched_off_in_the_settings(self):
        # saving the settings restarts the app; the pause it set at night must not outlive the night
        sim = self.sim
        sim.settings(appDurationMs=3000, timeMode=1, timeColor="#FFFFFF")
        try:
            sim.config(**dict(BASE, panels="temp", npause=True, night=True))
            sim.req("PUT", "/apps/order", {"order": ["Nimbus", "Time"], "disabled": ["Date"]})
            time.sleep(2)
            self.assertTrue(all(red(f) for _, f in sim.frames(8)))       # night, Nimbus stays on screen
            sim.config(**dict(BASE, panels="temp", npause=True, night=False))
            # the official Time app (calendar header at the frame's top-left) must come round again
            frames = sim.frames(12)
            self.assertTrue(any(f[sim.fx] == 0xFF0000 for _, f in frames), "rotation still paused")
        finally:
            sim.settings(appDurationMs=5000)
            sim.only("Nimbus")

if __name__ == "__main__":
    unittest.main()
