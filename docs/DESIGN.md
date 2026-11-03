# How it works

Technical notes behind the README: the geometry, the motion model and the image
pipeline. Read this before changing `travel_*`, `iris_fraction` or anything in
`geometry.py`.

## The window is a crop, not a moving image

The eye never moves. **The window is a crop (region of interest) of the eye
image, and the crop is what slides.**

The eye image is square (2048 x 2048) and **larger than the screen**: at display
scale it is 2136 x 2136. The window is exactly the projector size, 1920 x 1080,
so it only ever shows a central band of the image.

```
        eye image (world, 3456 x 2636)
   +---------------------------------------------------+
   |                                                   |
   |          +---------------------------+            |
   |          |          window           |            |
   |          |         1920 x 1080       |            |
   |          |      (crop of the eye)    |            |
   |          +---------------------------+            |
   |                                                   |
   +---------------------------------------------------+
```

Every frame copies to the projector the screen-sized rectangle that matches the
wanted position, a few hundred pixels away in the image. The image never moves:
moving the rectangle is enough to make the eye appear to move.

Frame cost is constant: a single 1920 x 1080 copy (~0.5 ms measured), wherever
the eye is.

## What the window shows, and why eye4 is the default

The default image, `eye4.jpg`, is a glowing eye **on black**: no bright sclera,
no eyelid edge, nothing but the eye and the black. The screen is therefore a
black field with an eye on it: 17 % lit pixels, 83 % black.

The motion then reads by itself: the eye **glides in the black field**. That is
what the sliding window buys, and it reads better than a bright-sclera image
where the eye fills the screen and the movement only shows as a black band
opening on one edge.

The trade-off: since black is everywhere already, the screen edge can no longer
be used as a stop. **The eye must never be cut by the frame.** Travel is
therefore bounded by `960 - iris_diameter / 2` horizontally and
`540 - iris_diameter / 2` vertically, i.e. 684 px and 264 px with a 551 px iris
(`fit_travel()` in `geometry.py`). The chosen values (660 and 250) stay below: at
the extreme point the glowing core of the eye is still more than 70 px from the
screen edge.

A wider margin would be pointless: the glow fades out gradually, so a slightly
clipped halo is invisible, while an iris cut by a hard edge shows immediately.

The image must be **larger than the window**, otherwise there is nothing to
slide. The program checks that at start-up and reports it:

```
cadrage      ROI : la fenetre montre une decoupe de l'image
```

If you read `l'image tient dans la fenetre`, `iris_fraction` is too small: the
eye is smaller than the screen and no crop is possible.

## The two settings that matter

`iris_fraction` fixes the iris size, hence the image scale: the image is scaled
so that its iris measures `iris_fraction x screen height`. At `0.51` on 1080p
the iris is 551 px and the image 2136 px, slightly wider than the screen, so the
crop stays possible.

`travel_x` / `travel_y` fix how far the window slides, hence the apparent
motion. At 660 px the eye crosses a third of the screen width in one saccade:
1.6 saccades per second, 251 px average amplitude, 545 px maximum. That is 18 %
more than the 560 px of `eye2`, but above all it is a motion you can see: with
`eye2` the eye filled the frame and the movement only read as a black band
opening on one edge, whereas here the eye really travels through the black field.

The ratio between window and iris is `1 / iris_fraction`: at `0.51` the window
is **1.96 times** the iris height. It cannot go much lower: an iris at 2.5x
(`iris_fraction 0.40`) would give a 1676 px image, smaller than the screen, so
no crop would be possible. With `eye4` the practical minimum is
`iris_fraction 0.459`, i.e. 2.18x.

Both are tuned on site, watching the actual surface.

## The motion model

A saccade is not a smooth slide. The program reproduces three things that make
the difference between "an eye that moves" and "an image that translates":

- **minimum-jerk profile**: `s(t) = 10t^3 - 15t^4 + 6t^5`, starting and ending at
  zero speed, so it leaves sharply and lands softly;
- **duration grows with amplitude**: 30 ms for a small glance, 60 ms for a wide
  sweep;
- **micro-movements**: slow drift (Troxler drift) and micro-saccades of a few
  pixels during fixations. Without them a frozen eye looks dead.

Fixations follow a bounded log-normal law: most last 300-500 ms, a few close to
a second. Amplitudes are biased towards small movements, like a real gaze.

The controller works in normalized `[-1, 1]` coordinates and knows neither the
screen nor the pixels, which is why `tests/test_saccade.py` can check it without
a display. Screen amplitude, in px:

```
amplitude_px = hypot(dx * travel_x, dy * travel_y)
```

## The images and their photometry

| image | iris | role |
|---|---|---|
| `eye4.jpg` | 528 px (25.8 %) | glowing eye on black: default image, the one that fixes the scale |
| `eye5.jpg` | 528 px (25.8 %) | same family as `eye4`, spare image, not loaded by default |
| `eye2.jpg` | 568 px (27.7 %) | bright sclera, tight iris |
| `eye3.jpg` | 632 px (30.9 %) | same family, slightly larger iris |

`eye4.jpg` is the reference image and is of another nature than the other two: a
glowing, textured eye **on black**, with no sclera and no eyelid edge. It suits a
projector, where everything that is not the eye has to be black: 82 % of the
image is already below 16/255, and the glow around the eye merges into the black
of the world with no visible seam. The black background is both the constraint
(the eye cannot be cut) and the asset (it can travel a long way without showing
a band).

`eye2.jpg` and `eye3.jpg` are close-ups with a bright sclera: the iris takes a
little more than half the screen height, which leaves white around it and makes
the gaze more realistic. They stay available (`2` and `3`) for comparison on the
surface, but their bright background fills the screen and the movement only reads
as a black band opening on one edge.

`eye5.jpg` is a spare from the same family as `eye4`: same 528 px iris, 25.8 % of
its frame, also a glowing eye on black. It is not loaded by default, but it is
photometrically **very** close to `eye4` (3.2/255), so it is the only pair for
which the pupil fade is enabled — see below.

The images are photometrically far apart (230.5/255 between `eye4` and `eye2`,
184.3/255 between `eye4` and `eye3`, 48.0/255 between `eye2` and `eye3`), so a
fade between them would be visible. The program detects it at load time, disables
the fade and switches **hard, during a saccade**: the brain does not perceive a
change that happens during an eye movement (saccadic suppression). The threshold
is `FADE_THRESHOLD = 15.0` in `pupil.py`, and only `eye4` / `eye5` (3.2/255) get
under it.

As a consequence, with `eye4` as the reference image the brightness equalisation
(`normalize_luma`) does nothing: it aligns the sclera of each image on the
reference sclera, and the sclera of `eye4` is black — there is nothing to align.
Gains stay at 1 and the images are displayed as they are.

## Scales and hard limits

Everything is written for a 1920 x 1080 screen (`REFERENCE_VIEW` in
`geometry.py`). On another screen:

| what | function | behaviour |
|---|---|---|
| travel, in px | `scale_travel()` | scaled by `min(view_w / 1920, view_h / 1080)`, so 720p shrinks everything in the same proportion |
| eye must stay in frame | `fit_travel()` | clamps travel to `view / 2 - iris/2 - 2 % margin` (`EDGE_MARGIN`) |
| image side | `cap_scale()` | capped at `MAX_SPRITE_EXTENT = 4096` px, never reduced to fit the window |
| world memory | `clamp_travel()` | world is `image + 2 x travel`; above `MAX_WORLD_PIXELS = 24 000 000` (96 MB at 4 bytes per pixel) travel is reduced by bisection, both axes by the same factor |

`MAX_DT = 0.05` in `app.py` caps the simulation step, so a hitch cannot teleport
the eye.

## Where to look

| module | what it owns |
|---|---|
| `app.py` | the frame: advance the simulation, repaint the world, copy the window |
| `world.py` | the big black surface, where the sprite sits, `viewport(nx, ny)` |
| `geometry.py` | all the arithmetic above, with no pygame import (hence testable) |
| `eye_image.py` | radial iris measurement, brightness gain, feather mask, sprites |
| `saccade.py` | fixation/saccade state machine, minimum-jerk, drift, micro-saccades |
| `pupil.py` | which image is shown, fade or hard cut, automatic switching |
| `renderer.py` | SDL only: display selection, full screen, DPI, sleep inhibitor |
| `config.py` | `config.json`, defaults, validation, command line |


