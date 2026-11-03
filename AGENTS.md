# Working on this project

Handoff notes so that a human or an AI assistant can pick this up cold. The
public description is in [README.md](README.md); the technical reasoning is in
[docs/DESIGN.md](docs/DESIGN.md), [docs/CONFIG.md](docs/CONFIG.md) and
[docs/DEPLOY.md](docs/DEPLOY.md).

## What the program is

A pygame application that projects a single eye full screen and animates it with
saccades, drift and a changing pupil. The illusion comes from one trick: the eye
image is bigger than the screen and **the window is a crop of it**; sliding the
crop makes the eye appear to move. Runs on Windows (dev) and on a Raspberry Pi
(no desktop, SDL kmsdrm).

## Invariants — do not break these

1. **The image never moves and is never rescaled per frame.** One `blit` of a
   1920 x 1080 rectangle per frame (`Renderer.present`). Anything that resizes,
   fills or scrolls the world per frame destroys the constant frame cost.
2. **The window must stay a crop of the image** (`geometry.is_region_of_interest`).
   If the image fits in the window there is nothing to slide and the illusion is
   gone. `iris_fraction` too small is the usual cause.
3. **The eye must never be cut by the edge of the screen.** Travel is clamped by
   `fit_travel()` to `view/2 - iris/2 - EDGE_MARGIN`. Raising `travel_*` in
   `config.json` past that is silently corrected (with a warning) at start-up.
4. **The window never leaves the world**: `World.viewport()` clamps the offset to
   the surface size (`tests/test_world.py`).
5. **Nothing machine-specific in the repository**: no address, no account, no
   credential. The deploy target is the `ANIMATED_EYE_TARGET` environment
   variable, and `scripts/hooks/pre-commit` blocks secrets.
6. **Text is LF in the repository** (`.gitattributes`). `scripts/hooks/pre-commit`
   and every `*.sh` must stay LF on disk, or `sh` refuses to run them.

## Data flow, per frame

```
clock.tick(fps) -> dt (capped at MAX_DT = 0.05)
SaccadeController.update(dt)      # normalized position in [-1, 1], phase
PupilState.update(dt)             # fade progress
World.paint_sprite(base, overlay, alpha)   # repaints only if the sprite changed
Renderer.present(world.surface, world.viewport(nx, ny))   # the one blit
Renderer.draw_hud(...)            # optional, debug only
pygame.display.flip()
```

`App.step(dt)` is exactly that, without the clock and the flip; `App.run()` is the
real loop. `tools/preview.py` and `--selftest` reuse `App.step`/the world code so
that what they draw is what the projector shows.

## Modules

| file | responsibility | key entry points |
|---|---|---|
| `animated_eye/cli.py` | command line, `--list-displays`, `--selftest` | `main()`, `selftest()` |
| `animated_eye/headless.py` | forces the SDL `dummy` driver before pygame is imported | `apply()` |
| `animated_eye/app.py` | the loop, travel resolution, HUD | `App`, `App.step()`, `App.run()` |
| `animated_eye/world.py` | big black surface, sprite placement, crop rectangle | `build_world()`, `World.viewport()` |
| `animated_eye/eye_image.py` | radial iris measurement, brightness gain, feather mask, sprites | `load_eyes()`, `measure_iris()` |
| `animated_eye/saccade.py` | fixation/saccade state machine | `SaccadeController`, `minimum_jerk()` |
| `animated_eye/pupil.py` | which image is displayed, fade vs hard cut | `PupilState` |
| `animated_eye/geometry.py` | crop/travel/memory arithmetic, **no pygame** | `fit_travel()`, `scale_travel()`, `clamp_travel()`, `cap_scale()`, `world_size()` |
| `animated_eye/config.py` | defaults, `config.json`, CLI, validation | `Config`, `load_from_argv()` |
| `animated_eye/renderer.py` | SDL only: display, full screen, DPI, sleep inhibitor | `Renderer`, `open_window()` |
| `tools/preview.py` | PNG control sheets, no projector needed | `main()` |
| `scripts/` | Pi deployment, systemd unit, EOL/checksum helpers, git hook | `deploy.ps1`, `run_kms.sh` |
| `tests/` | pytest, headless | 42 tests, ~5 s |

## Commands

```bash
pip install -r requirements-dev.txt        # runtime + pytest
python main.py                            # full screen on the main screen
python main.py --window --debug           # windowed with HUD
python main.py --list-displays            # output indices
python main.py --selftest                 # headless: load images, 120 frames
python -m pytest tests -q                 # unit tests
python tools/preview.py                   # preview/*.png + motion statistics
git config core.hooksPath scripts/hooks    # enable the secret guard (once)
```

## Validate a change — checklist

1. `python -m pytest tests -q` → all green, no display needed.
2. `python main.py --selftest` → exit 0, `cadrage ROI …`, and a plausible fps.
3. `python tools/preview.py` → look at `preview/*.png`. Stable reference values
   with the shipped config: ~1.6 saccades/s, 251 px mean amplitude, 545 px max,
   47 ms mean saccade, 335 ms mean fixation. A change to `travel_*` or
   `iris_fraction` moves these numbers; a change to the motion model should not
   move them wildly.
4. If geometry changed: read the start-up report (`fenetre`, `monde`, `oeil`,
   `debattement`) and confirm `monde = image + 2 x travel` and that the eye is
   still inside the frame at the extremes.

## Conventions

- Python 3.10+, `from __future__ import annotations`, dataclasses, type hints on
  public functions. No formatter is configured: match the surrounding style.
- **Code comments and docstrings are French** (without accents, ASCII only);
  README, `docs/` and `AGENTS.md` are English. When you touch a file, stay in the
  language of that file rather than mixing.
- Keep pure logic out of pygame: everything arithmetic lives in `geometry.py`
  (no pygame import) or works on normalized coordinates (`saccade.py`), which is
  what makes `tests/` runnable without a display.
- Tests must never need a screen: `tests/conftest.py` sets `SDL_VIDEODRIVER=dummy`.
- Commits: English imperative subject, short bullets in the body.
- New dependency: justify it in the commit. On Linux pygame must keep coming from
  apt (`python3-pygame`) — the PyPI wheel has no KMSDRM.

## Gotchas

- `PYGAME_HIDE_SUPPORT_PROMPT` is set in `animated_eye/__init__.py`, before any
  pygame import. Do not move it below one, or the banner comes back in the CLI
  output.
- `--selftest` must switch SDL to `dummy` **before** pygame is imported
  (`animated_eye/headless.py`, imported first by `main.py` and `__main__.py`).
  Reordering those imports reintroduces a window / display requirement.
- `--config` is resolved by `config.load_from_argv()`; keys that are execution
  modes (`config`, `list_displays`, `selftest`) live in `_CLI_ONLY` and are never
  copied onto `Config`.
- The `pkg_resources is deprecated` warning comes from pygame itself, not from
  this project.
- In PowerShell, git writing on stderr shows up as `NativeCommandError` with exit
  code 1 even when the command succeeded (push, bundle, hooks). Read the actual
  git output before believing the exit code.
- `preview/` is gitignored and regenerated by `tools/preview.py`; the photos used
  by the README live in `docs/` and are never overwritten.
- The pre-commit hook needs Git-for-Windows' `sh`; git invokes it automatically.
  If you edit it, keep it LF (`file`/byte check: no `0x0D`).

## Known gaps / next steps

1. **User-visible strings are still French** (`App.report()`, the warnings from
   `Config.validate()`, the argparse help). For a public English repository they
   should be translated. Nothing asserts on those strings, so it is a safe but
   broad change.
2. **Code comments/docstrings are French**, like the rest of the Intellar code
   base. Same decision as above.
3. **Two dead PNG blobs are still in history** (`docs/demo_1.png`,
   `docs/demo_2.png`, ~1.3 MB) from before they were converted to JPEG. Removing
   them needs a history rewrite (`git filter-branch --index-filter …`).
4. **No CI.** The test suite is headless and takes ~5 s, and
   `python main.py --selftest` works headless too, so a GitHub Actions matrix
   (ubuntu + windows) would be cheap. None of the sibling Intellar repositories
   has CI, which is why there is none here.
5. **The eye images are AI-generated** and this is now documented: Google's
   image model, C2PA-signed, SynthID watermarked (`assets/README.md`). The code
   is MIT; the images are used under Google's terms for generative output, and
   their AI origin has to be disclosed when they are reused. Read from the C2PA
   manifests, not assumed.
6. **The pupil fade is effectively dead code with the shipped images**: the
   photometric distance between them (230.5/255) is far above
   `FADE_THRESHOLD = 15.0`, so the code always takes the hard-cut path. Keep it
   (it is the right behaviour for pairs that do match), but do not "fix" it by
   raising the threshold without looking at `tools/preview.py`.

## Where the details live

| question | file |
|---|---|
| why a crop, why these bounds, why eye4 | [docs/DESIGN.md](docs/DESIGN.md) |
| what each key does, what start-up prints | [docs/CONFIG.md](docs/CONFIG.md) |
| Pi, ssh, systemd, kmsdrm, troubleshooting | [docs/DEPLOY.md](docs/DEPLOY.md) |
| the public pitch, the video, the photos | [README.md](README.md) |
| the image catalogue and its measurements | [assets/README.md](assets/README.md) |

