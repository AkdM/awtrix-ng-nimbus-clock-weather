"""README screenshots at 13:37 from the simulators: installs a copy of each dist/ file whose
clock reads 13:37, captures its shots, then reinstalls the real file.
Usage: python3 tests/screens.py [tc001] [tc002]   (both when none is given)"""
import sys
import time

from simlib import ROOT, Sim

# the file name in docs/ and the settings of each shot
SHOTS = {
    "tc001": [("date", {"panels": "date"}), ("temperature", {"panels": "temp"}), ("icon", {"panels": "weather"}),
              ("night", {"panels": "date", "night": True})],
    "tc002": [("tc002-sheet", {"face": "sheet", "panels": "date"}), ("tc002-ring", {"face": "ring", "panels": "date"}),
              ("tc002-flap", {"face": "flap", "panels": "date"}), ("tc002-big", {"face": "big", "panels": "date"}),
              ("tc002-temperature", {"face": "sheet", "panels": "temp"}),
              ("tc002-icon", {"face": "sheet", "panels": "weather"}),
              ("tc002-big-weather", {"face": "big", "panels": "weather"}),
              ("tc002-night", {"face": "sheet", "panels": "date", "night": True})],
}
STILL = {"tc001": {}, "tc002": {"canim": False}}            # no tear-off in the shots
RESTORE = {"tc001": {}, "tc002": {"face": "sheet", "canim": True}}


def png(path, w, h, px, scale=14, gap=2):
    import struct
    import zlib
    W, H = w * scale, h * scale
    rows = []
    for y in range(H):
        row = bytearray([0])
        for x in range(W):
            c = px[(y // scale) * w + (x // scale)]
            grid = x % scale >= scale - gap or y % scale >= scale - gap
            row += b"\x18\x18\x18" if grid else bytes([(c >> 16) & 255, (c >> 8) & 255, c & 255])
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")
    path.write_bytes(data)


def main():
    for clock in sys.argv[1:] or list(SHOTS):
        sim = Sim(clock)
        real = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
        demo = real.replace("      var h = hour()\n      var m = minute()\n", "      var h = 13\n      var m = 37\n", 1)
        # a daytime icon next to 13:37, whatever the weather outside: partly cloudy
        demo = demo.replace("    self.ico = n\n", "    self.ico = 2\n", 1)
        assert demo.count("var h = 13") == 1 and demo.count("self.ico = 2") == 1
        try:
            sim.req("PUT", "/apps/script/Nimbus", raw=demo.encode())
            sim.only("Nimbus")
            for name, cfg in SHOTS[clock]:
                sim.config(**{**STILL[clock], "tran": "none", "tsep": "steady", "night": False, "ntopic": "", **cfg})
                time.sleep(1 if cfg["panels"] == "date" else 4)
                w, h, px = sim.screen()
                png(ROOT / "docs" / (name + ".png"), w, h, px)
                print("docs/%s.png" % name)
        finally:
            sim.req("PUT", "/apps/script/Nimbus", raw=real.encode())
            sim.config(night=False, tsep="pulse", tran="wipe", panels="date,temp,weather", **RESTORE[clock])


if __name__ == "__main__":
    main()
