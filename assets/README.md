# Eye images

Four `2048 x 2048` images ship with the project, tightly framed on the eye with
the iris centred. Three are loaded by default; the fourth is a spare.

| file | iris diameter | of the frame | background | role |
|---|---|---|---|---|
| `eye4.jpg` | 528 px | 25.8 % | black (11/255) | glowing eye on black: **reference image**, fixes the common scale |
| `eye5.jpg` | 528 px | 25.8 % | black (13/255) | same family as `eye4`, spare, not loaded by default |
| `eye2.jpg` | 568 px | 27.7 % | bright (242/255) | bright sclera, tight iris |
| `eye3.jpg` | 632 px | 30.9 % | bright (195/255) | same family, slightly larger iris, warmer rendering |

These numbers are re-measured at every start-up. The program finds the limbus
(the dark ring around the iris) from the radial luminance profile, then walks up
to the iris edge, so nothing has to be entered by hand when the images change.

Two families are recognised and measured differently:

- **bright background** (`eye2`, `eye3`): start from the sclera plateau and walk
  inwards to the dark limbus;
- **black background** (`eye4`, `eye5`): there is no sclera, so start from the
  radial luminance peak and walk outwards until the profile drops. The switch is
  `sclera_level < 40`.

## Photometric distances

`loaded as a pair` means the two images are shown alternately for the pupil
animation. The residual is the mean absolute difference, 0-255, measured on the
sclera band:

| pair | residual |
|---|---|
| `eye4` ↔ `eye5` | **3.2** |
| `eye2` ↔ `eye3` | 48.0 |
| `eye3` ↔ `eye5` | 183.7 |
| `eye4` ↔ `eye3` | 184.3 |
| `eye5` ↔ `eye2` | 229.1 |
| `eye4` ↔ `eye2` | 230.5 |

A fade is only used below `FADE_THRESHOLD = 15.0` (`animated_eye/pupil.py`);
above it the switch is a hard cut during a saccade, which the eye does not
perceive (saccadic suppression).

With the default `images` (`eye4`, `eye2`, `eye3`) and `pupil_pair [0, 1]` every
pair is far apart, so the fade is disabled. `eye4` and `eye5` are the exception:
with `"images": ["eye4.jpg", "eye5.jpg"]` and `"pupil_pair": [0, 1]` the pupil
cross-fades instead of cutting.

## Constraint

An eye image must be **larger than the screen** once scaled, otherwise the window
is not a crop of it and the illusion disappears. For an iris of `d` px in a
2048 px image: `iris_fraction x screen_height / d x 2048 > screen_width`. At
1080p that gives `iris_fraction > 0.459` for `eye4` and `> 0.505` for `eye2`.

The glow fades out gradually, so the images need no black border (except `eye4`,
which is made of it): the fade towards black is built at load time, see `feather`
in `config.json`. That is what lets the image overflow the window without showing
a hard edge.
