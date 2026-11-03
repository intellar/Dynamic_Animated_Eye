# images d'oeil

Quatre images de `2048 x 2048` sont fournies, cadrage serre sur l'oeil, iris
centre. Trois sont utilisees.

| fichier | iris (diametre) | % de l'image | fond | role |
|---|---|---|---|---|
| `eye4.jpg` | 528 px | 25.8 % | noir | oeil lumineux sur fond noir — **image de reference** |
| `eye2.jpg` | 568 px | 27.7 % | blanc 242 | sclerotique claire, petit iris |
| `eye3.jpg` | 632 px | 30.9 % | blanc 195 | sclerotique claire, rendu plus chaud |
| `eye1.jpg` | 872 px | 42.6 % | blanc 239 | pupille large — **non utilisee** |

`eye4` est d'une autre nature que les trois autres : pas de sclerotique, pas de
bord de paupiere, un oeil lumineux et texture **pose sur du noir**. 82 % de ses
pixels sont sous 16/255. C'est ce qui en fait la meilleure image pour le
projecteur : le noir du fond se confond avec le noir du monde, aucun raccord n'est
visible, et l'oeil peut se deplacer beaucoup sans qu'une bande claire n'apparaisse
sur un bord.

`eye2` et `eye3` sont des gros plans a sclerotique claire : leur iris est assez
petit pour laisser du blanc autour de lui une fois l'image projetee, mais ce blanc
remplit tout l'ecran et le mouvement ne se lit qu'a la bande noire qui s'ouvre sur
un bord. `eye1`, dont l'iris occupe 42.6 % du cadre, remplissait l'ecran de blanc
et ne laissait pas de place au regard.

Ces mesures sont refaites a chaque demarrage. Le programme trouve le limbe
(l'anneau sombre autour de l'iris) par profil radial, puis remonte jusqu'au bord
de l'iris. Il n'y a donc rien a saisir a la main si les images changent.

Deux familles d'images sont reconnues, et mesurees differemment :

- **fond clair** (`eye1`, `eye2`, `eye3`) : on part du plateau de sclerotique et
  on marche vers l'interieur jusqu'au limbe sombre ;
- **fond noir** (`eye4`) : la sclerotique n'existe pas, donc on part du pic
  radial de luminance et on marche vers l'exterieur jusqu'a ce que le profil
  retombe. Le seuil est `sclera_level < 40`.

Les images sont photometriquement eloignees les unes des autres (230.5/255 entre
`eye4` et `eye2`, 184.3/255 entre `eye4` et `eye3`, 48.0/255 entre `eye2` et
`eye3`) : un fondu entre elles se verrait, donc l'animation de pupille automatique
se desactive et le changement se fait en coupe franche pendant une saccade.

L'egalisation de luminosite (`normalize_luma`) aligne la sclerotique des images
sur celle de la reference. Avec `eye4` comme reference, cette zone est noire :
il n'y a rien a aligner, les gains restent a 1 et les images sont affichees telles
quelles. Aucun gain, aucun gamma, aucun boost n'est applique.

Les images n'ont pas de bord noir (sauf `eye4`, qui en est fait) : le fondu vers
le noir est fabrique au chargement (voir `feather` dans `config.json`). C'est ce
fondu qui permet a l'image de deborder de la fenetre sans montrer un bord net.

Une image d'oeil doit etre **plus grande que l'ecran une fois mise a l'echelle**
pour que la fenetre soit une vraie decoupe. La contrainte, pour un iris de `d`
pixels dans une image de 2048 : `iris_fraction x hauteur_ecran / d x 2048 >
largeur_ecran`. En 1080p cela donne `iris_fraction > 0.459` pour `eye4` et
`> 0.505` pour `eye2`.
