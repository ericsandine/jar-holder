# AGENTS.md

These are instructions for AI coding agents and humans iterating on this repo. Read them
before changing anything. The README is for people who want to print the stand. This file is
for people who change it.

## What's here

| Path | What it is |
|---|---|
| `atuin.py` | The whole model: parameters, SDF sculpting, mesher, CAD booleans and STL export. Has `__version__`. |
| `great_atuin_turtle.stl`, `great_atuin_elephant.stl`, `great_atuin_disc_<D>mm.stl` | Generated outputs: the turtle with four sockets, one elephant (printed four times) and the Disc. Committed so people can print without running anything. |
| `great_atuin_base.stl` | The turtle and four elephants fused, for a one-colour print with no assembly. |
| `great_atuin_<D>mm.3mf` | Generated Bambu Studio project: plate 1 the turtle, plate 2 the four elephants, plate 3 the Disc, one filament each. |
| `filaments.json` | Which filament each part uses: Bambu preset, colour code, hex and store link. It is the single source for the 3MF, the renders and the README's filament table. |
| `tools/make_3mf.py` | Builds the 3MF through the Bambu Studio command line. `--slice` also reports time and filament. |
| `tools/check.py` | Printability, fit, socket and 3MF checks. Exits 1 on failure. |
| `tools/render.py` | Blender script that writes `renders/*.png` for the README, in the filament colours. |
| `renders/` | Generated README images. Never edit them by hand. |
| `photos/` | Photos of real prints, added by hand. It doesn't exist until the first one is added. |
| `Makefile` | `setup`, `stl`, `disc`, `3mf`, `slice`, `check`, `renders`, `all` (`JAR=<mm>` changes the jar). |
| `CHANGELOG.md` | One entry per version ([Keep a Changelog](https://keepachangelog.com)). |

Setup: `make setup` creates `.venv` from `requirements.txt`. Renders need Blender 4.x on `PATH`.
The 3MF needs Bambu Studio (macOS path by default; set `BAMBU_STUDIO` otherwise).

## The iteration loop

Every change that touches the geometry goes through all of these steps, in order. A change is
not done until the STLs, renders and docs in the commit match the code.

1. **Edit `atuin.py`.** For quick looks, run `.venv/bin/python atuin.py --resolution 0.8 --out <scratch dir>`.
   It takes seconds, and drafts must not overwrite the committed STLs.
2. **`make stl`**: regenerate the committed STLs at full resolution, then **`make slice`**:
   rebuild the 3MF and get Bambu Studio's time and filament estimates.
3. **`make check`**: it must end in `PASS`. Islands, a non-watertight mesh, more than one
   body, an elephant that doesn't drop into its socket, or a 3MF whose filaments don't match
   `filaments.json` are all blockers. Fix the model; don't ship it with supports as the answer.
4. **`make renders`**, then look at every image. Look at the images, not just the exit code:
   framing, lighting and whether the change is visible. If a view no longer frames the model
   well, adjust its entry in `SHOTS` in `tools/render.py`.
5. **Update `README.md`** if anything it states changed:
   - the part sizes table (copy from the `wrote …` lines `make stl` prints) and the socket
     depths in the assembly steps;
   - the pocket and clearance numbers, and the peg/hole fit;
   - the options table (when `argparse` flags change);
   - print advice, such as where the steepest overhang is;
   - the filament table and the time/filament estimates (copy from `make slice`). When you
     change a colour, edit `filaments.json` and the README table together. Store links come
     from the product page's schema.org data, `"name": "<line> - <colour> (<code>) / Filament with spool"`,
     whose `"url"` carries the variant `?id=`;
   - the gallery, when you add or remove a view.
6. **Version and changelog**: bump `__version__` (rules below) and add a `CHANGELOG.md`
   entry. Then `make stl` and `make 3mf` again, because the version is engraved under both
   parts. Then `make check` and `make renders` again, because the underside renders show
   the version.
7. **Commit** code, STLs, renders and docs together in one commit.
8. **Release** (see below), when the change should go out to printers.

Changes to docs or tooling alone (no change to the STL output) skip steps 2–4 and 6, and don't
get a version bump.

## Versioning

`__version__` in `atuin.py` is the single source of truth, and it follows semantic versioning
for printed parts:

- **MAJOR**: an interface between printed parts changes, so an old part won't fit a new one.
  - Base/Disc: `EL_R`, `EL_ANGLES`, `Z_TOP` and `EL_LEG_SHOW` (the seat height), `peg_d`,
    `peg_h`, `peg_clearance`, and the flat-seat shape.
  - Turtle/elephants: `EL_SOLE_Z`, `EL_FIT`, `EL_LEG_R`, `LEGS`, `PLANT` and anything else
    that moves the elephants' buried feet. `EL_SOLE_Z` is computed from the shell, so a
    change to the dome can move it too.
- **MINOR**: a visible design change, a new feature, or a new default `jar_diameter`.
- **PATCH**: printability or mesh fixes with no intended visible change.

Release steps, after the commit is pushed:

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z great_atuin_*.stl great_atuin_*.3mf \
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
  - flat elephant bellies that bridge between the legs;
  - a 45° throat under the head;
  - trunks that end in a pillar (`PLANT`) down to the soles, hidden in the socket, so the
    curl isn't left hanging when an elephant prints on its own.
- **Print orientation:** the turtle sits flat on its plastron, the elephants stand on their
  soles, and the Disc sits pocket side up. Text is engraved 0.6 mm into the faces on the
  bed, mirrored so it reads correctly when the part is turned over.
- **One colour per plate.** Each piece prints alone in its own filament, so the project
  never needs an AMS, a prime tower or purging. Keep it that way.
- **All four elephants are one shape.** Their feet follow `_el_ground()`, the shell height
  averaged over all four positions and both sides, so any elephant fits any socket and the
  STL holds just one. Their soles share one plane, `EL_SOLE_Z`, at least `EL_SOCKET` below
  the shell, so every foot sits down in a socket.
- **The turtle and elephants don't depend on the jar.** Only the Disc reads `Params` jar
  fields, so changing jar size never forces a turtle or elephant reprint.
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
  - The legs and trunk pillar below the shell surface are joined with `np.minimum`, not
    `smin`, so the hidden parts don't bulge the visible legs.
- **Workers use `spawn`:** run the generator as a script file. Piping code to `python -`
  fails in the worker processes. For one-off experiments, write a file that imports
  `atuin` inside `if __name__ == '__main__':`.
- **Text:** Luminari's glyph outlines touch themselves. `_bold_text()` grows the outlines,
  shrinks them back, and retries until no outline merely touches another. If a new string
  makes `make check` report a non-watertight mesh, look there first. Luminari is a macOS
  font; other systems fall back to a bold sans.
- **Renders:**
  - `tools/render.py` imports `atuin` (Blender bundles numpy) for `placement()`, `Z_TOP`,
    `EL_SOLE_Z` and `Params`, and places four copies of the elephant STL.
  - Cameras looking straight up need an explicit roll (`UP`), or the underside text comes
    out upside down at random.
  - Stand-ins aren't printed parts: the jar in the renders is a glass cylinder, and its
    height (`JAR_H`) is just for show.
- **Checks:** `tools/check.py` finds the Disc file from `--jar-diameter`. Pass the same
  `JAR` you generated with. `--dir <folder>` checks a draft build instead of the repo.
- **Sockets:** each one is the part of a placed elephant that is inside the turtle
  (`elephant ^ turtle`), projected to 2D, grown by `EL_FIT`, closed by 0.6 mm (so no thin
  slivers of shell are left between the trunk and the front feet), simplified, and
  extruded up from `EL_SOLE_Z`. Clipper's offsets and `simplify()` can leave zero-width
  spikes in the outline, and an extruded spike cuts a crack with no thickness: `make check`
  then reports the turtle as not watertight, more than one body, and with islands.
  `_despike()` removes them; look there first if those failures come back.
- **`placement(angle)`** is the one transform from the elephant STL to its place on the
  turtle. `build_base`, `tools/check.py` and `tools/render.py` all use it.
- **Bambu Studio command line (`tools/make_3mf.py`):** we write a plain 3MF with Bambu's
  `model_settings.config` (parts, filaments, plates). The CLI then loads it and re-saves it as
  a native project. Things it does not do on its own:
  - **Follow `inherits` or the per-printer G-code templates.** Without them you get a
    200 mm bed and generic start G-code that is wrong for the P2S. `resolved_profile()`
    merges both. The result's machine G-code must match what the GUI saves; compare it
    against a P2S project saved by the GUI if in doubt.
  - **Compute purge volumes.** It needs an N × N `flush_volumes_matrix`, which we take from
    Bambu's measured `flush/flush_data_standard.txt` (nearest colour pair).
  - **Keep our layout.** Pass `--arrange 0`, or it rearranges the plates and pushes the base
    off. Plates sit on a grid 1.2 bed-widths apart, `ceil(sqrt(n))` columns wide, with rows
    going towards −y; with three plates, plate 3 is below plate 1. An object off its plate
    fails slicing with "One of the plate is empty or has no object fully inside it".
  - **Place the prime tower sensibly** (only used if a plate ever gets two colours). The
    default (15, 220) collides with a flipper, so it goes at (218, 200), clear of the P2S's
    reserved back strip (x 153–216, y ≥ 235).
  - **Keep `make slice` passing.** It slices every plate; if it fails, `result.json` in the
    output folder has the reason.

## Photos of real prints

Put them in `photos/`, named descriptively (for example `photos/v1.0.0-assembled.jpg`, with
the version that was printed). Add them to the README's Photos section. Don't replace
`renders/`: renders are regenerated, photos are records of real prints. Note any print
findings (sagging, fit, tolerances) in `CHANGELOG.md` under `[Unreleased]` so the next
version can fix them.
