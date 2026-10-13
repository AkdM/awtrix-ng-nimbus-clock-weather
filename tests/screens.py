"""README screenshots at 13:37 from the simulators: installs a copy of each dist/ file whose
clock reads 13:37, captures date, temperature, icon and night, then reinstalls the real file."""
import time

from simlib import ROOT, Sim

SHOTS = {"tc001": ["date", "temperature", "icon", "night"]}


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
    for clock, shots in SHOTS.items():
        sim = Sim(clock)
        real = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
        demo = real.replace("      var h = hour()\n      var m = minute()\n", "      var h = 13\n      var m = 37\n", 1)
        # a daytime icon next to 13:37, whatever the weather outside: partly cloudy
        demo = demo.replace("    self.ico = n\n", "    self.ico = 2\n", 1)
        assert demo.count("var h = 13") == 1 and demo.count("self.ico = 2") == 1
        try:
            sim.req("PUT", "/apps/script/Nimbus", raw=demo.encode())
            sim.only("Nimbus")
            for shot in shots:
                panels = {"date": "date", "temperature": "temp", "icon": "weather", "night": "date"}[shot]
                sim.config(panels=panels, tran="none", tsep="steady", night=shot == "night", ntopic="")
                time.sleep(4 if shot != "date" else 1)
                w, h, px = sim.screen()
                name = shot if clock == "tc001" else "tc002-" + shot
                png(ROOT / "docs" / (name + ".png"), w, h, px)
                print("docs/%s.png" % name)
        finally:
            sim.req("PUT", "/apps/script/Nimbus", raw=real.encode())
            sim.config(night=False, tsep="pulse", tran="wipe", panels="date,temp,weather")


if __name__ == "__main__":
    main()
