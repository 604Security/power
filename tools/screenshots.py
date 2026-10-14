#!/usr/bin/env python3
"""Make README screenshots of `power`, using pretend batteries (no sudo, no real hardware needed).

Each scene builds a fake /sys/class/power_supply in a temp folder, runs ./power against it with colours on,
turns the ANSI colours into a terminal-style HTML page, and screenshots it with headless Chrome.
  python3 tools/screenshots.py      -> docs/screenshots/*.png
"""
import html, os, re, shutil, subprocess, tempfile
from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


def fake_sys(base, status, cap, watts, start, end, charger_w=None, volts=20):
    bat = os.path.join(base, "BAT0")
    os.makedirs(bat)
    for k, v in {"status": status, "capacity": cap, "power_now": int(watts * 1e6),
                 "charge_control_start_threshold": start, "charge_control_end_threshold": end}.items():
        open(os.path.join(bat, k), "w").write(f"{v}\n")
    ac = os.path.join(base, "AC")
    os.makedirs(ac)
    open(os.path.join(ac, "online"), "w").write("1\n" if charger_w else "0\n")
    if charger_w:
        u = os.path.join(base, "ucsi-source-psy-USBC000:002")
        os.makedirs(u)
        open(os.path.join(u, "online"), "w").write("1\n")
        open(os.path.join(u, "voltage_max"), "w").write(f"{volts * 1000000}\n")
        open(os.path.join(u, "current_max"), "w").write(f"{int(charger_w / volts * 1e6)}\n")


def run(base, args, cmdline):
    env = dict(os.environ, POWER_COLOR="1", POWER_SYS=base, POWER_RULE=os.path.join(base, "rule"))
    # a pretend sudo that just runs the command, so `power on/off` can be shown without a password
    fakebin = os.path.join(base, "bin")
    os.makedirs(fakebin, exist_ok=True)
    open(os.path.join(fakebin, "sudo"), "w").write('#!/bin/sh\nexec "$@"\n')
    os.chmod(os.path.join(fakebin, "sudo"), 0o755)
    env["PATH"] = fakebin + ":" + env["PATH"]
    out = subprocess.run([os.path.join(ROOT, "power")] + args, env=env, capture_output=True, text=True).stdout
    return f"\x1b[1;32m~\x1b[0m $ {cmdline}\n" + out


COLORS = {"31": "#ff6b6b", "32": "#5af78e", "33": "#f3f99d", "34": "#57c7ff"}


def ansi_to_html(text):
    out, style = [], {}
    for part in re.split(r"(\x1b\[[0-9;]*m)", text):
        m = re.match(r"\x1b\[([0-9;]*)m", part)
        if m:
            for code in (m.group(1) or "0").split(";"):
                if code == "0": style = {}
                elif code == "1": style["b"] = 1
                elif code == "2": style["dim"] = 1
                elif code in COLORS: style["c"] = COLORS[code]
            continue
        if not part: continue
        css = ""
        if "c" in style: css += f"color:{style['c']};"
        if "b" in style: css += "font-weight:700;"
        if "dim" in style: css += "opacity:.6;"
        out.append(f'<span style="{css}">{html.escape(part)}</span>' if css else html.escape(part))
    return "".join(out)


def shoot(name, text):
    lines = text.rstrip("\n").split("\n")
    width = max(len(l) for l in [re.sub(r"\x1b\[[0-9;]*m", "", x) for x in lines])
    w, h = int(width * 9.1) + 60, len(lines) * 21 + 74
    page = f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#ffffff}}
.win{{display:inline-block;margin:0;background:#282a36;border-radius:10px;overflow:hidden}}
.bar{{height:30px;background:#191a21;display:flex;align-items:center;gap:7px;padding-left:12px}}
.bar i{{width:12px;height:12px;border-radius:50%;display:inline-block}}
pre{{margin:0;padding:12px 18px;color:#f8f8f2;font:15px/21px 'DejaVu Sans Mono',monospace}}
</style><div class="win"><div class="bar"><i style="background:#ff5f56"></i><i style="background:#ffbd2e"></i>
<i style="background:#27c93f"></i></div><pre>{ansi_to_html(text)}</pre></div>"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    png = os.path.join(OUT, name + ".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w + 400},{h + 400}",
                    f"--screenshot={png}", "file://" + f.name], capture_output=True)
    os.unlink(f.name)
    # trim the white page around the terminal window
    im = Image.open(png).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    im.crop(box).save(png)
    print("  " + png)


SCENES = [  # name, battery state, command
    ("status-charging", dict(status="Charging", cap=54, watts=38.9, start=75, end=80, charger_w=65), [], "power"),
    ("status-resting", dict(status="Not charging", cap=80, watts=0.0, start=75, end=80, charger_w=65), [], "power"),
    ("status-limit-off", dict(status="Charging", cap=92, watts=12.4, start=0, end=100, charger_w=60), [], "power"),
    ("status-low-battery", dict(status="Discharging", cap=12, watts=7.2, start=75, end=80), [], "power"),
    ("power-off", dict(status="Charging", cap=78, watts=20.1, start=75, end=80, charger_w=65), ["off"], "power off"),
    ("power-on", dict(status="Charging", cap=78, watts=20.1, start=0, end=100, charger_w=65), ["on"], "power on"),
    ("help", dict(status="Charging", cap=54, watts=38.9, start=75, end=80, charger_w=65), ["-h"], "power -h"),
]

def install_scene():
    """install.sh updating an older installed copy: shows the changed lines and asks first."""
    target = tempfile.mkdtemp()
    old = open(os.path.join(ROOT, "power")).read().replace("START=75 END=80", "START=70 END=85")
    open(os.path.join(target, "power"), "w").write(old)
    env = dict(os.environ, POWER_COLOR="1", TARGET=target)
    r = subprocess.run([os.path.join(ROOT, "install.sh")], env=env, input="y\n", capture_output=True, text=True)
    out = r.stdout.replace("Install this? [y/N] ", "")
    # read -p writes its question to stderr: put it back where the person sees it, with their answer
    out = out.replace("\x1b[1;32m[+]\x1b[0m Installed", "Install this? [y/N] y\n\x1b[1;32m[+]\x1b[0m Installed")
    out = re.sub(r"/tmp/[^ \n]+/power", "~/.local/bin/power", out)
    shutil.rmtree(target)
    return "\x1b[1;32m~\x1b[0m $ ./install.sh\n" + out


os.makedirs(OUT, exist_ok=True)
shoot("install-update", install_scene())
for name, state, args, cmd in SCENES:
    base = tempfile.mkdtemp()
    fake_sys(base, **state)
    shoot(name, run(base, args, cmd))
    shutil.rmtree(base)
