# Changelog

Notable changes to the printable parts. Versions follow the rules in [AGENTS.md](AGENTS.md#versioning):
MAJOR means the base/Disc fit changed, MINOR a visible design change, PATCH printability fixes.

## [Unreleased]

## [1.1.0] - 2026-10-10

### Added
- **Two-colour base.** `great_atuin_base_turtle.stl` and `great_atuin_base_elephants.stl`
  split the base exactly, so it can print with grey elephants on a green turtle.
- **Ready-to-print Bambu Studio project, `great_atuin_152.4mm.3mf`.**
  - Plate 1 is the two-colour base; plate 2 is the Disc.
  - Filaments, colours, purge volumes and the prime tower position are preset for a P2S
    with an AMS.
  - Built by `tools/make_3mf.py` through the Bambu Studio command line, and verified by
    slicing.
- **`filaments.json`, the recommended filaments with store links:**
  - turtle: PLA Galaxy Green (13503);
  - elephants: PLA Matte Ash Gray (11102);
  - Disc: PLA Matte Marine Blue (11600).
- **`make 3mf` and `make slice`.** The slice gives Bambu Studio's estimates: base about
  7 h, 271 g green + 62 g grey, 59 colour changes; Disc about 2.5 h, 118 g blue.
- **Checks** for the split (watertight, no overlap, adds up to the base) and for the
  project's filament assignments.

### Changed
- Renders now show each part in its filament colour, including the Galaxy sparkle.
- The version engraved under both parts reads v1.1.0. The geometry is otherwise unchanged
  from 1.0.0, and the base and Disc still fit across versions.

## [1.0.0] - 2026-10-10

### Added
- **Base: Great A'Tuin.**
  - Scuted shell (vertebral, costal and marginal scutes) pocked with meteor craters.
  - Heavy-lidded "sea-sized" eyes and a hooked beak.
  - Swept-back flippers lying flat on the bed.
- **Base: the World Elephants.** Berilia, Tubul, Great T'Phon and Jerakeen stand on the
  diagonals with curled trunks. Each has a flat seat and a 7 × 4 mm peg for the Disc.
- **Disc.** A 12 mm deep jar pocket with 1 mm clearance per side; the default is for a 6 in
  (152.4 mm) jar. The Rimfall pours over rock strata at the edge. 7.6 mm chamfered peg holes
  are underneath.
- **Engraving.** Under the base: *GREAT A'TUIN · Chelys galactica · THE TURTLE MOVES*. Under
  the Disc: the elephants' names. Both parts carry the version number.
- **Generator.** `atuin.py` takes `--jar-diameter` (mm or inches), `--clearance`,
  `--pocket-depth`, `--parts` and `--resolution`.
- **Tooling.**
  - `tools/check.py`: watertight and single-body checks, build-plate fit, island detection
    on 0.2 mm slices, overhang summary, and peg/hole/pocket measurements.
  - `tools/render.py`: Blender renders for the README.
  - A `Makefile`.

[Unreleased]: https://github.com/ericsandine/jar-holder/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ericsandine/jar-holder/releases/tag/v1.1.0
[1.0.0]: https://github.com/ericsandine/jar-holder/releases/tag/v1.0.0
