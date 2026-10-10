#!/usr/bin/env python3
"""Printability and fit checks for the generated STLs; exits 1 if anything fails.

    .venv/bin/python tools/check.py                      # default jar diameter
    .venv/bin/python tools/check.py --jar-diameter 153.5

Checks each part is a single watertight solid that fits the build plate, slices it
at 0.2 mm like a printer to find islands (regions that would start in mid-air),
summarises steep overhangs, and measures the peg / hole / pocket fit.
"""
import argparse
import os
import sys

import numpy as np
import trimesh
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import atuin  # noqa: E402

BED = 256.0          # Bambu Lab P2S build plate, mm (X, Y and Z)
LAYER = 0.2


def islands(m):
    """Regions of a 0.2 mm slice that touch nothing in the slice below."""
    zs = np.arange(LAYER / 2, m.bounds[1][2], LAYER)
    found, prev = [], None
    for z, sec in zip(zs, m.section_multiplane([0, 0, 0], [0, 0, 1], zs)):
        polys = [] if sec is None else list(sec.polygons_full)
        if prev is not None:
            for p in polys:
                if p.area > 0.05 and p.intersection(prev.buffer(0.05)).area < 1e-3:
                    found.append((z, p.area, p.centroid.x, p.centroid.y))
        prev = unary_union(polys) if polys else None
    return found


def overhang_area(m, deg):
    """mm^2 of surface facing down more steeply than `deg` from vertical, off the bed."""
    steep = (m.face_normals[:, 2] < -np.sin(np.radians(deg))) & (m.triangles_center[:, 2] > 0.4)
    return m.area_faces[steep].sum()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jar-diameter', type=atuin._length, default=atuin.Params.jar_diameter)
    a = ap.parse_args()
    P = atuin.Params(jar_diameter=a.jar_diameter)
    rp, R, H = atuin.disc_dims(P)
    paths = {'base': os.path.join(ROOT, 'great_atuin_base.stl'),
             'disc': os.path.join(ROOT, f'great_atuin_disc_{P.jar_diameter:.1f}mm.stl')}
    failures = []

    def check(ok, msg):
        print(('  ok    ' if ok else '  FAIL  ') + msg)
        if not ok:
            failures.append(msg)

    meshes = {}
    for name, path in paths.items():
        print(f'{os.path.basename(path)}')
        if not os.path.exists(path):
            check(False, 'missing (run: make stl)')
            continue
        m = meshes[name] = trimesh.load(path)
        size = m.bounds[1] - m.bounds[0]
        check(m.is_watertight and m.is_winding_consistent, 'watertight, consistent winding')
        check(len(m.split(only_watertight=False)) == 1, 'a single solid body')
        check(abs(m.bounds[0][2]) < 0.01, f'sits on the bed (min z {m.bounds[0][2]:.3f})')
        check(size[0] <= BED and size[1] <= BED and size[2] <= BED,
              f'fits the {BED:.0f} mm build plate ({size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm)')
        isl = islands(m)
        check(not isl, f'no islands in {LAYER} mm slices' +
              ''.join(f'\n          z={z:.1f} {ar:.2f} mm2 at ({x:.1f}, {y:.1f})' for z, ar, x, y in isl[:10]))
        print(f'  info  overhang area: >55 deg {overhang_area(m, 55):.0f} mm2, '
              f'>65 deg {overhang_area(m, 65):.0f} mm2 (mostly bridged ceilings; see AGENTS.md)')

    if len(meshes) == 2:
        print('fit')
        b, d = meshes['base'].vertices, meshes['disc'].vertices
        z = atuin.Z_TOP
        dist = np.min([np.hypot(b[:, 0] - e.o[0], b[:, 1] - e.o[1]) for e in atuin.ELEPHANTS], axis=0)
        check(abs(b[dist > P.peg_d / 2 + 0.2, 2].max() - z) < 0.01,
              f'nothing but the pegs rises above the disc seat at z = {z:.2f}')
        pr = P.peg_d / 2
        for e, name in zip(atuin.ELEPHANTS, atuin.EL_NAMES):
            rb = np.hypot(b[:, 0] - e.o[0], b[:, 1] - e.o[1])
            peg = (rb < pr + 0.1) & (b[:, 2] > z + 0.5)
            rd = np.hypot(d[:, 0] - e.o[0], d[:, 1] - e.o[1])
            hole = (rd < pr + P.peg_clearance + 0.1) & (d[:, 2] > 0.6)
            off = np.hypot(*(b[peg, :2].mean(0) - d[hole, :2].mean(0)))
            ok = (peg.any() and hole.any() and off < 0.05
                  and d[hole, 2].max() > b[peg, 2].max() - z + 0.3
                  and 2 * rd[hole].min() > 2 * rb[peg].max() + 0.3)
            check(ok, f'{name:13s} peg {2 * rb[peg].max():.2f} x {b[peg, 2].max() - z:.2f} mm in hole '
                      f'{2 * rd[hole].min():.2f} x {d[hole, 2].max():.2f} mm, centres {off:.3f} mm apart')
        r = np.hypot(d[:, 0], d[:, 1])
        wall = (d[:, 2] >= P.floor - 0.01) & (d[:, 2] < H - 1.0) & (np.abs(r - rp) < 0.5)
        check(wall.any() and abs(2 * r[wall].mean() - 2 * rp) < 0.05,
              f'pocket {2 * r[wall].mean():.2f} mm across, {P.pocket_depth:.0f} mm deep, '
              f'for a {P.jar_diameter:.1f} mm jar')

    print('PASS' if not failures else f'{len(failures)} check(s) FAILED')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
