# Configuration

Everything lives in `config.json` at the project root. Every key has a
command-line option of the same name, and the command line wins over the file.

```bash
python main.py --iris-fraction 0.55 --travel-x 700
python main.py --config other.json
```

| key | default | effect |
|---|---|---|
| `images` | `["eye4.jpg", "eye2.jpg", "eye3.jpg"]` | eye images to load, in key order |
| `reference_image` | `eye4.jpg` | image that fixes the common scale (`null` = first) |
| `pupil_pair` | `[0, 1]` | indices in `images` swapped during a saccade |
| `normalize_luma` | `true` | equalise brightness between images |
| `pupil_switch_chance` | `0.12` | chance of swapping the pupil on a saccade |
| `pupil_fade_ms` | `150` | fade duration (dropped when images differ too much) |
| `start_eye_index` | `0` | image shown at start-up |
| `pupil_auto` | `true` | automatic pupil animation |
| `display` | `0` | output screen index |
| `width` / `height` | `1920` / `1080` | window size when `auto_size` is off |
| `fullscreen` | `true` | borderless full screen |
| `auto_size` | `true` | use the native resolution of the target screen |
| `fps` | `60` | target frame rate |
| `vsync` | `true` | vertical sync (avoids tearing) |
| `iris_fraction` | `0.51` | iris diameter as a fraction of screen height: sets the image scale |
| `travel_x` | `660` | horizontal travel, in px, in each direction |
| `travel_y` | `250` | vertical travel |
| `feather` | `0.12` | width of the fade to black, as a fraction of the patch side |
| `fixation_min_ms` / `fixation_max_ms` | `250` / `900` | duration of a fixation |
| `saccade_min_ms` / `saccade_max_ms` | `30` / `60` | duration of a movement |
| `micro_saccade_chance` | `0.55` | chance of a micro-correction during a fixation |
| `micro_saccade_max_px` | `10` | maximum size of those micro-corrections |
| `drift_px_per_s` | `6` | slow drift of the eye during fixations |
| `max_amplitude` | `1.0` | fraction of the travel a saccade may use |
| `seed` | `null` | random seed, to replay the same animation exactly |
| `debug` | `false` | HUD at start-up |

Values that would break the framing are corrected at start-up and reported as
warnings (`Config.validate()`): a travel larger than `fit_travel()` allows, a
world larger than the memory budget, an unknown key.

## Command line

```
python main.py --help            # every option, generated from the settings
python main.py --list-displays   # available outputs and their index
python main.py --selftest        # load the images, render 120 frames, check framing
python main.py --window          # windowed, for tuning without a projector
python main.py --config other.json
```

`--config`, `--list-displays` and `--selftest` are execution modes, not settings:
they are ignored when the settings are applied.

## What start-up prints

```
window       1920x1080  screen 0  driver x11
world        3456x2636
eye          eye4  2136x2136 px  iris 551 px (51% of the height)  scale 1.043
travel       x +/-660 px   y +/-250 px
framing      ROI: the window shows a crop of the image
residual eye4 <-> eye2: 230.5/255
residual eye4 <-> eye3: 184.3/255
  ! pupil_pair [0, 1]: photometric residual 230.5/255 > 15, fade disabled (hard cut during saccades)
```

`window` is the size actually opened, with the screen index and the video driver
(`dummy` under `--selftest`). `world` must equal the image side plus twice the
travel. `framing` should read `ROI: ...`; `the image fits in the window` means
`iris_fraction` is too small (see [DESIGN.md](DESIGN.md)).

A line starting with `!` is a warning: a corrected value, a disabled fade, a
fallback driver. `--selftest` adds `selftest: 120 frames in ... s (... fps
without vsync)` and an `ERROR` line per framing problem, and exits non-zero if
there is one.

## Adding images

1. Drop the file in `assets/`.
2. Add its name to `images` in `config.json`.
3. If needed, set `start_eye_index`, or `reference_image` to the image whose iris
   defines the scale.

The iris is measured on load (radial profile, see `eye_image.measure_iris`), so
nothing has to be entered by hand. Images of a different size are accepted; the
world is rebuilt when one is displayed.
