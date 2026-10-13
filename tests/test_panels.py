import time
import unittest

from simlib import label, need, pub, region

BASE = dict(t24=True, tlz=True, tampm=False, tsep="steady", tcol=0xFFFFFF, tright=True, chc=0xFF0000,
            ctc=0x000000, cbc=0xFFFFFF, wbar=True, wmon=True, wtd=0xFFFFFF, wod=0x666666, wtw=0xFFFFFF,
            wow=0x666666, ddur=1, pdur=1, tran="none", night=False, nauto=False, rtopic="", htopic="",
            rcol=0xFFFFFF, hcol=0x00AAFF)


def kind(sim, f):
    """What the panel shows: 'date' (calendar header), 'blank', or 'other'."""
    if f[0 * sim.w + sim.fx] == BASE["chc"]:
        return "date"
    return "other" if region(f, sim.w, range(sim.fx, sim.fx + 11), range(0, 7)) else "blank"


def wait_for(sim, pred, seconds=15):
    t0 = time.time()
    while time.time() - t0 < seconds:
        f = sim.screen()[2]
        if pred(f):
            return f
    raise AssertionError("condition not met within %d s" % seconds)


class Panels(unittest.TestCase):
    def setUp(self):
        self.sim = need("tc001")
        self.sim.install()

    def panel_px(self, f):
        return region(f, self.sim.w, range(self.sim.fx, self.sim.fx + 11), range(0, 7))

    def is_label(self, f):
        """A temperature-like label: not the calendar, one color, not the grey placeholder."""
        colors = set(self.panel_px(f).values())
        return kind(self.sim, f) == "other" and len(colors) == 1 and 0x666666 not in colors

    def test_outdoor_temperature_stays_in_the_panel_area(self):
        self.sim.config(**dict(BASE, panels="temp"))
        f = wait_for(self.sim, self.is_label)
        xs = [x for x, _ in self.panel_px(f)]
        self.assertGreaterEqual(min(xs), 0)
        self.assertLessEqual(max(xs), 10)

    def test_weather_icon_is_8_px_wide(self):
        self.sim.config(**dict(BASE, panels="weather"))
        f = wait_for(self.sim, lambda f: self.panel_px(f) and 0x666666 not in self.panel_px(f).values())
        xs = [x for x, _ in self.panel_px(f)]
        self.assertLessEqual(max(xs) - min(xs), 7)

    def test_panels_setting_is_read_loosely(self):
        # " Date , WEATHER,foo,temp ,date": date, weather, temp, date; with 1 s each the date shows
        # twice in a row, so over 8 s the date is on screen about half the time
        self.sim.config(**dict(BASE, panels=" Date , WEATHER,foo,temp ,date"))
        kinds = [kind(self.sim, f) for _, f in self.sim.frames(8)]
        share = kinds.count("date") / len(kinds)
        self.assertTrue(0.35 < share < 0.65, share)
        self.assertNotIn("blank", kinds[len(kinds) // 4:])

    def test_device_sensor_without_reading_falls_back_to_the_date(self):
        # the simulator has no sensors: room and humidity have no data, so the date shows
        self.sim.config(**dict(BASE, panels="room,humidity"))
        kinds = [kind(self.sim, f) for _, f in self.sim.frames(3)]
        self.assertEqual(set(kinds[len(kinds) // 3:]), {"date"})


class RoomOverMqtt(unittest.TestCase):
    def setUp(self):
        self.sim = need("tc001")
        self.sim.install()
        pub("nimbus/test/room", "", retain=True)
        pub("nimbus/test/hum", "", retain=True)

    def shows(self, expected, seconds=6):
        def ok(f):
            return region(f, self.sim.w, range(0, 11), range(0, 7)) == expected
        return wait_for(self.sim, ok, seconds)

    def test_room_values_from_mqtt(self):
        self.sim.config(**dict(BASE, panels="room,humidity", rtopic="nimbus/test/room", htopic="nimbus/test/hum"))
        kinds = [kind(self.sim, f) for _, f in self.sim.frames(2)]
        self.assertEqual(set(kinds[len(kinds) // 3:]), {"date"})   # nothing received yet
        pub("nimbus/test/room", "21.5")
        self.shows(label("22", 0, 0xFFFFFF))                           # 10 px: from x 0
        pub("nimbus/test/hum", '{"humidity": 45.4}')
        self.shows(label("45%", 0, 0x00AAFF, dot=False))               # 11 px: from x 0
        pub("nimbus/test/room", "7 °C")
        self.shows(label("7", 1, 0xFFFFFF))                            # 6 px: centred in the slot
        pub("nimbus/test/room", "-5")
        self.shows(label("-5", 0, 0xFFFFFF))
        pub("nimbus/test/room", "no number")
        self.shows(label("-5", 0, 0xFFFFFF))                           # ignored

    def test_wide_value_bounces_inside_the_panel_area(self):
        self.sim.config(**dict(BASE, panels="room", rtopic="nimbus/test/room"))
        pub("nimbus/test/room", "-12")
        time.sleep(2)
        frames = [f for _, f in self.sim.frames(3)]
        self.assertTrue(all(kind(self.sim, f) != "date" for f in frames), "the room panel is not shown")
        for f in frames:
            xs = [x for (x, y) in region(f, self.sim.w, range(0, 12), range(0, 7))]
            self.assertTrue(not xs or max(xs) <= 10, max(xs) if xs else None)


if __name__ == "__main__":
    unittest.main()
