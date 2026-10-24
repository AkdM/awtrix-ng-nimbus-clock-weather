import subprocess
import sys
import unittest

from simlib import ROOT, need

sys.path.insert(0, str(ROOT))
import build as builder  # noqa: E402  (build.py at the repository root)

LAYOUT = {"tc001": ("32x8", 0, 7), "tc002": ("52x16", None, None)}
LAYOUTS = {"tc001": {"display": "32x8", "fx": 0, "by": 7}, "tc002": {"display": "52x16"}}
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
        plain = dict(minified=False)
        self.assertEqual(builder.render(self.SRC, "tc001", {"display": "32x8"}, CLOCKS, **plain), "# @display 32x8\na\nb\nd\n")
        self.assertEqual(builder.render(self.SRC, "tc002", {"display": "52x16"}, CLOCKS, **plain), "# @display 52x16\na\nc\nd\n")

    def test_unbalanced_or_unknown_blocks_stop_the_build(self):
        for bad in ("# @if tc001\n", "# @end\n", "# @if tc001\n# @if tc002\n# @end\n# @end\n", "# @if tc003\n# @end\n"):
            with self.assertRaises(SystemExit, msg=bad):
                builder.render("# @display 32x8\n" + bad, "tc001", {"display": "32x8"}, CLOCKS)


class Strip(unittest.TestCase):
    def test_comments_blank_lines_and_indentation_go_strings_stay(self):
        src = ('# @name X\n# @config c color "C" default=#FFFFFF group="G"\n\n# a comment\n'
               'var a = "#1"  # trailing\n  var b = \'x#y\' # trailing\n    # indented comment\n\n'
               'var d = "a\\"#b" # c\nvar e = 1\n')
        self.assertEqual(builder.strip(src), '# @name X\n# @config c color "C" default=#FFFFFF group="G"\n'
                                             'var a = "#1"\nvar b = \'x#y\'\nvar d = "a\\"#b"\nvar e = 1\n')

    def test_block_comments_stop_the_build(self):
        with self.assertRaises(SystemExit):
            builder.strip("var a = 1 #- a block -#\n")


class Minify(unittest.TestCase):
    PLAIN = """# @name X
# @config k text "K" default="a b # c"
import string
var G = 1
class App
var long_member, other
def init()
self.long_member = store.get("k")
self.other = [1, 2]
end
def helper(value, count)
var total = value + count * G
for item : self.other total += item end
return total
end
def draw()
var label = str(self.helper(1, 2))
mqtt.subscribe("t", / topic, payload -> self.helper(size(payload), 0))
text(0, 6, label + "# x", 0xFFFFFF)
end
end
return App()
"""

    def test_short_names_and_no_optional_spaces(self):
        # members and methods by use (other, helper, long_member), then each function's locals the
        # same way; the hooks, the built-in calls, globals, the class and every string stay
        self.assertEqual(builder.minify(self.PLAIN, width=1000),
                         '# @name X\n# @config k text "K" default="a b # c"\n'
                         'import string var G=1 class App var c,a def init()self.c=store.get("k")self.a=[1,2]end '
                         'def b(b,c)var a=b+c*G for d:self.a a+=d end return a end '
                         'def draw()var a=str(self.b(1,2))mqtt.subscribe("t",/c,b->self.b(size(b),0))'
                         'text(0,6,a+"# x",0xFFFFFF)end end return App()\n')

    def test_lines_stay_short(self):
        out = builder.minify(self.PLAIN, width=40)
        self.assertTrue(all(len(l) <= 43 for l in out.split("\n") if not l.startswith("# @")), out)

        def tokens(text):
            code = "\n".join(l for l in text.split("\n") if not l.startswith("# @"))
            return [t for t in builder.TOKEN.findall(code) if not t.isspace()]
        self.assertEqual(tokens(out), tokens(builder.minify(self.PLAIN, width=1000)))

    def test_a_call_keeps_its_parenthesis_on_the_same_line(self):
        # Berry calls f(x) only without whitespace before "(": a line break there would end the
        # expression; a space the source put there is kept, it separates two expressions
        for width in range(10, 80):
            out = builder.minify(self.PLAIN, width=width)
            self.assertFalse([l for l in out.split("\n") if l.startswith("(")], width)
        self.assertEqual(builder.minify("var a = b (c)\n", width=80), "var a=b (c)\n")
        self.assertEqual(builder.minify("var a = (c)\n", width=80), "var a=(c)\n")

    def test_a_number_keeps_a_space_before_a_dot(self):
        # Berry reads 0..E-1 as the start of a real number (0. with an exponent): a range that
        # starts with a number keeps its space
        self.assertEqual(builder.minify("var a = s[0 .. E - 1]\n", width=80), "var a=s[0 ..E-1]\n")
        self.assertEqual(builder.minify("var a = s[b .. 3]\n", width=80), "var a=s[b..3]\n")

    def test_a_local_that_hides_a_built_in_call_stops_the_build(self):
        with self.assertRaises(SystemExit):
            builder.minify("class A\ndef draw()\nvar text = 1\nend\nend\nreturn A()\n")


class Build(unittest.TestCase):
    def test_writes_one_file_per_clock(self):
        self.assertEqual(build().returncode, 0)
        for clock, (display, fx, by) in LAYOUT.items():
            text = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
            self.assertIn("# @display %s\n" % display, text)
            self.assertNotRegex(text, r"(?m)^\s*# @(if|end)\b")
            # no blank lines, no indentation, no comments: only the header's "# @" lines start with "#"
            for line in text.split("\n")[:-1]:
                self.assertTrue(line.strip(), "blank line in %s" % clock)
                self.assertEqual(line, line.lstrip(), "indented line in %s" % clock)
                self.assertFalse(line.lstrip().startswith("#") and not line.startswith("# @"), line)
            if fx is not None:
                self.assertIn("var FX=%d " % fx, text)
                self.assertIn("var BY=%d " % by, text)
            else:
                self.assertNotIn("var FX", text)
            # minified: shorter than the readable build, short lines, hooks and setting keys kept
            plain = builder.render((ROOT / "src" / "nimbus.ax").read_text(), clock, LAYOUTS[clock], CLOCKS, minified=False)
            self.assertLess(len(text), 0.9 * len(plain))
            # lines of about 200 characters (a call's "(" stays with its name, a few over at most)
            self.assertTrue(all(len(l) <= 205 for l in text.split("\n") if not l.startswith("# @")), clock)
            for hook in ("def init()", "def loop()", "def draw()"):
                self.assertIn(hook, text)
            self.assertIn('store.get("t24")', text)
            self.assertNotIn("self.t24", text)

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
