# AGENTS.md

These are instructions for AI coding agents and humans iterating on this repo. Read them
before changing anything. The README is for people who want to print the stand. This file is
for people who change it.

## What's here

| Path | What it is |
|---|---|
| `atuin.py` | The whole model: parameters, SDF sculpting, mesher, CAD booleans and STL export. Has `__version__`. |
| `great_atuin_base.stl`, `great_atuin_disc_<D>mm.stl` | Generated outputs. Committed so people can print without running anything. |
| `tools/check.py` | Printability and fit checks. Exits 1 on failure. |
| `tools/render.py` | Blender script that writes `renders/*.png` for the README. |
| `renders/` | Generated README images. Never edit them by hand. |
| `photos/` | Photos of real prints, added by hand. It doesn't exist until the first one is added. |
| `Makefile` | `setup`, `stl`, `disc`, `check`, `renders`, `all` (`JAR=<mm>` changes the jar). |
| `CHANGELOG.md` | One entry per version ([Keep a Changelog](https://keepachangelog.com)). |

Setup: `make setup` creates `.venv` from `requirements.txt`. Renders need Blender 4.x on `PATH`.

## The iteration loop

Every change that touches the geometry goes through all of these steps, in order. A change is
not done until the STLs, renders and docs in the commit match the code.

1. **Edit `atuin.py`.** For quick looks, run `.venv/bin/python atuin.py --resolution 0.8 --out <scratch dir>`.
   It takes seconds, and drafts must not overwrite the committed STLs.
2. **`make stl`**: regenerate the committed STLs at full resolution.
3. **`make check`**: it must end in `PASS`. Islands, a non-watertight mesh or more than one
   body are blockers. Fix the model; don't ship it with supports as the answer.
4. **`make renders`**, then look at every image. Look at the images, not just the exit code:
   framing, lighting and whether the change is visible. If a view no longer frames the model
   well, adjust its entry in `SHOTS` in `tools/render.py`.
5. **Update `README.md`** if anything it states changed:
   - the part sizes table (copy from the `wrote …` lines `make stl` prints);
   - the pocket and clearance numbers, and the peg/hole fit;
   - the options table (when `argparse` flags change);
   - print advice, such as where the steepest overhang is;
   - the gallery, when you add or remove a view.
6. **Version and changelog**: bump `__version__` (rules below) and add a `CHANGELOG.md`
   entry. Then `make stl` again, because the version is engraved under both parts. Then
   `make check` and `make renders` again, because the underside renders show the version.
7. **Commit** code, STLs, renders and docs together in one commit.
8. **Release** (see below), when the change should go out to printers.

Changes to docs or tooling alone (no change to the STL output) skip steps 2–4 and 6, and don't
get a version bump.

## Versioning

`__version__` in `atuin.py` is the single source of truth, and it follows semantic versioning
for printed parts:

- **MAJOR**: the base/Disc interface changes, so an old Disc won't fit a new base or the
  reverse. That covers `EL_R`, `EL_ANGLES`, `Z_TOP` and `EL_LEG_SHOW` (the seat height),
  `peg_d`, `peg_h`, `peg_clearance`, and the flat-seat shape.
- **MINOR**: a visible design change, a new feature, or a new default `jar_diameter`.
- **PATCH**: printability or mesh fixes with no intended visible change.

Release steps, after the commit is pushed:

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z great_atuin_base.stl great_atuin_disc_*.stl \
  --title "vX.Y.Z" --notes "<this version's CHANGELOG entry>"
```

Under `[Unreleased]` in `CHANGELOG.md`, list changes that are merged but not released. Move
them under the new version heading when you release.

## Design rules

Don't break these without a deliberate decision:

- **Build volume:** each part must fit the Bambu Lab P2S plate (256 × 256 × 256 mm). The
  base is about 239 × 238 mm, so there's little room to grow sideways.
- **Supports:** nothing should need them. No islands (enforced by `make check`). Overhangs
  steeper than about 55° should be bridges or small; the check prints those areas for
  information. Undersides are shaped for this:
  - 45° skirt under the shell rim;
  - flat-bottomed flippers and tail;
  - flat elephant bellies that bridge between legs and trunk;
  - a 45° throat under the head;
  - trunks curled back to rest on the shell.
- **Print orientation:** the base sits flat on its plastron and the Disc sits pocket side
  up. Text is engraved 0.6 mm into the faces on the bed, mirrored so it reads correctly
  when the part is turned over.
- **The base doesn't depend on the jar.** Only the Disc reads `Params` jar fields, so
  changing jar size never forces a base reprint.
- **Smallest features (0.4 mm nozzle):** about 0.8 mm for raised details. Engraving text
  should be at least 5.5 mm tall.
- **Jar fit:** the pocket is `jar_diameter + 2 × clearance` (default 1 mm per side), so glass
  jars that vary a little still fit.

## Modeling notes and gotchas

- **Coordinates:** mm, with x forward (the turtle's head), y left and z up. The bed is at
  z = 0. The Disc shares the base's x/y, and its seat is at `Z_TOP`.
- **SDF conventions:**
  - Fields are negative inside.
  - Every field must be exact or conservative (never larger than the true distance). The
    sparse mesher skips blocks whose centre is far from the surface, so an over-estimating
    field leaves holes in the mesh.
  - Use `bounded()` to skip expensive parts far from their bounding sphere.
  - Use `carve()` to cut detail only near the surface. Plain subtraction can leave hidden
    internal voids.
  - `flat()` squashes a shape vertically and stays conservative.
- **Mesher:**
  - The grid is offset by 0.37 voxel so flat faces (the bed, the elephants' backs) never
    sit exactly on samples. Samples exactly on a face produce clusters of near-duplicate
    vertices.
  - Vertices within 2e-4 mm are welded with a KD-tree. Otherwise they'd collide at STL
    float precision and make non-manifold edges.
  - `export()` drops any component under 1 mm³.
- **Workers use `spawn`:** run the generator as a script file. Piping code to `python -`
  fails in the worker processes. For one-off experiments, write a file that imports
  `atuin` inside `if __name__ == '__main__':`.
- **Text:** Luminari's glyph outlines touch themselves. `_bold_text()` grows the outlines,
  shrinks them back, and retries until no outline merely touches another. If a new string
  makes `make check` report a non-watertight mesh, look there first. Luminari is a macOS
  font; other systems fall back to a bold sans.
- **Renders:**
  - `tools/render.py` hard-codes `PEG_H` and `FLOOR` to match `Params`. Keep them in sync.
  - Cameras looking straight up need an explicit roll (`UP`), or the underside text comes
    out upside down at random.
  - Stand-ins aren't printed parts: the jar in the renders is a glass cylinder, and its
    height (`JAR_H`) is just for show.
- **Checks:** `tools/check.py` finds the Disc file from `--jar-diameter`. Pass the same
  `JAR` you generated with.

## Photos of real prints

Put them in `photos/`, named descriptively (for example `photos/v1.0.0-assembled.jpg`, with
the version that was printed). Add them to the README's Photos section. Don't replace
`renders/`: renders are regenerated, photos are records of real prints. Note any print
findings (sagging, fit, tolerances) in `CHANGELOG.md` under `[Unreleased]` so the next
version can fix them.
