# Great A'Tuin Jar Stand

A 3D-printable stand for a round, flat-bottomed jar, in the shape of Discworld's Great A'Tuin.
The star turtle swims along with the four World Elephants on her shell. The elephants carry
the Disc, and the jar sits down in the Disc.

![Great A'Tuin carrying the Disc, with a jar sitting in it](renders/hero.png)

> "Great A'Tuin the turtle comes, swimming slowly through the interstellar gulf …
> his huge and ancient shell pocked with meteor craters." (Terry Pratchett, *The Colour of Magic*)

It prints as two parts:

| Part | File | Size |
|---|---|---|
| **Base**: A'Tuin carrying Berilia, Tubul, Great T'Phon and Jerakeen | `great_atuin_base.stl` | 239 × 238 × 98 mm |
| **Disc**: a cradle the jar sits in, with the Rimfall pouring off its edge | `great_atuin_disc_152.4mm.stl` | 177 mm across, 22 mm tall |

Pegs on the elephants' backs key into holes under the Disc. Only the Disc depends on the jar's
size, so if your jar is different you regenerate and reprint just the Disc (see
[Fit your jar](#fit-your-jar)).

## Gallery

These are Blender renders of the STLs. Photos of real prints go in [`photos/`](#photos).

| | |
|---|---|
| ![Stand without the jar](renders/assembled.png) | ![The base](renders/base.png) |
| The Disc resting on the elephants | The base: scutes, meteor craters, flippers flat on the bed |
| ![The four World Elephants](renders/elephants.png) | ![A'Tuin's head](renders/head.png) |
| The World Elephants, trunks curled to their feet | "Sea-sized eyes crusted with rheum" |
| ![The Rimfall](renders/rimfall.png) | ![Underside of the Disc](renders/underside_disc.png) |
| The Rimfall pouring over rock strata | Under the Disc: each elephant's name by its peg hole |

![Underside of the base](renders/underside_base.png)

The underside of the base is engraved with *GREAT A'TUIN · Chelys galactica · THE TURTLE MOVES*,
plus the version number. Text is mirrored so it reads correctly when the part is turned over.

## Printing

Download the STLs from this repo or from the
[latest release](https://github.com/ericsandine/jar-holder/releases/latest). The parts were
designed for a Bambu Lab P2S (256 mm plate) with a 0.4 mm nozzle. The base needs a bed of at
least 240 × 240 mm.

**Disc:** print it pocket side up, flat face on the bed, with no supports.

**Base:** print it flat on the bed with no supports. Use 10–15% gyroid infill, because the base
is large and mostly solid.

- The model was sliced at 0.2 mm layers with `tools/check.py`: no region starts in mid-air.
- The elephants' bellies are flat on purpose, so they print as short bridges between the legs
  and trunk.
- The steepest overhang left is under the turtle's chin. If it sags on your printer, enable
  tree supports set to "build plate only". They will only touch the chin.

**Assembly:** set the Disc on the four pegs. It fits any of four ways round. A dab of glue
is optional. The pegs have 0.3 mm of play per side, and the holes are 0.8 mm deeper than
the pegs, so the Disc rests on the elephants' backs and not on the peg tips.

## Fit your jar

1. Measure the outside diameter across the **bottom 12 mm** of the jar. That is the part
   that sits down in the pocket. Calipers are best.
2. Regenerate the Disc. You can give the diameter in millimetres or inches:

   ```sh
   .venv/bin/python atuin.py --jar-diameter 153.5 --parts disc
   .venv/bin/python atuin.py --jar-diameter 6.04in --parts disc
   ```

3. Print the new `great_atuin_disc_<diameter>mm.stl`. The base stays the same.

| Option | Default | Meaning |
|---|---|---|
| `--jar-diameter` | `152.4` (6 in) | Jar base diameter, in mm or with an `in` suffix |
| `--clearance` | `1.0` | Gap per side between the jar and the pocket wall, mm |
| `--pocket-depth` | `12` | How far the jar sits down into the Disc, mm |
| `--parts` | `all` | `all`, `base` or `disc` |
| `--resolution` | `0.35` | Mesh voxel size, mm. Use `0.8` for a quick draft |
| `--out` | repo folder | Where to write the STLs |

## Development

The geometry lives in one file, `atuin.py`. Organic shapes (shell, creatures, Rimfall) are
signed distance fields meshed with marching cubes. The jar pocket, pegs, holes and engraving
are exact CAD booleans done with [manifold3d](https://github.com/elalish/manifold).

```sh
make setup     # create .venv and install requirements.txt (Python 3.11+)
make stl       # regenerate both STLs           (JAR=153.5 make stl for another jar, in mm)
make check     # printability and fit checks; must print PASS
make renders   # re-render renders/*.png         (needs Blender 4.x on PATH)
make all       # stl + check + renders
```

The engraving uses macOS's Luminari font. On other systems it falls back to a bold sans
font, which changes how the engraved text looks.

Contributors and AI agents: [AGENTS.md](AGENTS.md) has the full iteration checklist, the
design rules and the release process.

## Versioning

Versions follow [semantic versioning](https://semver.org), with the parts' fit in mind:

- **MAJOR**: the base/Disc interface changed (peg layout, peg size or seat height). A Disc
  from an older major version won't fit a newer base, or the reverse.
- **MINOR**: a visible design change, a new feature, or a new default jar size.
- **PATCH**: printability or mesh fixes with no intended visible change.

The version is in `atuin.py` (`__version__`) and is engraved under both parts, so you can tell
which version a print came from. Changes are listed in [CHANGELOG.md](CHANGELOG.md). Every
version is tagged `vX.Y.Z` and has a GitHub release with its STLs attached.

## Photos

Photos of real prints go in `photos/`, and the README links them alongside the renders.

## Credits

This is an unofficial fan project. Discworld, Great A'Tuin and the World Elephants are the
creations of Sir Terry Pratchett. GNU Terry Pratchett.
