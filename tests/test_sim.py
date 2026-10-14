import unittest

from simlib import need


class Simulators(unittest.TestCase):
    def test_both_run_firmware_122_at_their_size(self):
        for clock, size in (("tc001", (32, 8)), ("tc002", (52, 16))):
            sim = need(clock)
            self.assertEqual(sim.req("GET", "/version")["version"], "1.2.2")
            self.assertEqual(sim.screen()[:2], size)

    def test_both_use_the_test_broker(self):
        for clock in ("tc001", "tc002"):
            system = need(clock).req("GET", "/system")
            self.assertTrue(system["mqttEnabled"])
            self.assertEqual(system["mqttHost"], "awtrix-mqtt")

    def test_tc002_runs_the_tc002_clock(self):
        # sim/Dockerfile: the TC002 simulator runs the TC002's own clock app; its sheet face puts a
        # 15 px calendar sheet at x 0, header on rows 0-6, paper below
        sim = need("tc002")
        sim.settings(clockFace="sheet", calendarAnimation=False, calendarHeaderColor="#FF0000",
                     calendarBodyColor="#FFFFFF")
        sim.only("Time")
        f = sim.screen()[2]
        self.assertEqual((f[0], f[14], f[15 * 52]), (0xFF0000, 0xFF0000, 0xFFFFFF))


if __name__ == "__main__":
    unittest.main()
