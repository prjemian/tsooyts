# SPAAC Page Display — Troubleshooting Guide

---

## IR Receiver: No Signals Reaching the Application

This is the most common issue.  The hardware may be working correctly while the
software stack fails silently.

### Step 1 — Verify the hardware receives signals

```bash
sudo ir-ctl --receive
```

Point the remote at the receiver and press a button.  You should see lines of
`+NNN -NNN` timing values.  If you see nothing, the hardware is not working
(check wiring, GPIO pin, and power).  If you see timing data, the hardware is
working and the problem is in the software layer.

### Step 2 — Check the evdev device exists

```bash
python3 -m evdev.evtest
```

A device named `gpio_ir_recv` should appear (typically `/dev/input/event0`).
If it does not appear, the `gpio-ir` overlay is not loaded.  Check
`/boot/firmware/config.txt` for:

```ini
dtoverlay=gpio-ir,gpio_pin=17
```

Then reboot.

### Step 3 — Check that evdev reports raw events

```python
# run as: python3 ir_test.py
from evdev import InputDevice, ecodes

device = InputDevice('/dev/input/event0')
print("Listening for events (press Ctrl-C to stop)...")
for event in device.read_loop():
    print(event)
    if event.type == ecodes.EV_MSC:
        print(f"  --> Raw IR scancode: code={event.code}, value={event.value}")
```

Press remote buttons.  If you see `EV_MSC` events the stack is working and
you need only teach the app your remote buttons (see User Guide).  If you
see **no events at all**, continue to Step 4.

### Step 4 — Check active IR protocol decoders

```bash
cat /sys/class/rc/rc0/protocols
```

On a freshly booted system only `[lirc]` may be in brackets — this is normal
on kernel 6.12.  Enable all decoders with `ir-keytable`:

**Enable all decoders (session, does not survive reboot):**

```bash
sudo ir-keytable -s rc0 -p all
cat /sys/class/rc/rc0/protocols
```

All protocols should now appear in brackets.

> **Note:** Writing directly to `/sys/class/rc/rc0/protocols` does not work on
> kernel 6.12 even with decoder modules loaded.  Use `ir-keytable` instead.

**Load decoder modules and activate permanently:**

```bash
sudo modprobe ir_nec_decoder
sudo modprobe ir_rc5_decoder
sudo modprobe ir_sony_decoder
sudo modprobe ir_jvc_decoder
```

Then add these to `/etc/modules-load.d/ir-decoders.conf` and enable the
`ir-protocols` systemd service to activate them at boot (see
[Installation Guide](installation_guide.md#enable-all-ir-protocol-decoders)).

After loading, re-run the evdev test in Step 3.

### Step 5 — Inspect kernel messages

```bash
sudo dmesg | grep -i 'rc\|ir_\|gpio_ir'
```

Look for:

| Message | Meaning |
|---------|---------|
| `IR NEC protocol handler initialized` | Decoder module loaded OK |
| `gpio-ir-recv-irq` in `/proc/interrupts` | Hardware receiving interrupts |
| `rc rc0: two consecutive events of type space` | Hardware timing issue — see below |

Check whether interrupts are being received:

```bash
cat /proc/interrupts | grep ir
```

The counter next to `gpio-ir-recv-irq` should increase each time you press a
remote button.  If it does not, the hardware connection or GPIO configuration
is wrong.

### "two consecutive events of type space" Error

This kernel warning means the IR decoder received an unexpected pulse sequence.
Possible causes:

- **Remote protocol mismatch** — try enabling all decoders (Step 4).
- **Electrical noise** — use a shorter jumper cable; add a 100 Ω resistor in
  series on the OUT line; ensure solid GND connection.
- **GPIO pin conflict** — confirm no other overlay is using GPIO 17.
- **Wrong inversion setting** — some receivers output active-low; try adding
  `invert=1` to the overlay:

  ```ini
  dtoverlay=gpio-ir,gpio_pin=17,invert=1
  ```

---

## IR Receiver: Raw Signals Visible But App Does Not Respond

The hardware works and evdev delivers events, but button presses have no effect
in the app.

**Possible causes:**

1. **Buttons not taught** — Open Settings → Teach Buttons and map remote buttons
   to functions.  See [User Guide — Teach Mode](user_guide.md#teach-mode).

2. **Wrong device** — The app looks for a device named exactly `gpio_ir_recv`.
   Verify:

   ```bash
   python3 -m evdev.evtest
   ```

   The device name in the list must be `gpio_ir_recv`.

3. **Permissions** — The app needs read access to `/dev/input/event*`.
   On Raspberry Pi OS the `pi` user is in the `input` group by default.
   Verify:

   ```bash
   groups pi | grep input
   ```

   If `input` is missing:

   ```bash
   sudo usermod -aG input pi
   ```

   Log out and back in for the change to take effect.

4. **Repeat controller filtering** — If you press the same button very rapidly,
   the repeat controller may suppress some events.  This is normal behavior;
   hold the button to activate repeat for page navigation.

---

## Service Does Not Start

```bash
sudo systemctl status spaac.service
sudo journalctl -u spaac.service -n 50
```

Common causes and fixes:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `no display name` or `cannot connect to X` | X session not ready yet | Increase the `ExecStartPre=/bin/sleep` value in the service file (default 5 s) |
| `ModuleNotFoundError: No module named 'PyQt5'` | PyQt5 not installed | `sudo apt install python3-pyqt5` |
| `ModuleNotFoundError: No module named 'evdev'` | evdev not installed | `sudo apt install python3-evdev` |
| `Permission denied: '/dev/input/event0'` | User not in `input` group | `sudo usermod -aG input pi` then reboot |
| Service starts then immediately restarts | Application crash at startup | Check journal for Python traceback |

To test the service command manually (as the pi user, with a display):

```bash
DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority python3 /home/pi/Documents/show_page/spaac_display.py
```

---

## Display Issues

### Screen is rotated or upside down

Add or adjust `display_rotate` in `/boot/firmware/config.txt`:

```ini
display_rotate=0   # normal
display_rotate=1   # 90 degrees clockwise
display_rotate=2   # 180 degrees (upside down)
display_rotate=3   # 270 degrees clockwise
```

Reboot after changing.

### Touchscreen touch coordinates are inverted

After rotating the display, the touch coordinates may not match the displayed
content.  See the touchscreen rotation section in the
[Installation Guide](installation_guide.md#configure-the-7-touchscreen).

### Display is blank / black on boot

- Confirm the DSI ribbon cable is fully seated on both ends.
- Check the USB power cable from the Pi to the display (needed for backlight on
  the official 7" screen).
- Try a different power supply — insufficient current causes display issues.

---

## Application Behavior Issues

### Page number jumps to 1 after reboot

The current page number is held in memory and is not saved across reboots.  This
is by design — the operator sets the page number at the start of each service.

### Settings are lost after reboot

Check that `~/.spaac/config.json` and `~/.spaac/keymap.json` are present and
writable:

```bash
ls -la ~/.spaac/
cat ~/.spaac/keymap.json
```

If the files are missing, run the app once manually and open Settings > Save to
create them.

### The gear (⚙) button is hard to tap

The settings button is intentionally small to avoid accidental taps during
normal use.  If accessibility is a concern you can tap the exact lower-right
corner of the touchscreen — the button is 50 × 50 pixels.

### Dial entry times out immediately

The dial entry auto-cancels after 8 seconds of inactivity.  If it is cancelling
too quickly, check that the remote's digit buttons are taught correctly in Teach
Mode.

### Page number text is cut off or too large

The application scales fonts based on screen height.  If the Pi is connected to
an unexpected display (e.g., during setup via HDMI), the font sizes will differ
from the 7" screen.  This corrects itself when the 7" touchscreen is the active
display.

---

## Diagnostic Commands Summary

```bash
# Check IR receiver hardware
sudo ir-ctl --receive

# List evdev input devices
python3 -m evdev.evtest

# Check active IR protocol decoders
cat /sys/class/rc/rc0/protocols

# Enable all IR decoders (session only)
sudo ir-keytable -s rc0 -p all

# Load NEC decoder module
sudo modprobe ir_nec_decoder

# Check interrupt counter
cat /proc/interrupts | grep ir

# Kernel messages about IR
sudo dmesg | grep -i 'rc\|ir_\|gpio_ir'

# Service status
sudo systemctl status spaac.service

# Service logs
sudo journalctl -u spaac.service -n 50 --no-pager

# Check user groups
groups pi
```
