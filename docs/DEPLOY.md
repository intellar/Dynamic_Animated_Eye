# Deployment on a Raspberry Pi

The eye can run without a PC: a Pi wired to the projector is enough, and it can
start at boot.

## The target

The deploy target is **never stored in the repository** (no LAN address, no
account name). It comes from `ANIMATED_EYE_TARGET`, on the machine that deploys:

```powershell
# once per machine, in the user environment (outside the repository)
[Environment]::SetEnvironmentVariable("ANIMATED_EYE_TARGET", "user@192.0.2.25", "User")

# one-off switch to the other machine, for the current session
$env:ANIMATED_EYE_TARGET = "user@192.0.2.14"
```

An `~/.ssh/config` alias works too (`oeil-pi`), which saves remembering the
addresses. The examples use `192.0.2.0/24`, the range reserved for
documentation (RFC 5737).

Without `-Target` and without the variable, the script stops with a clear
message instead of guessing.

## What the script does

```powershell
.\scripts\deploy.ps1                                  # whole project
.\scripts\deploy.ps1 -Only "animated_eye,main.py"     # quick iteration
.\scripts\deploy.ps1 -NoAssets                        # images already on the Pi
.\scripts\deploy.ps1 -Verify                          # compare checksums
.\scripts\deploy.ps1 -InstallService                  # start at boot
.\scripts\deploy.ps1 -Identity $env:USERPROFILE\.ssh\id_ed25519
```

1. One ssh round trip to learn the real user and `$HOME` of the Pi; without
   `-Dest` the destination is `$HOME/Animated_eye`.
2. `scp -r` of each item (no archive: no surprise with modes or line endings).
3. In a single ssh session: `chmod`, CRLF -> LF normalisation
   (`scripts/fix_eol.py`), creation of `.venv` if missing, `compileall` of the
   whole Python tree, then `main.py --selftest`.
4. With `-Verify`, the SHA-256 manifest of the deployed files is compared with
   the local one (`scripts/hash_manifest.py`, text files normalised to LF before
   hashing, so both sides agree).

A missing image, a broken pygame or a bad framing therefore fails **at
deployment**, not in the middle of the show.

### Why a script and not a one-liner

The Windows OpenSSH client **strips double quotes** from remote commands, so an
inline `python3 -c "..."` arrives mangled on the bash side (`printf "%s|%s\n"`
becomes a pipe into `%sn`). Hence a deployed script, called without quotes, and
`id -un; echo $HOME` with no quotes to find the Pi's home directory.

## SSH key, once per machine

```powershell
ssh-keygen -t ed25519                                   # once on the PC
$pub = Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
$insere = "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
$env:ANIMATED_EYE_TARGET = "user@192.0.2.25"; $pub | ssh $env:ANIMATED_EYE_TARGET $insere
$env:ANIMATED_EYE_TARGET = "user@192.0.2.14"; $pub | ssh $env:ANIMATED_EYE_TARGET $insere
```

### When a Pi changes address

Two Pis on the same network eventually swap DHCP leases, and ssh then refuses:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
```

That is not an attack: the old host key of the *first* machine is still attached
to that address in `known_hosts`. Forget the stale entry, then read the
fingerprint again to check it is the right machine:

```powershell
$hote = ($env:ANIMATED_EYE_TARGET -split "@")[-1]     # address or name only
ssh-keygen -R $hote                                   # forget the stale entry
ssh -o StrictHostKeyChecking=accept-new $env:ANIMATED_EYE_TARGET "ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub"
```

The real fix is two static DHCP leases in the router: fingerprints then stay
attached to the right machine.

## Start at boot

So the eye lights up as soon as the projector has power, with no PC and no ssh:

```powershell
.\scripts\deploy.ps1 -InstallService
```

The service is called `animated-eye.service`. `scripts/install_service.sh` fills
the template `scripts/animated-eye.service` (`@USER@`, `@APP_DIR@`) from the
account that runs `sudo`: nothing is hard-coded, so it works for any account
(`pi`, `ubuntu`, …) and the project can live anywhere. Restart is unlimited
(`StartLimitIntervalSec=0`): a crash, or an HDMI link not ready at boot, recovers
by itself.

```bash
systemctl status animated-eye                 # state
journalctl -u animated-eye -f                 # live log
sudo systemctl stop animated-eye              # stop (until next boot)
sudo systemctl start animated-eye
sudo sh scripts/install_service.sh --remove   # uninstall
```

### kmsdrm, and why run_kms.sh exists

The service starts `scripts/run_kms.sh`, which sets `SDL_VIDEODRIVER=kmsdrm`
**and** picks the DRM card that has a display attached: `/dev/dri/card0` on a
Pi 4, `/dev/dri/card1` on a Pi 5. This matters because on a Pi 5 `card0` is the
v3d render node with no connector; SDL kmsdrm only tries `card0` unless
`SDL_VIDEO_KMSDRM_DEVICE` is set, and fails with `kmsdrm not available` while
the program silently falls back to the `offscreen` driver — black screen, no
error.

Two things to keep in mind:

- the service has no terminal, so the keyboard shortcuts (`q`, `d`, `space`,
  `1/2/3`) do nothing: use `systemctl`;
- pygame must come from apt (`python3-pygame`), not pip: the PyPI wheel ships an
  SDL2 **without KMSDRM**, so it cannot drive the screen from a console. The
  venv is created with `--system-site-packages`, so it picks up the apt pygame;
  `deploy.ps1` even uninstalls the pip one when both are present.

## Troubleshooting

| symptom | what to do |
|---|---|
| black screen at boot, service running | `journalctl -u animated-eye -f`; then `ssh … 'cd ~/Animated_eye && .venv/bin/python scripts/video_check.py'` says which drivers this pygame can actually open |
| `kmsdrm not available` | check `/dev/dri/card*`, the user is in the `video` group, no desktop running |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | see "When a Pi changes address" above |
| deploy fails at `--selftest` | an image is missing, or the framing is wrong: run `python main.py --selftest` locally to compare |
| ssh asks for a password every time | install the public key (see above) |
| `Permission denied (publickey)` for `sudo` | the service install uses `sudo -n`; run `sudo sh scripts/install_service.sh` by hand once |

