# Animated eye

Un oeil projete en plein ecran sur une toile, qui bouge par saccades.

## Le principe

L'oeil ne se deplace pas. **La fenetre est une decoupe (ROI) de l'image de
l'oeil, et c'est elle qui glisse.**

L'image de l'oeil est carree (2048 x 2048) et **plus grande que l'ecran** : a
l'echelle d'affichage elle fait 2136 x 2136. La fenetre, elle, fait exactement la
taille du projecteur, 1920 x 1080. On n'en voit donc qu'une partie : une bande
centrale de l'image.

```
        image de l'oeil (monde, 3456 x 2636)
   +---------------------------------------------------+
   |                                                   |
   |          +---------------------------+            |
   |          |         fenetre           |            |
   |          |        1920 x 1080        |            |
   |          |     (decoupe de l'oeil)   |            |
   |          +---------------------------+            |
   |                                                   |
   +---------------------------------------------------+
```

Chaque frame, on copie vers le projecteur le rectangle de la taille de l'ecran
qui correspond a la position voulue, decale de quelques centaines de pixels dans
l'image. L'image, elle, ne bouge jamais : deplacer le rectangle suffit a donner
l'impression que l'oeil se deplace.

Le cout d'une frame est constant : une seule copie de 1920 x 1080 (mesure
~0.5 ms), quelle que soit la position de l'oeil.

### Ce que montre la fenetre

L'image par defaut, `eye4.jpg`, est un oeil lumineux **pose sur du noir** : pas de
sclerotique claire, pas de bord de paupiere, rien que l'oeil et le noir. L'ecran
est donc un champ noir avec l'oeil dessus — 17 % de pixels allumes, 83 % de noir.

Le mouvement se lit alors tout seul : l'oeil **glisse dans le champ noir**. C'est
ce que la fenetre mobile permet, et c'est plus lisible que sur une image a
sclerotique claire, ou l'oeil occupe tout l'ecran et ou le deplacement ne se voit
qu'a la bande noire qui s'ouvre sur un bord.

La contrepartie : puisque le noir est deja partout, on ne peut plus se servir du
bord de l'ecran comme butee. **L'oeil ne doit jamais etre coupe par le cadre.** Le
debattement est donc borne par `960 - diametre_iris / 2` en horizontal et
`540 - diametre_iris / 2` en vertical, soit 684 px et 264 px avec un iris de
551 px. Les valeurs retenues (660 et 250) restent en dessous : au point extreme,
le coeur lumineux de l'oeil est encore a plus de 70 px du bord de l'ecran.

Une marge plus large ne servirait a rien : la lueur s'eteint progressivement, donc
un halo legerement rogne ne se voit pas, alors qu'un iris coupe par un bord net se
verrait tout de suite.

L'image doit etre **plus grande que la fenetre**, sinon il n'y a rien a
deplacer. Le programme le verifie au demarrage et le signale :

```
cadrage      ROI : la fenetre montre une decoupe de l'image
```

Si vous lisez `l'image tient dans la fenetre`, c'est que `iris_fraction` est trop
petit : l'oeil est plus petit que l'ecran et il n'y a pas de decoupe possible.

### Les deux reglages qui comptent

`iris_fraction` fixe la taille de l'iris, donc l'echelle de l'image : l'image est
mise a l'echelle pour que son iris fasse `iris_fraction x hauteur de l'ecran`. A
`0.51` sur 1080p, l'iris fait 551 px et l'image 2136 px — un peu plus large que
l'ecran, donc la decoupe reste possible.

`travel_x` / `travel_y` fixent l'amplitude du deplacement de la fenetre, donc du
mouvement apparent. A 660 px, l'oeil traverse un tiers de la largeur de l'ecran en
une saccade : 1.6 saccade par seconde, 251 px d'amplitude moyenne, 545 px au
maximum. C'est 18 % de plus que les 560 px d'`eye2`, mais surtout un mouvement qui
se voit : avec `eye2` l'oeil remplissait le cadre et le deplacement ne se lisait
qu'a la bande noire qui s'ouvrait sur un bord, alors qu'ici l'oeil se deplace
reellement dans le champ noir.

Le rapport entre la fenetre et l'iris vaut `1 / iris_fraction` : a `0.51` la
fenetre fait **1.96 fois** la hauteur de l'iris. On ne peut pas descendre plus
bas : un iris a 2.5x (soit `iris_fraction 0.40`) donnerait une image de 1676 px,
plus petite que l'ecran, donc plus de decoupe possible. Avec `eye4` le minimum
praticable est `iris_fraction 0.459`, soit 2.18x.

Les deux se reglent sur place, en regardant la toile.

## Installation

```bash
pip install -r requirements.txt
```

Python 3.10 ou plus recent. Teste avec Python 3.12, pygame 2.6.1 (SDL 2.28).

## Lancement

```bash
python main.py                      # plein ecran sur l'ecran principal
python main.py --display 1          # sur le projecteur (deuxieme ecran)
python main.py --window             # en fenetre, pour regler sans projeter
python main.py --list-displays      # quelles sorties sont disponibles
python main.py --debug              # avec un HUD
```

Sous Windows, la resolution est lue sur l'ecran cible (`auto_size`) : si le
projecteur est en 1080p, le rendu se fait en 1920 x 1080 meme si l'ecran du
portable est en 1280 x 800.

`--window` ouvre une fenetre plus petite que le projecteur. Le debattement, lui,
reste en pixels absolus : dans une petite fenetre l'oeil sort donc du cadre plus
vite. C'est normal, et sans consequence — les valeurs de `config.json` sont
pensees pour le 1080p du projecteur.

Le programme demande a Windows de ne pas mettre l'ecran en veille et de ne pas
appliquer de mise a l'echelle DPI : sans ca, le plein ecran n'occupe qu'une
partie du projecteur.

## Deploiement sur le Pi

L'oeil peut tourner sans PC : un Raspberry Pi branche au projecteur suffit.

```powershell
.\scripts\deploy.ps1
.\scripts\deploy.ps1 -Target utilisateur@192.0.2.14                    # autre machine
.\scripts\deploy.ps1 -Target utilisateur@192.0.2.25 -Dest /home/utilisateur/Animated_eye
.\scripts\deploy.ps1 -Only "animated_eye,main.py"  # iteration rapide
.\scripts\deploy.ps1 -NoAssets                     # images deja sur le Pi
.\scripts\deploy.ps1 -Verify                       # compare les empreintes
.\scripts\deploy.ps1 -InstallService               # demarrage automatique au boot
```

Sans `-Target`, le script lit `$env:ANIMATED_EYE_TARGET`, et **aucune cible
n'est ecrite dans le depot** (ni IP du reseau local, ni nom de compte). La
variable se pose une fois par machine, hors depot ; sans elle, le script
s'arrete avec un message clair.

```powershell
# une fois pour toutes, dans l'environnement de l'utilisateur (hors depot)
[Environment]::SetEnvironmentVariable("ANIMATED_EYE_TARGET", "utilisateur@192.0.2.25", "User")

# bascule ponctuelle sur l'autre machine, pour la session courante
$env:ANIMATED_EYE_TARGET = "utilisateur@192.0.2.14"
```

Un alias de `~/.ssh/config` marche aussi (`oeil-pi`, par exemple), ce qui evite
de retenir les IP. Les exemples utilisent `192.0.2.0/24`, la plage reservee a la
documentation (RFC 5737).

Sans `-Dest`, la destination est `$HOME/Animated_eye` **du Pi** : le script lui
demande son utilisateur et son `$HOME` au premier aller-retour, donc il marche
avec n'importe quel compte (`pi` d'une vieille image, `ubuntu`, ...).

Le script copie par `scp -r`, normalise les fins de ligne (les fichiers ecrits
sous Windows sont en CRLF, Python n'aime pas), cree le venv s'il manque, compile
tout le Python puis lance `main.py --selftest` : les vraies images sont chargees
et 120 frames sont rendues hors ecran. Une image manquante ou un pygame absent
echoue donc au deploiement, pas pendant la projection.

La normalisation CRLF -> LF est faite par `scripts/fix_eol.py`, deploye avec le
projet et appele sans guillemets. Deux details de `deploy.ps1` viennent de la :
le client OpenSSH de Windows **supprime les guillemets doubles** des commandes
distantes, donc un `python3 -c "..."` inline arrive mutile cote bash (`printf
"%s|%s\n"` devient un tube vers la commande `%sn`). D'ou un script deploye
plutot qu'un one-liner, et un `id -un; echo $HOME` sans guillemets doubles pour
trouver le `$HOME` du Pi.

`--selftest` affiche le cadrage effectif, a verifier avant de projeter :

```
fenetre      1920x1080  ecran 0
monde        3456x2636
oeil         eye4  2136x2136 px  iris 551 px (51% de la hauteur)  echelle 1.043
debattement  x +/-660 px   y +/-250 px
cadrage      ROI : la fenetre montre une decoupe de l'image
ecart eye4 <-> eye2 : 230.5/255
  ! pupil_pair [0, 1] : ecart photometrique 230.5/255 > 15, fondu desactive (coupe pendant les saccades)
```

Pour ne plus taper de mot de passe, installer la cle une fois **par machine** :
la meme cle publique va dans `authorized_keys` des deux Pi, sinon ssh demande le
mot de passe a chaque fois.

```powershell
ssh-keygen -t ed25519          # une seule fois sur le PC
$pub = Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

```powershell
# une fois par machine : viser chaque Pi a tour de role
$insere = "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
$env:ANIMATED_EYE_TARGET = "utilisateur@192.0.2.25"; $pub | ssh $env:ANIMATED_EYE_TARGET $insere
$env:ANIMATED_EYE_TARGET = "utilisateur@192.0.2.14"; $pub | ssh $env:ANIMATED_EYE_TARGET $insere
```

### Si l'IP d'un Pi change

Deux Pi sur le meme reseau finissent par echanger leurs baux DHCP, et ssh refuse
alors de se connecter :

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
```

Ce n'est pas une attaque : l'ancienne cle d'hote de la *premiere* machine est
encore associee a cette IP dans `known_hosts`. On oublie l'entree perimee, puis
on relit l'empreinte de la machine pour verifier qu'elle est bien la bonne :

```powershell
$hote = ($env:ANIMATED_EYE_TARGET -split "@")[-1]            # l'IP ou le nom seul
ssh-keygen -R $hote                                          # oublie l'entree perimee
ssh -o StrictHostKeyChecking=accept-new $env:ANIMATED_EYE_TARGET "ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub"
```

La meilleure prevention reste de reserver les deux IP dans la box (bail DHCP
statique) : les empreintes restent alors associees a la bonne machine.

`scripts/hash_manifest.py` calcule l'empreinte SHA-256 des fichiers deployes (les
fichiers texte sont normalises en LF avant hachage, donc l'empreinte est la meme
des deux cotes) ; c'est ce que compare `-Verify`.

## Demarrage automatique au boot

Pour que l'oeil s'affiche des la mise sous tension, sans PC ni ssh :

```powershell
.\scripts\deploy.ps1 -InstallService
```

Le service s'appelle `animated-eye.service`. `scripts/install_service.sh` remplit
le gabarit `scripts/animated-eye.service` (`@USER@`, `@APP_DIR@`) d'apres le
compte qui lance `sudo` : rien n'est code en dur, donc ca marche pour n'importe
quel compte (`pi`, `ubuntu`, ...), et le projet peut vivre n'importe ou. Le
redemarrage est illimite
(`StartLimitIntervalSec=0`) : un plantage, ou un HDMI pas encore pret au boot, se
rattrape tout seul.

```bash
systemctl status animated-eye                 # etat
journalctl -u animated-eye -f                 # journal en direct
sudo systemctl stop animated-eye              # arreter (jusqu'au prochain demarrage)
sudo systemctl start animated-eye
sudo sh scripts/install_service.sh --remove   # desinstaller
```

Le lancement passe par `scripts/run_kms.sh`, qui pose `SDL_VIDEODRIVER=kmsdrm`
**et** choisit la carte DRM qui a un ecran branche : `/dev/dri/card0` sur un
Pi 4, `/dev/dri/card1` sur un Pi 5. C'est necessaire car sur Pi 5 `card0` est le
noeud de rendu v3d (aucun connecteur) ; SDL kmsdrm n'essaie que `card0` et
echoue avec `kmsdrm not available`, le programme retombe alors sur le pilote
`offscreen` — ecran noir, sans erreur visible.

Deux points a garder en tete :

- le service n'a pas de terminal attache, donc les raccourcis clavier (`q`, `d`,
  `espace`, `1/2/3`) ne repondent pas : passer par `systemctl` ;
- pygame doit venir d'apt (`python3-pygame`), pas de pip : le wheel PyPI embarque
  une SDL2 sans KMSDRM (voir l'en-tete de `requirements.txt`). Si l'ecran reste
  noir, `ssh ... 'cd ~/Animated_eye && .venv/bin/python scripts/video_check.py'`
  dit quel pilote ce pygame sait reellement ouvrir.

## Reglages

Tout est dans `config.json`, et chaque cle a une option en ligne de commande du
meme nom (les arguments l'emportent sur le fichier).

| cle | defaut | effet |
|---|---|---|
| `display` | `0` | index de l'ecran de sortie |
| `fullscreen` | `true` | plein ecran sans bordure |
| `auto_size` | `true` | prendre la resolution native de l'ecran cible |
| `fps` | `60` | cadence visee |
| `vsync` | `true` | synchronisation verticale (evite le tearing) |
| `iris_fraction` | `0.51` | diametre de l'iris en fraction de la hauteur : fixe l'echelle de l'image |
| `travel_x` | `660` | debattement horizontal, en px, dans chaque direction |
| `travel_y` | `250` | debattement vertical |
| `feather` | `0.12` | largeur du fondu vers le noir, en fraction du cote |
| `fixation_min_ms` / `fixation_max_ms` | `250` / `900` | duree d'un temps d'arret |
| `saccade_min_ms` / `saccade_max_ms` | `30` / `60` | duree d'un mouvement |
| `micro_saccade_chance` | `0.55` | probabilite d'une micro-correction pendant un arret |
| `micro_saccade_max_px` | `10` | amplitude maximale de ces micro-corrections |
| `drift_px_per_s` | `6` | derive lente de l'oeil pendant les arrets |
| `max_amplitude` | `1.0` | fraction du debattement utilisable par une saccade |
| `pupil_pair` | `[0, 1]` | indices des images fondues l'une dans l'autre |
| `pupil_switch_chance` | `0.12` | probabilite de changer de pupille a chaque saccade |
| `pupil_fade_ms` | `150` | duree du fondu |
| `start_eye_index` | `0` | image affichee au demarrage |
| `pupil_auto` | `true` | animation automatique de la pupille |
| `normalize_luma` | `true` | egalise la luminosite entre les images |
| `seed` | `null` | graine du hasard, pour rejouer exactement la meme animation |
| `debug` | `false` | HUD au demarrage |

### Le mouvement

Une saccade n'est pas un glissement regulier. Le programme reproduit trois
choses qui font la difference entre « un oeil qui bouge » et « une image qui
translate » :

- **le profil minimum-jerk** : `s(t) = 10t³ − 15t⁴ + 6t⁵`, depart et arrivee a
  vitesse nulle, donc un demarrage franc et un atterrissage doux ;
- **la duree depend de l'amplitude** : 30 ms pour un petit coup d'oeil, 60 ms
  pour un grand balayage ;
- **les micro-mouvements** : derive lente (Troxler drift) et micro-saccades de
  quelques pixels pendant les temps d'arret. Sans eux, l'oeil fige parait mort.

Les temps d'arret suivent une loi log-normale bornee : la plupart durent
300-500 ms, quelques-uns pres d'une seconde. Les amplitudes sont biaisees vers
les petits mouvements, comme un vrai regard.

## Les trois images

| image | iris | role |
|---|---|---|
| `eye4.jpg` | 528 px (25.8 %) | oeil lumineux sur fond noir — image par defaut, celle qui fixe l'echelle |
| `eye2.jpg` | 568 px (27.7 %) | oeil a sclerotique claire, iris serre |
| `eye3.jpg` | 632 px (30.9 %) | variante de rendu, iris un peu plus large |

`eye4.jpg` est l'image de reference. C'est une image d'une autre nature que les
deux autres : un oeil lumineux et texture **sur un fond noir**, sans sclerotique
ni bord de paupiere. Elle convient particulierement au projecteur, ou tout ce qui
n'est pas l'oeil doit etre noir : 82 % de l'image est deja a moins de 16/255, et
la lueur autour de l'oeil se fond dans le noir du monde sans raccord visible. Le
noir du fond est donc a la fois la contrainte (on ne peut pas couper l'oeil) et
l'atout (on peut le deplacer beaucoup sans faire apparaitre de bande).

`eye2.jpg` et `eye3.jpg` sont des gros plans a sclerotique claire : l'iris occupe
un peu plus de la moitie de la hauteur de l'ecran, ce qui laisse du blanc autour
de lui et rend le regard plus realiste. Ils restent disponibles (`2` et `3`) pour
comparer sur la toile, mais leur fond clair remplit tout l'ecran et le mouvement
ne se lit qu'a la bande noire qui s'ouvre sur un bord.

`eye1.jpg` (iris de 872 px, 42.6 % de son cadre) reste dans `assets/` mais n'est
pas chargee : son iris occupait les trois quarts de l'ecran. Pour la remettre,
ajouter `"eye1.jpg"` a `images` dans `config.json`.

Les images sont photometriquement eloignees les unes des autres (230.5/255 entre
`eye4` et `eye2`, 184.3/255 entre `eye4` et `eye3`, 48.0/255 entre `eye2` et
`eye3`) : un fondu entre elles se verrait. Le programme le detecte au chargement,
desactive le fondu et passe de l'une a l'autre **en coupe franche pendant une
saccade** — le cerveau ne percoit pas un changement qui a lieu pendant un
mouvement oculaire.

Consequence : avec `eye4` comme image de reference, l'egalisation de luminosite
(`normalize_luma`) ne fait rien. Elle aligne la sclerotique des images sur celle
de la reference, or celle de `eye4` est noire — il n'y a rien a aligner. Les
gains restent a 1 et les images sont affichees telles quelles.

## Hygiene du depot

Le depot ne contient **ni IP du reseau local, ni nom de compte, ni aucun
identifiant** : la cible de deploiement vit dans `ANIMATED_EYE_TARGET`, sur la
machine. Trois garde-fous :

- `ANIMATED_EYE_TARGET` est une variable d'environnement, jamais un fichier
  versionne (voir « Deploiement sur le Pi ») ;
- `.gitignore` ecarte les environnements virtuels, les journaux et les fichiers
  qui n'ont rien a faire ici (`.env`, cles privees, certificats, `known_hosts`,
  `.netrc`, ...) ;
- `scripts/hooks/pre-commit` refuse le commit s'il voit passer une cle privee,
  un jeton GitHub ou cloud, une URL contenant des identifiants en clair, une
  affectation de mot de passe ou de cle d'API, ou un fichier au nom suspect. Il
  avertit, sans bloquer, sur une adresse du reseau local.

Le hook est versionne, mais git ne l'active pas tout seul : une commande par
clone.

```bash
git config core.hooksPath scripts/hooks
```

Pour passer outre volontairement : `git commit --no-verify`.

Si un secret a deja ete pousse, le retirer du dernier commit ne suffit pas : il
reste dans l'historique. Il faut d'abord considerer le secret comme compromis
(revoquer le jeton, changer le mot de passe), puis reecrire l'historique : un
depot neuf reecrit plus vite qu'il ne se nettoie.

## Commandes

| touche | effet |
|---|---|
| `Echap` / `Q` | quitter |
| `F` | basculer plein ecran / fenetre |
| `B` | ecran noir (pour regler le projecteur) |
| `D` | HUD (fps, phase, position, amplitude) |
| `Espace` | image d'oeil suivante (boucle sur toutes les images de `assets/`) |
| `1` `2` `3` | aller directement a une image |
| `S` | forcer une saccade |
| `P` | activer / couper l'animation de pupille |
| `R` | nouvelle graine aleatoire |

`Espace` parcourt toutes les images listees dans `images` (`config.json`), dans
l'ordre, et revient a la premiere apres la derniere. Le HUD (`D`) affiche le rang
de l'image courante, `2/3` par exemple. Les images sont deja en memoire : le
changement est immediat et ne recharge rien.

Choisir une image a la main (`Espace` ou `1`..`9`) coupe l'animation automatique
de la pupille, sinon la saccade suivante pourrait ramener une autre image et
contredire le choix. `P` la rallume.

Pour faire tourner des images supplementaires, il suffit de les poser dans
`assets/` et de les ajouter a `images`. Une image dont le cote differe des autres
est acceptee : le monde est reconstruit au moment ou on l'affiche.

## Verification sans projecteur

```bash
python tools/preview.py
```

Ecrit dans `preview/` des planches PNG rendues par le meme code que
l'application :

- `world.png` — le monde complet, avec le cadre de la fenetre ;
- `eye4_corners.png`, `eye2_corners.png`, `eye3_corners.png` — chaque oeil aux
  cinq positions extremes, pour voir le noir disponible de chaque cote ;
- `feather.png` — le bord du patch sur fond rouge, pour juger le fondu ;
- `saccade.png` — une planche temporelle de 3 secondes de mouvement.

```bash
python -m pytest tests -q
```

Les tests verifient notamment que la fenetre est bien une **decoupe de l'image**
(l'oeil deborde du cadre), que l'image couvre toujours la fenetre au repos, que
le noir n'apparait qu'au bord que l'oeil quitte, que la fenetre ne sort jamais du
monde, et qu'aux huit positions extremes **l'oeil n'est jamais coupe** par le
bord de l'ecran.

## Reglage sur place

1. `python main.py --list-displays` pour trouver l'index du projecteur.
2. `python main.py --display 1 --debug` : verifier que l'image remplit bien la
   toile et que le compteur tient 60 fps.
3. `B` pour couper l'image et regler la nettete et le cadrage du projecteur.
4. Ajuster `iris_fraction` (taille de l'oeil) puis `travel_x` / `travel_y`
   (amplitude) ; le cadrage et le noir disponible en decoulent.
5. `python main.py --display 1` pour la version finale.
