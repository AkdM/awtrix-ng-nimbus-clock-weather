import subprocess
import sys
import unittest

from simlib import ROOT, need

LAYOUT = {"tc001": ("32x8", 0, 7), "tc002": ("52x16", 10, 15)}
KEYS = ["t24", "tlz", "tampm", "tsep", "tcol", "tright", "chc", "ctc", "cbc", "wbar", "wmon", "wtd", "wod",
        "wtw", "wow", "panels", "ddur", "pdur", "tran", "lat", "lon", "wref", "rtopic", "htopic", "rcol",
        "hcol", "night", "nauto", "nfrom", "nto", "nbar", "npause", "nbri", "ntopic"]


def build(*args):
    return subprocess.run([sys.executable, str(ROOT / "build.py"), *args], capture_output=True, text=True)


class Build(unittest.TestCase):
    def test_writes_one_file_per_clock(self):
        self.assertEqual(build().returncode, 0)
        for clock, (display, fx, by) in LAYOUT.items():
            text = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
            self.assertIn("# @display %s\n" % display, text)
            self.assertIn("\nvar FX = %d " % fx, text)
            self.assertIn("\nvar BY = %d " % by, text)

    def test_check_detects_a_stale_file(self):
        self.assertEqual(build().returncode, 0)
        self.assertEqual(build("--check").returncode, 0)
        path = ROOT / "dist" / "nimbus-tc002.ax"
        path.write_text(path.read_text() + "\n")
        self.assertEqual(build("--check").returncode, 1)
        self.assertEqual(build().returncode, 0)


class Install(unittest.TestCase):
    def test_installs_with_every_setting(self):
        build()
        for clock in LAYOUT:
            sim = need(clock)
            sim.install()
            self.assertIsNone(sim.error())
            defaults = sim.config_defaults()
            self.assertEqual(list(defaults), KEYS)
            self.assertEqual(defaults["tsep"], "pulse")
            self.assertEqual(defaults["tran"], "wipe")
            self.assertEqual(defaults["panels"], "date,temp,weather")


if __name__ == "__main__":
    unittest.main()
