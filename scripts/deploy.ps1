# Copie le projet sur le Raspberry Pi, normalise les fins de ligne et teste.
#
#   .\scripts\deploy.ps1                                    # cible ANIMATED_EYE_TARGET
#   .\scripts\deploy.ps1 -Target utilisateur@hote            # autre machine
#   .\scripts\deploy.ps1 -Only "animated_eye,main.py"        # iteration rapide
#   .\scripts\deploy.ps1 -NoAssets                           # images deja sur le Pi
#   .\scripts\deploy.ps1 -Verify                             # compare les empreintes
#   .\scripts\deploy.ps1 -InstallService                     # demarrage au boot
#   .\scripts\deploy.ps1 -Identity $env:USERPROFILE\.ssh\id_ed25519
#
# Sans -Target, l'hote vient de la variable d'environnement ANIMATED_EYE_TARGET
# (un `utilisateur@hote`, une IP ou un alias de ~/.ssh/config). Il n'y a plus de
# cible par defaut : le depot ne doit contenir ni IP du reseau local ni nom de
# compte, la variable se pose une fois par machine (voir docs/DEPLOY.md).
# `pi@raspberrypi.local` ne se resout pas depuis Windows, et sous Bookworm
# l'utilisateur n'est pas forcement `pi` : une IP ou un alias ssh vaut mieux.
#
# Sans -Dest, la destination est $HOME/Animated_eye **du Pi** : le script lui
# demande son utilisateur et son $HOME au premier aller-retour, donc /home/pi en
# dur ne casse plus le deploiement quand l'utilisateur s'appelle autrement.
#
# Le transfert est un simple `scp -r`, comme ailleurs dans nos projets : pas
# d'archive, donc pas de surprise de mode ou de fin de ligne. Ensuite, en une
# seule session ssh : normalisation CRLF -> LF, creation du venv s'il manque,
# compilation de tout le Python, puis `main.py --selftest` qui charge les vraies
# images et rend 120 frames hors ecran. Si une image manque ou si pygame n'est
# pas installe, ca echoue ici et pas au moment de la projection.
#
# Pour ne plus taper de mot de passe, installer une cle une fois :
#   ssh-keygen -t ed25519
#   type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh $env:ANIMATED_EYE_TARGET "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
param(
    [string]$Target = "",
    [string]$Dest = "",
    [string[]]$Only = @(),
    [string]$Identity = "",
    [switch]$Verify,
    [switch]$NoAssets,
    [switch]$SkipTest,
    [switch]$InstallService
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

# Cible : -Target, sinon ANIMATED_EYE_TARGET (pratique pour basculer entre deux
# Pi). On peut y mettre une IP, un hostname ou un alias ssh. Aucune valeur par
# defaut : elle vivrait dans le depot avec l'IP du reseau local et le nom de
# compte (voir docs/DEPLOY.md).
if ([string]::IsNullOrWhiteSpace($Target) -and $env:ANIMATED_EYE_TARGET) {
    $Target = $env:ANIMATED_EYE_TARGET.Trim()
}
if ([string]::IsNullOrWhiteSpace($Target)) {
    throw ("aucune cible : passer -Target utilisateur@hote, ou definir " +
           "`$env:ANIMATED_EYE_TARGET = 'utilisateur@hote' (voir docs/DEPLOY.md)")
}

# Accepte `-Only a,b,c` (tableau) et `-Only "a,b,c"` (chaine).
$Items = if ($Only.Count -gt 0) {
    $Only | ForEach-Object { $_ -split ',' } |
        Where-Object { $_ } | ForEach-Object { $_.Trim() }
} else {
    $default = @(
        "animated_eye", "scripts", "tools", "tests",
        "main.py", "config.json", "requirements.txt"
    )
    if (-not $NoAssets) { $default += "assets" }
    $default
}
$RelItems = @($Items | ForEach-Object { $_ -replace '\\', '/' })

$SshArgs = @()
$ScpArgs = @()
if ($Identity) {
    $SshArgs += @("-i", $Identity)
    $ScpArgs += @("-i", $Identity)
}

$dirs = @()
$pyTargets = @()
foreach ($item in $Items) {
    $local = Join-Path $Root $item
    if (-not (Test-Path $local)) { throw "introuvable : $item" }
    if (Test-Path $local -PathType Container) {
        $dirs += $item
        $pyTargets += $item
    } elseif ($item -like "*.py") {
        $pyTargets += $item
    }
}
$chmodTargets = @($dirs + ($Items | Where-Object { $_ -like "*.*" }))

# Normalisation des fins de ligne : PowerShell ecrit du CRLF, bash non.
# Le code vit dans scripts/fix_eol.py et non en `python3 -c "..."` : le client
# OpenSSH de Windows supprime les guillemets doubles des commandes distantes, un
# one-liner arriverait mutile cote bash. Le `[ -f ]` couvre le cas `-Only` ou
# scripts/ n'est pas deploye.
$fixEol = 'if [ -f scripts/fix_eol.py ]; then python3 scripts/fix_eol.py . ; fi'

Push-Location $Root
try {
    # Premier aller-retour : il valide la connexion et, quand -Dest n'est pas
    # fourni, il donne l'utilisateur et le $HOME reels du Pi. Sous Bookworm le
    # compte n'est pas `pi` et /home/pi n'existe pas : c'est ce qui faisait
    # echouer le mkdir sans explication utile.
    Write-Host "==> connexion a $Target"
    # Guillemets simples uniquement : le client OpenSSH de Windows retire les
    # guillemets doubles des commandes distantes (`printf "%s|%s\n"` arrive en
    # `printf %s|%s\n`, soit un tube vers `%sn`). `id -un; echo $HOME` est passe
    # tel quel a bash et donne deux lignes.
    $probe = @(& ssh @SshArgs $Target 'id -un; echo $HOME')
    if ($LASTEXITCODE -ne 0) {
        throw "connexion ssh impossible vers $Target (voir le message ssh ci-dessus)"
    }
    $probeLines = @($probe | Where-Object { $_.Trim() })
    if ($probeLines.Count -lt 2) {
        throw "reponse inattendue du Pi : '$($probe -join ' / ')'"
    }
    $remoteUser = $probeLines[-2].Trim()
    $remoteHome = $probeLines[-1].Trim()
    if ([string]::IsNullOrWhiteSpace($Dest)) { $Dest = "$remoteHome/Animated_eye" }
    Write-Host "    utilisateur $remoteUser, destination $Dest"

    Write-Host "==> mkdir -p $Dest"
    & ssh @SshArgs $Target "mkdir -p '$Dest'"
    if ($LASTEXITCODE -ne 0) {
        throw "mkdir -p $Dest impossible sur $Target (voir le message ssh ci-dessus)"
    }

    foreach ($item in $Items) {
        $local = Join-Path $Root $item
        if (Test-Path $local -PathType Container) {
            Write-Host "==> scp -r $item/"
            & scp @ScpArgs -r -q $local "${Target}:${Dest}/"
        } else {
            $parent = Split-Path -Parent $item
            $remoteDir = if ($parent) { "$Dest/" + ($parent -replace '\\', '/') } else { $Dest }
            if ($remoteDir -ne $Dest) {
                & ssh @SshArgs $Target "mkdir -p '$remoteDir'"
                if ($LASTEXITCODE -ne 0) { throw "mkdir $remoteDir" }
            }
            Write-Host "==> scp $item"
            & scp @ScpArgs -q $local "${Target}:${remoteDir}/"
        }
        if ($LASTEXITCODE -ne 0) { throw "copie echouee : $item" }
    }

    $steps = @("cd '$Dest'")
    if ($chmodTargets.Count -gt 0) {
        $steps += "chmod -R u+rwX $($chmodTargets -join ' ')"
    }
    $steps += $fixEol
    if ($Items -contains "requirements.txt") {
        # Idempotent : ne fait rien si le venv est deja la.
        $steps += '([ -x .venv/bin/python ] || ' +
                  '(python3 -m venv --system-site-packages .venv && ' +
                  '.venv/bin/python -m pip install --quiet --upgrade pip && ' +
                  '.venv/bin/python -m pip install --quiet -r requirements.txt))'
        # Le wheel PyPI embarque une SDL2 sans KMSDRM : sur un Pi sans bureau
        # il ne peut pas piloter l'ecran. On retire donc ce pygame du venv
        # quand le pygame du systeme (apt) est la : le venv, cree avec
        # --system-site-packages, prendra celui-la.
        $steps += 'if python3 -c ''import pygame'' >/dev/null 2>&1; ' +
                  'then .venv/bin/python -m pip uninstall -y --quiet pygame >/dev/null 2>&1 || true; fi'
    }
    $python = if ($Items -contains "requirements.txt") { ".venv/bin/python" } else { "python3" }
    if ($pyTargets.Count -gt 0) {
        $steps += "$python -m compileall -q $($pyTargets -join ' ')"
    }
    if (-not $SkipTest -and $Items -contains "main.py" -and $Items -contains "animated_eye") {
        $steps += "$python main.py --selftest"
    }

    Write-Host "==> eol + venv + compile + selftest"
    & ssh @SshArgs $Target ($steps -join " && ")
    if ($LASTEXITCODE -ne 0) { throw "etape distante echouee (voir ci-dessus)" }

    if ($Verify) {
        if (-not ($Items -contains "scripts")) {
            Write-Warning "-Verify ignore : scripts/ n'a pas ete deploye"
        } else {
            Write-Host "==> verification des empreintes"
            $hasher = Join-Path $Root "scripts\hash_manifest.py"
            $localRaw = @(& python $hasher $Root @RelItems --digest)
            if ($LASTEXITCODE -ne 0 -or $localRaw.Count -eq 0) {
                throw "empreinte locale impossible (voir ci-dessus)"
            }
            $localDigest = $localRaw[-1].ToString().Trim()
            # `cd` indispensable : le hasher est un chemin relatif au projet, et
            # une session ssh demarre dans $HOME, pas dans $Dest.
            $remoteCmd = "cd '$Dest' && $python scripts/hash_manifest.py . $($RelItems -join ' ') --digest"
            $remoteRaw = @(& ssh @SshArgs $Target $remoteCmd)
            if ($LASTEXITCODE -ne 0 -or $remoteRaw.Count -eq 0) {
                throw "empreinte distante impossible (voir le message ssh ci-dessus)"
            }
            $remoteDigest = $remoteRaw[-1].ToString().Trim()
            if ($localDigest -ne $remoteDigest) {
                throw "copie incomplete : local $localDigest, distant $remoteDigest"
            }
            Write-Host "    empreinte identique : $localDigest"
        }
    }

    if ($InstallService) {
        if (-not ($Items -contains "scripts")) {
            Write-Warning "-InstallService ignore : scripts/ n'a pas ete deploye"
        } else {
            # Le script vit sur le Pi : il deduit l'utilisateur (SUDO_USER), le
            # dossier du projet et la carte DRM. `sudo -n` evite de rester bloque
            # sur une demande de mot de passe ; le message d'erreur donne alors la
            # commande a lancer a la main.
            Write-Host "==> service systemd (demarrage au boot)"
            & ssh @SshArgs $Target "sudo -n sh '$Dest/scripts/install_service.sh'"
            if ($LASTEXITCODE -ne 0) {
                throw ("installation du service impossible : lancer a la main  " +
                       "ssh $Target 'sudo sh $Dest/scripts/install_service.sh'")
            }
        }
    }

    Write-Host "deploye dans ${Target}:${Dest}"
    Write-Host "pour projeter :  ssh $Target 'sh $Dest/scripts/run_kms.sh'"
    Write-Host "  (run_kms.sh pose SDL_VIDEODRIVER=kmsdrm et choisit la carte DRM qui"
    Write-Host "   a un ecran branche : card0 sur Pi 4, card1 sur Pi 5)"
    Write-Host "au boot :  .\scripts\deploy.ps1 -InstallService    (ou sudo sh $Dest/scripts/install_service.sh)"
    Write-Host "si l'ecran refuse de s'ouvrir :  .venv/bin/python scripts/video_check.py"
} finally {
    Pop-Location
}
