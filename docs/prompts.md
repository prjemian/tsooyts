# Page display for SPAAC

2026-03-02

Create an electronic display to show the congregation the current page
number (in the blue book) at church. Also show when congregation should
stand, sit, or kneel.  A member of the congregation will hold the TV
remote that directs the page number on the screen.

Implement using RaspberryPi with 7" touch-screen display, IR receiver,
and TV remote.  IR receiver should be packaged to avoid damage.

Build a Python app using evdev package and either PyQt (preferred) or Tkinter.

Normal display should be full screen with page numbers clearly visible
from the back of the church.  Background color can be same as the book.

App should have a setup mode (accessible from touch screen) to control
button repetition  (delay before repeat, maximum repeats/second).  Also
need a teach mode for app to map buttons on the remote to app functions.

RPi should startup and launch the app directly.  No need for WiFi, or
other KVM inputs.

description                 | IR remote signal
------------                | -----------
increment to next page      | RIGHT button
decrement to previous page  | LEFT button
congregation should stand   | UP button
congregation should sit     | DOWN button
congregation should kneel   |
dial in page number         | number buttons
accept new page number      | ENTER button
cancel page number change   | LAST button or STOP button
setup and training          | SETUP button

Empirical observation: Using `evdev` in a demo app, only `EV_MSC` and 
`EV_SYN` (no `EV_KEY`) events were received.

## Update prompts

Checklist items below marked FIXME or TODO should be addressed.  When
complete, check the items off the list.  (Do not delete them).
Keep a separate log summarizing each update session.

## Blank page feature

- [x] Add a new command to show a blank page (keep the settings
button in the lower corner).
- [x] Make various color choices configurable, keep the defaults.

## Icons for stand, site, kneel

- [x] Replace stand, kneel, ... text with posture icons
  - [x] PNG files in docs subdirectory
  - [x] kneel: appears below middle of screen on right side
  - [x] sit: appears at middle of screen on right side
  - [x] stand: appears above middle of screen on right side
  - [x] Rearrange display so image appears to right of numbers.
  - [x] Does not block settings icon
  - [x] Visible per 10 foot interface.
  - [x] Increase (maximize) size of displayed page numbers to fit space, with border.

## 2026-03-18 session

- [x] Fix posture icons rendering as solid-color rectangles (PNG files
  lacked alpha channel; `_colorize_pixmap` now handles missing alpha
  defensively).
- [x] Restore original hand-drawn posture icon PNGs from the `.odg`
  source; convert from black-on-white RGB to white-on-transparent RGBA
  so compositing works correctly.
- [x] Remove colored border around displayed page numbers.
- [x] Restructure Settings dialog as a tabbed panel (Settings, Colors,
  Teach, Test) instead of cramming everything onto one page with
  sub-dialogs.  `TeachDialog` and `TestButtonDialog` classes removed;
  their content is now embedded as tabs.
- [x] Increase page number font size (base 200pt -> 260pt) for better
  readability on the 800x480 RPi 7" touchscreen.
- [x] Update all documentation (README, User Guide, Installation Guide,
  Troubleshooting) to reflect UI changes.  Screenshot placeholders
  marked with `<!-- TODO: replace with updated screenshot -->`.

## 2026-03-21: rename repo

- future: Consider renaming the repo and app
  - tsooyts (ցույց), neams "show"
