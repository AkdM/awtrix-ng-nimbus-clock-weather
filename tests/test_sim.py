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


if __name__ == "__main__":
    unittest.main()
