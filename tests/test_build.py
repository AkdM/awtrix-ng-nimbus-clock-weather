import subprocess
import sys
import unittest

from simlib import ROOT, need

sys.path.insert(0, str(ROOT))
import build as builder  # noqa: E402  (build.py at the repository root)

LAYOUT = {"tc001": ("32x8", 0, 7), "tc002": ("52x16", None, None)}
CLOCKS = ("tc001", "tc002")
REST = ["wbar", "wmon", "wtd", "wod", "wtw", "wow", "panels", "ddur", "pdur", "tran", "lat", "lon", "wref", "rtopic",
        "htopic", "rcol", "hcol", "night", "nauto", "nfrom", "nto", "nbar", "npause", "nbri", "ntopic"]
WEATHER = REST.index("wref") + 1   # the TC002 adds its weather words after the refresh period
KEYS = {"tc001": ["t24", "tlz", "tampm", "tsep", "tcol", "tright", "chc", "ctc", "cbc"] + REST,
        "tc002": ["t24", "tlz", "tsep", "tcol", "face", "chc", "ctc", "cbc", "canim", "dfmt"] + REST[:WEATHER]
        + ["wlang", "wtext"] + REST[WEATHER:]}


def build(*args):
    return subprocess.run([sys.executable, str(ROOT / "build.py"), *args], capture_output=True, text=True)


class Blocks(unittest.TestCase):
    SRC = "# @display 32x8\na\n# @if tc001\nb\n# @end\n  # @if tc002\n  c\n  # @end\nd\n"

    def test_each_clock_keeps_its_own_blocks_without_the_markers(self):
        self.assertEqual(builder.render(self.SRC, "tc001", {"display": "32x8"}, CLOCKS), "# @display 32x8\na\nb\nd\n")
        self.assertEqual(builder.render(self.SRC, "tc002", {"display": "52x16"}, CLOCKS), "# @display 52x16\na\n  c\nd\n")

    def test_unbalanced_or_unknown_blocks_stop_the_build(self):
        for bad in ("# @if tc001\n", "# @end\n", "# @if tc001\n# @if tc002\n# @end\n# @end\n", "# @if tc003\n# @end\n"):
            with self.assertRaises(SystemExit, msg=bad):
                builder.render("# @display 32x8\n" + bad, "tc001", {"display": "32x8"}, CLOCKS)


class Build(unittest.TestCase):
    def test_writes_one_file_per_clock(self):
        self.assertEqual(build().returncode, 0)
        for clock, (display, fx, by) in LAYOUT.items():
            text = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
            self.assertIn("# @display %s\n" % display, text)
            self.assertNotRegex(text, r"(?m)^\s*# @(if|end)\b")
            if fx is not None:
                self.assertIn("\nvar FX = %d " % fx, text)
                self.assertIn("\nvar BY = %d " % by, text)
            else:
                self.assertNotIn("var FX", text)

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
            self.assertEqual(list(defaults), KEYS[clock])
            if clock == "tc002":
                self.assertEqual((defaults["face"], defaults["canim"], defaults["dfmt"], defaults["wlang"], defaults["wtext"]),
                                 ("sheet", True, "dd.mm.yy", "English", ""))
            self.assertEqual(defaults["tsep"], "pulse")
            self.assertEqual(defaults["tran"], "wipe")
            self.assertEqual(defaults["panels"], "date,temp,weather")

    def test_mqtt_topics_say_which_broker(self):
        # Nimbus has no MQTT login of its own: it reads its topics through the clock's connection
        build()
        for clock in LAYOUT:
            sim = need(clock)
            sim.install()
            helps = {f["key"]: f.get("help", "") for f in sim.req("GET", "/apps/Nimbus/config")["fields"]}
            for key in ("rtopic", "htopic", "ntopic"):
                self.assertIn("broker set in AWTRIX's MQTT settings", helps[key], "%s %s" % (clock, key))


if __name__ == "__main__":
    unittest.main()
