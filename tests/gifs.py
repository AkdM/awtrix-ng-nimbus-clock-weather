"""README animations: one carousel cycle (date, temperature, weather, 2 s each) of each clock at
13:37, captured from the simulators and written as docs/nimbus-<clock>.gif with ffmpeg.
Usage: python3 tests/gifs.py [tc001] [tc002]   (both when none is given)"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from screens import png
from simlib import ROOT, Sim, script

FPS = 15
CYCLE = 6.0      # three panels of 2 s: the GIF loops without a jump
SETTINGS = {"tc001": {}, "tc002": {"face": "sheet", "canim": False}}
RESTORE = {"tc001": {}, "tc002": {"face": "sheet", "canim": True}}


def panel_area(clock, f):
    """The pixels of the carousel's area: x 0-10 rows 0-6 on the TC001, x 0-15 on the TC002."""
    w, xs, ys = (32, 11, 7) if clock == "tc001" else (52, 16, 16)
    return tuple(f[y * w + x] for y in range(ys) for x in range(xs))


def main():
    for clock in sys.argv[1:] or ["tc001", "tc002"]:
        sim = Sim(clock)
        real = (ROOT / "dist" / ("nimbus-%s.ax" % clock)).read_text()
        demo = script(clock, (("\nvar h = hour()\nvar m = minute()\n", "\nvar h = 13\nvar m = 37\n"),
                              ("\nself.ico = n\n", "\nself.ico = 2\n")))
        try:
            sim.req("PUT", "/apps/script/Nimbus", raw=demo.encode())
            sim.only("Nimbus")
            sim.config(**{**SETTINGS[clock], "panels": "date,temp,weather", "ddur": 2, "pdur": 2,
                          "tran": "wipe", "tsep": "pulse", "night": False, "ntopic": ""})
            time.sleep(8)    # the weather answers, the carousel runs
            frames = sim.frames(CYCLE * 2 + 1)
        finally:
            sim.req("PUT", "/apps/script/Nimbus", raw=real.encode())
            sim.config(night=False, tsep="pulse", tran="wipe", panels="date,temp,weather", ddur=10, pdur=3,
                       **RESTORE[clock])
        # start the loop on the date panel, just before it wipes to the temperature
        date = panel_area(clock, frames[0][1])
        start = next(t for t, f in frames if panel_area(clock, f) != date) - 1.0
        w, h = (32, 8) if clock == "tc001" else (52, 16)
        with tempfile.TemporaryDirectory() as tmp:
            for k in range(int(CYCLE * FPS)):
                t = start + k / FPS
                f = min(frames, key=lambda fr: abs(fr[0] - t))[1]
                png(Path(tmp) / ("%03d.png" % k), w, h, f, scale=10, gap=1)
            out = ROOT / "docs" / ("nimbus-%s.gif" % clock)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "%s/%%03d.png" % tmp,
                            "-vf", "split[a][b];[a]palettegen=stats_mode=full:reserve_transparent=0[p];"
                                   "[b][p]paletteuse=dither=none", "-loop", "0", str(out)], check=True)
        print("docs/%s (%d KB)" % (out.name, out.stat().st_size // 1024))


if __name__ == "__main__":
    main()
