# SPAAC Page Display — Installation Guide

This guide covers assembling the hardware, flashing the Raspberry Pi, configuring
the operating system, and deploying the application so it starts automatically on
boot.

---

## Parts List

| Qty | Item | Notes |
|-----|------|-------|
| 1 | Raspberry Pi 3B, 3B+, or 4 | Tested on Pi 3 model B+; first developed on a 2 model B (not recommended) |
| 1 | 7" Official Raspberry Pi Touchscreen Display | DSI ribbon cable included |
| 1 | Raspberry Pi Display Case (optional) | Any case that exposes the touchscreen |
| 1 | IR receiver module | TSOP38238 or VS1838B (3-pin: VCC, GND, OUT); or a pre-wired module on a breakout board |
| 1 | TV remote control | Any standard IR remote |
| 3 | Female–to–female jumper wires (≥ 15 cm) | To connect the IR receiver to GPIO |
| 1 | Small project box | To house and protect the IR receiver module |
| 1 | microSD card (16 GB or larger) | Class 10 / A1 or better |
| 1 | USB-C (Pi 4) or micro-USB (Pi 3) power supply | 3 A recommended |
| 1 | Short USB cable or GPIO power for the touchscreen | Supplied with official screen kit |

Optional but recommended:

- Clear acrylic or IR-transparent window material for the project box
- Hot glue or double-sided foam tape for mounting the sensor
- Strain-relief grommet for the cable exit on the project box

---

## Assemble the Hardware

### 1. Attach the Touchscreen

Follow the official Raspberry Pi touchscreen assembly guide:

1. Connect the DSI ribbon cable from the display to the Raspberry Pi's DSI port.
2. Power the display via the USB cable from the Pi (official screen) or via the
   GPIO 5 V and GND pins.
3. Fit the Pi and screen into the display case if using one.

### 2. Wire the IR Receiver

The IR receiver has three pins.  The IR sensor is on the round face.  With the
round face of the IR receiver facing you, the standard VS1838B / TSOP38238
pinout (left to right) is:

```
[OUT] [GND] [VCC]
```

> Check your module's datasheet — [pin order](https://pinout.xyz) varies between manufacturers.

Connect the pins to the Raspberry Pi GPIO header:

| IR receiver pin | Raspberry Pi pin |
|-----------------|-----------------|
| VCC | 3.3 V (pin 1) |
| GND | Ground (pin 6) |
| OUT | GPIO 17 (pin 11) |

GPIO 17 matches the device-tree overlay configured later.  Do **not** use 5 V
for VCC; the 3.3 V rail is sufficient and avoids risking the GPIO input.

### 3. Package the IR Receiver

The IR receiver module is fragile and its lens must have a clear view of the
congregation.

1. Drill or cut a 5 mm hole (or a rectangular slot) in the front face of the
   project box aligned to the sensor lens.
2. Optionally glue a piece of clear acrylic or IR-transparent plastic over the
   opening to protect the sensor while still passing IR signals.
3. Hot-glue or mount the sensor inside the box so the lens aligns with the
   opening.
4. Route the three jumper wires out through a small hole in the side or back of
   the box.  Add a strain-relief grommet or a cable tie to prevent the wires
   from pulling on the sensor.
5. Run the wires to the Pi GPIO header and connect as above.
6. Position the project box so the sensor faces the congregation area (a slight
   downward angle can help capture signals from pew height).

---

## Flash the microSD Card

### Download Raspberry Pi Imager

Install the official Raspberry Pi Imager on your desktop/laptop:
<https://www.raspberrypi.com/software/>

### Choose an OS Image

1. Open Raspberry Pi Imager.
2. Click **Choose OS**.
3. Select **Raspberry Pi OS (64-bit)** — the full *Desktop* variant, not Lite.
   - 64-bit is preferred for best performance on Pi 3 and Pi 4.
   - The Desktop environment is required for the PyQt5 graphical application.

### Configure the Image (before writing)

Click the **gear icon** (Advanced options) in Raspberry Pi Imager and set:

- **Hostname:** e.g., `page` or `spaac`
- **Enable SSH:** yes (password authentication)
- **Username:** `pi`  (or your preferred name — adjust file paths below accordingly)
- **Password:** set a strong password
- **Locale / timezone:** set to your region
- **Wi-Fi:** not needed for normal operation, but useful during setup if an
  Ethernet cable is unavailable

### Write the Image

1. Insert the microSD card into your computer.
2. Click **Choose Storage** and select the card.
3. Click **Write** and confirm.  This erases the card.
4. When complete, remove the card and insert it into the Raspberry Pi.

---

## First Boot and OS Configuration

Power on the Pi.  On first boot the desktop will appear.  Connect a keyboard and
mouse (USB) for initial configuration, or use SSH.

### Update the System


```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### Configure the 7" Touchscreen

The official Raspberry Pi 7" touchscreen is plug-and-play on current Raspberry Pi
OS via DSI.  If the image appears rotated or the touch is inverted:

**Rotate display (if needed):**

Edit `/boot/firmware/config.txt` and add:

```ini
display_rotate=2   # 180 degrees; use 1 for 90°, 3 for 270°
```

**Touchscreen rotation (if touch is inverted after display rotation):**

```bash
sudo nano /usr/share/X11/xorg.conf.d/40-libinput.conf
```

Find the `InputClass` section for the touchscreen and add:

```
Option "TransformationMatrix" "0 -1 1 1 0 0 0 0 1"
```

(Adjust the matrix for your specific rotation.)

---

## Configure the IR Receiver

### Enable the gpio-ir Kernel Overlay

Edit the Pi boot configuration:

```bash
sudo nano /boot/firmware/config.txt
```

> On older Raspberry Pi OS versions the file is `/boot/config.txt`.

Add the following line (or confirm it is already present):

```ini
dtoverlay=gpio-ir,gpio_pin=17
```

Save and reboot.  After reboot, verify the IR device appears:

```bash
cat /proc/bus/input/devices
```

Look for a block containing `Name="gpio_ir_recv"`.  The `Handlers=` line in
that block shows the assigned event node, for example `event0`.  The exact
number may vary between boots or Pi models.

### Install IR Diagnostic Tools

```bash
sudo apt install -y ir-keytable v4l-utils
```

These provide `ir-keytable` and `ir-ctl` for testing and diagnosing the IR
receiver (see [Troubleshooting](troubleshooting.md)).

### Enable All IR Protocol Decoders

The application reads raw scancodes directly from evdev and does not require a
specific IR protocol keymap.  However, all protocol decoder modules must be
loaded so the kernel can translate raw signals into scancode events.

Check which decoders are currently active:

```bash
cat /sys/class/rc/rc0/protocols
```

On a correctly configured system all protocols are shown in brackets `[…]`.
If some are missing, enable them using `ir-keytable`:

```bash
sudo ir-keytable -s rc0 -p all
```

Verify:

```bash
cat /sys/class/rc/rc0/protocols
```

> **Note:** On kernel 6.12, writing directly to the `protocols` sysfs file does
> not activate decoders even with modules loaded.  Use `ir-keytable` instead.

To make this persistent across reboots, load the kernel decoder modules at boot.
Create a modules-load configuration file:

```bash
sudo nano /etc/modules-load.d/ir-decoders.conf
```

Add:

```
ir_nec_decoder
ir_rc5_decoder
ir_rc6_decoder
ir_sony_decoder
ir_jvc_decoder
```

To activate the protocols at every boot, create a systemd oneshot service
(`/etc/rc.local` does not exist by default on modern Raspberry Pi OS):

```bash
sudo tee /etc/systemd/system/ir-protocols.service << 'EOF'
[Unit]
Description=Enable IR protocol decoders
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/ir-keytable -s rc0 -p all
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ir-protocols.service
sudo systemctl start ir-protocols.service
```

Verify the service started cleanly:

```bash
sudo systemctl status ir-protocols.service
```

---

## Install Software Dependencies

```bash
sudo apt update
sudo apt install -y python3-pyqt5 python3-evdev
```

If `python3-evdev` is not available via apt:

```bash
pip3 install evdev
```

### Test the IR Receiver

With the decoder modules loaded, test that the IR receiver produces events:

```bash
python3 -m evdev.evtest
```

Select device `gpio_ir_recv` and press any button on the remote.  You should see
`EV_MSC` events with scancode values.  If you do not, see
[Troubleshooting](troubleshooting.md).

---

## Deploy the Application

### Copy the Files

```bash
mkdir -p /home/pi/Documents/show_page
cp spaac_display.py /home/pi/Documents/show_page/
cp Ararat-and-Khor-Virap.png /home/pi/Documents/show_page/
```

Or clone the repository directly:

```bash
cd /home/pi/Documents
git clone https://github.com/prjemian/show_page.git
```

### Make the Script Executable

```bash
chmod +x /home/pi/Documents/show_page/spaac_display.py
```

### Set Desktop Wallpaper

A church-themed wallpaper image (`Ararat-and-Khor-Virap.png`) is included in
the repository.

**Raspberry Pi OS with Wayfire / labwc (newer models):**

Using the touchscreen, click through these menus:

- Raspberry → Preferences → Control Centre → Desktop → Picture
- Navigate the file dialog to `Ararat-and-Khor-Virap.png`

**Raspberry Pi OS with LXDE (older Pi models / Pi 3 with 32-bit OS):**

```bash
nano ~/.config/pcmanfm/LXDE-pi/desktop-items-0.conf
```

Change the wallpaper line:

```ini
wallpaper=/home/pi/Documents/show_page/Ararat-and-Khor-Virap.png
```

### Test the Application Manually

With a display connected, run:

```bash
DISPLAY=:0 python3 /home/pi/Documents/show_page/spaac_display.py
```

The app should open full-screen.  Press Escape to quit.  If it works, proceed
to set up the service.

---

## Configure Autostart via systemd

### Install the Service File

```bash
sudo cp spaac.service /etc/systemd/system/spaac.service
```

Open the file and verify the paths and username match your installation:

```bash
sudo nano /etc/systemd/system/spaac.service
```

Key lines to check:

```ini
User=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
ExecStart=/usr/bin/python3 /home/pi/Documents/show_page/spaac_display.py
```

### Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable spaac.service
sudo systemctl start spaac.service
```

Check status:

```bash
sudo systemctl status spaac.service
```

The service starts after the graphical desktop (`graphical.target`) is ready,
with a 5-second delay to allow the X session to initialize.  If the app crashes,
systemd automatically restarts it after 5 seconds.

### Reboot Test

```bash
sudo reboot
```

The display should show the SPAAC page number screen within about 30 seconds of
power-on, with no login required.

---

## Disable Unnecessary Services (Optional)

For a dedicated kiosk installation with no network access needed:

```bash
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
sudo raspi-config
# → System Options → Boot / Auto Login → Desktop Autologin
```

Ensure the Pi logs in automatically to the desktop so the `DISPLAY=:0` X session
is available when the spaac service starts.

---

## Post-Installation: Teach the Remote

After the app is running, teach it your remote's buttons:

1. Touch the **⚙** button in the lower-right corner of the screen.
2. Tap **Teach Buttons**.
3. Follow the [Teach Mode instructions](user_guide.md#teach-mode) in the User Guide.
4. Tap **Save**.

The key mapping is saved to `~/.spaac/keymap.json` and persists across reboots.
