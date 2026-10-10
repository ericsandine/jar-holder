# Changelog

Notable changes to the printable parts. Versions follow the rules in [AGENTS.md](AGENTS.md#versioning):
MAJOR means the base/Disc fit changed, MINOR a visible design change, PATCH printability fixes.

## [Unreleased]

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

[Unreleased]: https://github.com/ericsandine/jar-holder/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ericsandine/jar-holder/releases/tag/v1.0.0
