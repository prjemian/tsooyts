# SPAAC Show Page Number

Electronic display to show the congregation the current page number.
Also show when is is appropriate to stand, sit, or kneel.  A TV
remote directs the page number on the screen.

Implement using RaspberryPi with 7" touch-screen display, IR receiver,
and TV remote.  IR receiver should be packaged to avoid damage.

Normal display should be full screen with page numbers clearly visible
from the back of the church.  Background color can be same as the book.

App should have a setup mode (accessible from touch screen) to control
button repetition  (delay before repeat, maximum repeats/second).  Also
need a teach mode for app to map buttons on the remote to app functions.

RPi should startup and launch the app directly.  No need for WiFi, or
other KVM inputs.

## Install wallpaper

Change the stock background image.

### Newer RPi models an OS

Using the touchscreen, click through these menus:

- Raspberry
- Preferences
- Control Centre
- Desktop
- Picture
- navigate the file dialog to the new image

### Older RPi using LXDE

Edit  ...

```bash
nano ~/.config/pcmanfm/LXDE-pi/desktop-items-0.conf
```

change this line:

```ini
wallpaper=/home/pi/Documents/show_page/Ararat-and-Khor-Virap.png
```
