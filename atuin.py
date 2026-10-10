#!/usr/bin/env python3
"""Great A'Tuin jar stand: parametric generator for two printable STLs.

  great_atuin_base.stl       Great A'Tuin swimming through space, her shell pocked
                             with meteor craters, carrying Berilia, Tubul,
                             Great T'Phon and Jerakeen on her back.
  great_atuin_disc_<D>mm.stl The Disc. The jar sits down in a pocket in its top and
                             the Rimfall pours off its edge. Holes underneath key
                             onto pegs on the elephants' backs.

Only the disc depends on the jar, so once you have an exact measurement you only
need to regenerate and reprint the disc:

    python atuin.py                                   # 6 in (152.4 mm) jar
    python atuin.py --jar-diameter 153.5              # millimetres
    python atuin.py --jar-diameter 6.04in --parts disc

Organic shapes are signed distance fields meshed with marching cubes. The jar
pocket, pegs, peg holes and engraved text are exact CAD booleans (manifold3d).
Setup and the rest of the workflow (checks, renders, versioning): see README.md
and AGENTS.md.
"""
import argparse
import math
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass

import numpy as np

# Semantic version of the printable geometry, engraved under both parts.
# MAJOR: base/disc interface changed (old discs no longer fit new bases).
# MINOR: visible design change or new default jar. PATCH: printability/mesh fixes.
__version__ = '1.0.0'


@dataclass
class Params:
    jar_diameter: float = 152.4   # outside diameter of the jar's base, mm
    clearance: float = 1.0        # gap per side between the jar and the pocket wall
    pocket_depth: float = 12.0    # how far the jar sits down into the disc
    floor: float = 8.0            # disc thickness under the jar
    rim_width: float = 10.0       # disc material outside the pocket (wall + Rimsea)
    peg_d: float = 7.0
    peg_h: float = 4.0
    peg_clearance: float = 0.3    # radial play in the disc's peg holes
    resolution: float = 0.35      # marching-cubes voxel size, mm


# --------------------------------------------------------------------------- SDF
# Every primitive takes points p of shape (N, 3) and returns signed distances,
# negative inside. They are exact or conservative (never larger than the true
# distance), which the sparse mesher relies on when it skips empty space.

def norm(v):
    return np.sqrt(np.einsum('...i,...i->...', v, v))


def sphere(p, c, r):
    return norm(p - np.asarray(c, float)) - r


def ellipsoid(p, c, r):
    r = np.asarray(r, float)
    q = (p - np.asarray(c, float)) / r
    k0 = norm(q)
    k1 = norm(q / r)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def round_cone(p, a, b, r1, r2):
    """Cone with spherical caps: radius r1 at a, r2 at b (Inigo Quilez, exact)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    w = pa * l2 - y[:, None] * ba
    x2 = np.einsum('ij,ij->i', w, w)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d_side = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    d_b = np.sqrt(x2 + z2) * il2 - r2
    d_a = np.sqrt(x2 + y2) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d_b,
                    np.where(np.sign(y) * a2 * y2 < k, d_a, d_side))


def tube(p, pts):
    """Chain of round cones through [(x, y, z, r), ...]."""
    d = None
    for (x0, y0, z0, r0), (x1, y1, z1, r1) in zip(pts[:-1], pts[1:]):
        di = round_cone(p, (x0, y0, z0), (x1, y1, z1), r0, r1)
        d = di if d is None else np.minimum(d, di)
    return d


def torus(p, c, axis, R, r):
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    d = p - np.asarray(c, float)
    h = d @ axis
    radial = norm(d - h[:, None] * axis)
    return np.sqrt((radial - R) ** 2 + h ** 2) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def carve(d, tool, depth):
    """Subtract `tool`, but only within `depth` of the surface, so no hidden voids."""
    return np.maximum(d, -np.maximum(tool, -(d + depth)))


def bounded(p, center, radius, fn, margin=8.0):
    """fn(p) near its bounding sphere; the cheaper (smaller) sphere distance elsewhere."""
    out = norm(p - np.asarray(center, float)) - radius
    m = out < margin
    if m.any():
        out[m] = fn(p[m])
    return out


def flat(fn, s, p):
    """fn squashed vertically by factor s (conservative)."""
    q = p.copy()
    q[:, 2] *= s
    return fn(q) / s


# ------------------------------------------------------------- Great A'Tuin
# mm; x = forward (head), y = left, z = up, ground at z = 0.

SHELL_A, SHELL_B = 86.0, 76.0   # half length / half width of the carapace
SHELL_C = 48.0                  # dome height above the rim
SHELL_RIM_Z = 14.0              # rim height
SHELL_N = 2.6                   # dome profile exponent: 2 = ellipsoid, higher = flatter top
SHELL_EGG = 0.06                # a little wider toward the front
SKIRT_TOP = 12.5                # 45-degree skirt under the rim (prints without supports)


def _shell_r(x, y):
    u = np.clip(x / SHELL_A, -1.5, 1.5)
    return np.hypot(x / SHELL_A, y / ((1.0 + SHELL_EGG * u) * SHELL_B))


def shell_top_z(x, y):
    r = _shell_r(x, y)
    return SHELL_RIM_Z + SHELL_C * np.clip(1.0 - r ** SHELL_N, 0.0, None) ** (1.0 / SHELL_N)


def dome(p):
    x, y, z = p.T
    w = np.abs(z - SHELL_RIM_Z) / SHELL_C
    f = (_shell_r(x, y) ** SHELL_N + w ** SHELL_N) ** (1.0 / SHELL_N) - 1.0
    return f * SHELL_C


def skirt(p):
    """45-degree cone that undercuts the rim, so the shell prints without supports."""
    x, y, z = p.T
    inset = np.clip(SKIRT_TOP - z, 0.0, None)
    a = SHELL_A - inset
    b = SHELL_B - inset
    u = np.clip(x / SHELL_A, -1.5, 1.5)
    r = np.hypot(x / a, y / ((1.0 + SHELL_EGG * u) * b))
    return (r - 1.0) * np.minimum(a, b) / math.sqrt(2.0)


def _on_shell(u, v):
    x = u * SHELL_A
    y = v * SHELL_B * (1.0 + SHELL_EGG * u)
    return np.array([x, y, float(shell_top_z(x, y))])


def _shell_normal(s):
    e = 0.01
    g = np.array([(dome((s + dv)[None]) - dome((s - dv)[None]))[0]
                  for dv in np.eye(3) * e])
    return g / np.linalg.norm(g)


def _scute_seeds():
    uv = [(u, 0.0) for u in (0.66, 0.34, 0.02, -0.30, -0.60)]                  # vertebrals
    for s in (1, -1):
        uv += [(0.50, 0.50 * s), (0.18, 0.60 * s), (-0.16, 0.60 * s), (-0.48, 0.50 * s)]  # costals
    return np.array([_on_shell(u, v) for u, v in uv])


SCUTE_SEEDS = _scute_seeds()
MARGINAL_Z = SHELL_RIM_Z + 0.30 * SHELL_C   # top edge of the band of marginal scutes
N_MARGINALS = 22
GROOVE_HALF_W, GROOVE_DEPTH = 0.85, 1.1


def scute_grooves(p, d):
    m = (np.abs(d) < 2.0) & (p[:, 2] > SHELL_RIM_Z + 1.5)
    if not m.any():
        return d
    q, dq = p[m], d[m]
    x, y, z = q.T
    # vertebral and costal scutes: Voronoi cells of the seeds, groove on the cell borders
    d2 = ((q[:, None, :] - SCUTE_SEEDS[None]) ** 2).sum(-1)
    two = np.argpartition(d2, 1, axis=1)[:, :2]
    rows = np.arange(len(q))
    da, db = d2[rows, two[:, 0]], d2[rows, two[:, 1]]
    i = np.where(da <= db, two[:, 0], two[:, 1])
    j = np.where(da <= db, two[:, 1], two[:, 0])
    gap = norm(SCUTE_SEEDS[j] - SCUTE_SEEDS[i])
    upper = (d2[rows, j] - d2[rows, i]) / (2.0 * gap)
    # marginal scutes: a band round the rim, split by radial lines
    b_eff = SHELL_B * (1.0 + SHELL_EGG * np.clip(x / SHELL_A, -1.5, 1.5))
    step = 2 * math.pi / N_MARGINALS
    th = np.arctan2(y / b_eff, x / SHELL_A)
    tk = (np.floor(th / step) + 0.5) * step          # nearest division (cells centred front/back)
    psi = np.arctan2(b_eff * np.sin(tk), SHELL_A * np.cos(tk))
    radial = np.abs(-x * np.sin(psi) + y * np.cos(psi))
    ring = np.abs(z - MARGINAL_Z)
    g = np.where(z > MARGINAL_Z, np.minimum(upper, ring), np.minimum(radial, ring))
    tool = g - GROOVE_HALF_W * (1.0 + dq / GROOVE_DEPTH)   # V-shaped groove
    out = d.copy()
    out[m] = carve(dq, tool, GROOVE_DEPTH + 0.2)
    return out


# "his huge and ancient shell pocked with meteor craters" -- (u, v, radius)
CRATER_SPEC = [(0.0, 0.0, 6.0), (0.60, 0.06, 5.0), (0.84, -0.22, 3.5), (0.05, 0.64, 7.0),
               (-0.25, 0.86, 4.0), (-0.64, -0.05, 6.0), (-0.50, 0.12, 3.2), (0.12, -0.70, 5.0),
               (-0.05, -0.45, 3.5), (0.78, 0.45, 3.0), (-0.70, -0.55, 4.5)]
CRATERS = [(s, _shell_normal(s), r) for s, r in
           ((_on_shell(u, v), r) for u, v, r in CRATER_SPEC)]


def craters(p, d):
    for s, n, R in CRATERS:
        ring_c = s + n * 0.05 * R
        rim = bounded(p, s, 1.3 * R, lambda q: torus(q, ring_c, n, 0.85 * R, 0.22 * R))
        d = smin(d, rim, 0.6)
        bowl_c = s + n * 0.55 * R
        bowl = bounded(p, bowl_c, R, lambda q: sphere(q, bowl_c, R))
        d = smax(d, -bowl, 0.6)
    return d


# Head and neck. "sea-sized eyes crusted with rheum"
HEAD_C = np.array([SHELL_A + 24.0, 0.0, 30.0])
HEAD_PITCH = math.radians(20.0)   # nose up
NECK = ((SHELL_A - 22, 0, 20), (SHELL_A + 12, 0, 27), 18.0, 12.5)
THROAT = ((SHELL_A - 8, 0, -2), (SHELL_A + 18, 0, 21), 12.0, 8.5)  # ~45 deg underside to the chin


def _head_local(p):
    q = p - HEAD_C
    c, s = math.cos(HEAD_PITCH), math.sin(HEAD_PITCH)
    return np.stack([c * q[:, 0] + s * q[:, 2], q[:, 1], -s * q[:, 0] + c * q[:, 2]], 1)


SKULL = (19.0, 14.0, 12.5)
EYE_C, EYE_R = (8.5, 10.4, 3.6), 5.0


def _pupil_centers():
    out = []
    for s in (1, -1):
        eye = np.array([EYE_C[0], EYE_C[1] * s, EYE_C[2]])
        g = eye / np.array(SKULL) ** 2
        out.append(eye + g / np.linalg.norm(g) * (EYE_R + 0.5))
    return out


PUPILS = _pupil_centers()


def head(p):
    q = _head_local(p)
    d = ellipsoid(q, (0, 0, 0), SKULL)
    d = smin(d, ellipsoid(q, (7, 0, -6.5), (15, 11.5, 6)), 3.0)               # jaw
    d = smin(d, round_cone(q, (10, 0, -1), (21, 0, -1.5), 9.0, 5.5), 4.0)    # beak
    d = smin(d, round_cone(q, (21, 0, -1.5), (25, 0, -5.0), 5.0, 2.2), 1.5)
    for s in (1, -1):
        d = smin(d, sphere(q, (EYE_C[0], EYE_C[1] * s, EYE_C[2]), EYE_R), 1.0)   # sea-sized eye
        d = smin(d, ellipsoid(q, (8.0, 10.8 * s, 7.0), (6.8, 4.6, 2.6)), 1.2)    # heavy lid
        d = smin(d, ellipsoid(q, (9.0, 10.6 * s, 0.2), (5.5, 4.3, 2.2)), 1.0)    # rheumy bag
        d = smax(d, -sphere(q, (22.5, 2.2 * s, 2.0), 1.0), 0.3)                  # nostril
    for c in PUPILS:
        d = smax(d, -sphere(q, c, 1.8), 0.3)
    mouth_z = -4.6 - 0.28 * np.maximum(q[:, 0] - 15.0, 0.0)   # dips into the hooked beak
    slit = np.maximum(np.abs(q[:, 2] - mouth_z) - 0.55, 1.0 - q[:, 0])
    return carve(d, slit, 1.3)


def head_and_neck(p):
    d = smin(round_cone(p, *NECK), round_cone(p, *THROAT), 6.0)
    d = smin(d, head(p), 5.0)
    a, b = np.array(NECK[0], float), np.array(NECK[1], float)
    for t in (0.55, 0.66, 0.77, 0.88):   # ancient wrinkles
        r = NECK[2] + (NECK[3] - NECK[2]) * t
        d = carve(d, torus(p, a + (b - a) * t, b - a, r + 0.4, 0.8), 1.0)
    return d


# Flippers lie flat on the ground: (x, y, r) of the left side, mirrored for the right.
# The chains are centred on the ground, so the bed cuts them at their widest:
# flat bottoms, no curled-up edges to print in mid-air.
FLAT_K = 2.2
FRONT_FLIPPER = [(36, 44, 14), (54, 74, 13.5), (48, 96, 11), (32, 109, 7.5), (14, 115, 4)]
REAR_FLIPPER = [(-46, 42, 12), (-62, 56, 11.5), (-76, 67, 11), (-88, 77, 8), (-95, 82, 4)]
TAIL = [(-78, 0, 9), (-92, 0, 5), (-99, 0, 2.5)]


def _ground_chain(pts, s):
    return [(x, y, 0.4 * s, r) for x, y, r in pts]


def front_flipper(p):
    return flat(lambda q: tube(q, _ground_chain(FRONT_FLIPPER, FLAT_K)), FLAT_K, p)


def rear_flipper(p):
    return flat(lambda q: tube(q, _ground_chain(REAR_FLIPPER, FLAT_K)), FLAT_K, p)


def tail(p):
    return flat(lambda q: tube(q, _ground_chain(TAIL, 1.0)), 1.0, p)


# The four World Elephants, facing outward on the diagonals.
EL_R = 40.0                # distance from shell centre to each elephant's back
EL_LEG_SHOW = 11.0         # leg visible under the belly (at the body centre)
EL_NAMES = ("BERILIA", "TUBUL", "GREAT T'PHON", "JERAKEEN")
EL_ANGLES = (45.0, 135.0, 225.0, 315.0)
LEGS = ((10.5, 8.0), (10.5, -8.0), (-10.5, 8.0), (-10.5, -8.0))


class Elephant:
    def __init__(self, angle_deg, z_top):
        t = math.radians(angle_deg)
        self.c, self.s = math.cos(t), math.sin(t)
        self.o = np.array([EL_R * self.c, EL_R * self.s, z_top])
        self.legs = [(lx, ly, self.ground(lx, ly)) for lx, ly in LEGS]
        self.toes = [(lx + 5.4, ly + o, self.ground(lx + 5.4, ly + o) + 1.0)
                     for lx, ly in LEGS for o in (-2.4, 0.0, 2.4)]
        # trunk hangs down and curls back to rest between the front feet
        tip = min(self.ground(16.0, 0) + 2.7, -37.5)
        self.trunk = [(27.5, 0, -19, 5.6), (30.5, 0, -25.5, 4.8), (28.0, 0, -31.5, 4.2),
                      (21.5, 0, -36.5, 3.7), (16.0, 0, tip, 3.2)]
        bc = self.world_xy(7.0, 0.0)
        self.bound_c = (bc[0], bc[1], z_top - 25.0)
        self.bound_r = 46.0

    def world_xy(self, lx, ly):
        return (self.o[0] + lx * self.c - ly * self.s, self.o[1] + lx * self.s + ly * self.c)

    def ground(self, lx, ly):
        return float(shell_top_z(*self.world_xy(lx, ly))) - self.o[2]

    def sdf(self, p):
        d0 = p - self.o
        q = np.stack([d0[:, 0] * self.c + d0[:, 1] * self.s,
                      -d0[:, 0] * self.s + d0[:, 1] * self.c, d0[:, 2]], 1)
        d = ellipsoid(q, (0, 0, -10), (21, 14, 14))                          # body
        d = smin(d, ellipsoid(q, (19.5, 0, -13), (11, 11, 12.5)), 5.0)      # head
        d = smin(d, sphere(q, (21, 0, -8), 8.0), 3.0)                       # forehead
        ear_patch = (np.hypot((q[:, 0] - 12.5) / 9.5, (q[:, 2] + 12.5) / 11.5) - 1.0) * 9.5
        ear = np.maximum(np.maximum(d - 3.0, ear_patch), 6.0 - np.abs(q[:, 1]))
        d = smin(d, ear, 0.5)
        # flat belly: it prints as a bridge between the legs instead of starting in mid-air
        d = smax(d, -(q[:, 2] + 22.0), 1.5)
        for lx, ly, g in self.legs:
            d = smin(d, round_cone(q, (lx, ly, -14), (lx, ly, g - 3), 5.3, 6.0), 4.0)
        for toe in self.toes:
            d = smin(d, sphere(q, toe, 1.25), 0.4)
        d = smin(d, tube(q, self.trunk), 3.0)
        for s in (1, -1):
            d = smin(d, round_cone(q, (26, 5.5 * s, -20), (32.5, 8.5 * s, -13.5), 1.9, 0.9), 1.0)
            d = smin(d, sphere(q, (26.5, 7.6 * s, -9.5), 1.6), 0.4)         # eye
        return smax(d, q[:, 2], 1.5)    # flat top for the Disc to rest on


Z_TOP = round(max(float(shell_top_z(EL_R * math.cos(math.radians(a)), EL_R * math.sin(math.radians(a))))
                  for a in EL_ANGLES) + 24.0 + EL_LEG_SHOW, 2)
ELEPHANTS = [Elephant(a, Z_TOP) for a in EL_ANGLES]

FRONT_BOUND = ((38.0, 76.0, 4.0), 56.0)
REAR_BOUND = ((-66.0, 58.0, 4.0), 47.0)
TAIL_BOUND = ((-88.0, 0.0, 4.0), 22.0)
HEAD_BOUND = ((SHELL_A + 8.0, 0.0, 22.0), 48.0)


def base_sdf(p):
    d = np.maximum(dome(p), skirt(p))
    d = scute_grooves(p, d)
    d = craters(p, d)
    d = smin(d, bounded(p, *HEAD_BOUND, head_and_neck), 4.0)
    q = p.copy()
    q[:, 1] = np.abs(q[:, 1])
    d = smin(d, bounded(q, *FRONT_BOUND, front_flipper), 5.0)
    d = smin(d, bounded(q, *REAR_BOUND, rear_flipper), 5.0)
    d = smin(d, bounded(p, *TAIL_BOUND, tail), 4.0)
    for el in ELEPHANTS:
        d = smin(d, bounded(p, el.bound_c, el.bound_r, el.sdf), 3.0)
    return np.maximum(d, -p[:, 2])


BASE_BOUNDS = ((-112.0, -128.0, -1.0), (146.0, 128.0, Z_TOP + 2.0))


# ------------------------------------------------------------------- the Disc

def disc_dims(P):
    r_pocket = P.jar_diameter / 2 + P.clearance
    return r_pocket, r_pocket + P.rim_width, P.floor + P.pocket_depth


def _wave(th, terms):
    return sum(a * np.sin(f * th + ph) for f, a, ph in terms)


# (frequency, amplitude, phase) of the Rimfall's ragged lower edge and its streaks
RIMFALL_EDGE = ((3, 0.22, 0.4), (5, 0.15, 2.1), (11, 0.10, 4.0), (19, 0.08, 1.3), (37, 0.05, 5.2))
RIMFALL_STREAKS = ((53, 0.40, 0.0), (89, 0.25, 1.9), (157, 0.15, 3.3))
EDGE_R = 2.5


def disc_sdf(p, P):
    _, R, H = disc_dims(P)
    x, y, z = p.T
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    qx, qz = r - (R - EDGE_R), z - (H - EDGE_R)                 # rounded top edge
    body = (np.hypot(np.maximum(qx, 0), np.maximum(qz, 0))
            + np.minimum(np.maximum(qx, qz), 0) - EDGE_R)
    body = np.maximum(body, -z)
    # rock strata on the edge of the world, showing below the falling water
    rock = body
    for zf, ph in ((0.22, 0.0), (0.42, 1.7)):
        zg = H * zf + 0.8 * np.sin(3 * th + ph) + 0.4 * np.sin(11 * th + 2 * ph)
        rock = carve(rock, np.maximum(np.abs(z - zg) - 0.45, (R - 2.0) - r), 0.5)
    # the Rimfall: the Rimsea pours over the edge as a streaked curtain of water
    z_end = H * (0.42 + _wave(th + 0.3 * np.sin(7 * th), RIMFALL_EDGE))
    thick = 0.95 + _wave(th + 0.05 * np.sin(13 * th), RIMFALL_STREAKS)
    water = np.maximum(np.maximum(body - thick, z_end - z), (R - 3.5) - r)
    return np.maximum(smin(rock, water, 0.5), -z)


# ---------------------------------------------------------------------- mesher

_W = {}


def _sdf_for(part, P):
    if part == 'base':
        return base_sdf
    return lambda p: disc_sdf(p, P)


def _init_worker(part, params):
    _W['sdf'] = _sdf_for(part, Params(**params))


def _mesh_block(task):
    from skimage.measure import marching_cubes
    i0, n, h, lo = task
    axes = [lo[a] + (i0[a] + np.arange(n + 1)) * h for a in range(3)]
    g = np.stack(np.meshgrid(*axes, indexing='ij'), -1).reshape(-1, 3)
    vol = _W['sdf'](g).reshape(n + 1, n + 1, n + 1)
    if vol.min() > 0 or vol.max() < 0:
        return None
    vol[vol == 0] = 1e-9
    verts, faces, _, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    return verts + np.array([a[0] for a in axes]), faces


def mesh_sdf(part, P, bounds, h, block=24):
    # offset the grid so flat faces (the bed, the elephants' backs) never land on samples
    lo, hi = np.array(bounds[0], float) - 0.37 * h, np.array(bounds[1], float)
    nb = np.ceil((hi - lo) / h / block).astype(int)
    bi = np.stack(np.meshgrid(*[np.arange(k) for k in nb], indexing='ij'), -1).reshape(-1, 3)
    centers = lo + (bi * block + block / 2) * h
    dc = _sdf_for(part, P)(centers)
    active = bi[np.abs(dc) < 1.6 * math.sqrt(3) * block * h / 2 + 2 * h]
    tasks = [(tuple(int(v) for v in b * block), block, h, tuple(lo)) for b in active]
    print(f'  {part}: {len(tasks)} of {len(bi)} blocks near the surface', flush=True)
    ctx = mp.get_context('spawn')
    with ProcessPoolExecutor(os.cpu_count(), mp_context=ctx, initializer=_init_worker,
                             initargs=(part, asdict(P))) as ex:
        results = [r for r in ex.map(_mesh_block, tasks, chunksize=8) if r is not None]
    verts = np.concatenate([v for v, _ in results])
    offsets = np.cumsum([0] + [len(v) for v, _ in results[:-1]])
    faces = np.concatenate([f + o for (_, f), o in zip(results, offsets)])
    # weld the blocks together, and fuse the near-duplicate vertices marching cubes makes
    # where the surface grazes a sample (they would collide at STL float precision)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    pairs = cKDTree(verts).query_pairs(2e-4, output_type='ndarray')
    n = len(verts)
    _, label = connected_components(
        coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)), directed=False)
    _, first = np.unique(label, return_index=True)
    verts, faces = verts[first], label[faces]
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2])
                  & (faces[:, 0] != faces[:, 2])]
    _, inv, cnt = np.unique(np.sort(faces, axis=1), axis=0, return_inverse=True, return_counts=True)
    return verts, faces[cnt[inv.reshape(-1)] == 1]    # collapsed slivers come in cancelling pairs


def to_manifold(verts, faces):
    from manifold3d import Manifold, Mesh
    m = Manifold(Mesh(vert_properties=np.ascontiguousarray(verts, np.float32),
                      tri_verts=np.ascontiguousarray(faces, np.uint32)))
    if m.volume() < 0 or m.is_empty():
        m = Manifold(Mesh(vert_properties=np.ascontiguousarray(verts, np.float32),
                          tri_verts=np.ascontiguousarray(faces[:, ::-1], np.uint32)))
    if m.is_empty():
        raise RuntimeError(f'mesh is not watertight: {m.status()}')
    return m


def _pinched(m):
    """True if the solid has edges shared by more than two faces once written to STL."""
    mesh = m.to_mesh()
    _, ids = np.unique(np.round(mesh.vert_properties[:, :3], 5), axis=0, return_inverse=True)
    tri = ids.reshape(-1)[mesh.tri_verts]
    e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] != 2).any())


def _bold_text(cs, depth, bold=0.12):
    """Thicken the strokes by `bold` and extrude, overshooting and backing off until
    no two outlines merely touch (that would leave non-manifold edges in the STL)."""
    from manifold3d import JoinType
    for grow in np.arange(0.2, 0.8, 0.03):
        out = cs.offset(grow, JoinType.Round).offset(bold - grow, JoinType.Round).simplify(0.01)
        solid = out.extrude(depth + 1.0).translate((0, 0, -1.0))
        if not _pinched(solid):
            return solid
    return solid


def text_solid(lines, depth):
    """Engraving tool for the underside. `lines` are laid out as seen from below:
    [(text, size, (x, y), angle_deg)], then mirrored into model coordinates."""
    from manifold3d import CrossSection, FillRule, Manifold, OpType
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    font = '/System/Library/Fonts/Supplemental/Luminari.ttf'
    prop = FontProperties(fname=font) if os.path.exists(font) else FontProperties(weight='bold')
    tools = []
    for text, size, (x, y), angle in lines:
        tp = TextPath((0, 0), text, size=size, prop=prop)
        polys = [np.asarray(poly, float) for poly in tp.to_polygons(closed_only=True)]
        ext = tp.get_extents()
        cs = (CrossSection(polys, FillRule.EvenOdd)
              .translate((-(ext.x0 + ext.x1) / 2, -(ext.y0 + ext.y1) / 2))
              .rotate(angle).translate((x, y)).mirror((1, 0)))
        tools.append(_bold_text(cs, depth))
    return Manifold.batch_boolean(tools, OpType.Add)


def export(m, path):
    import trimesh
    from manifold3d import Manifold
    parts = [c for c in m.decompose() if abs(c.volume()) > 1.0]   # drop sub-mm specks
    m = Manifold.compose(parts)
    mesh = m.to_mesh()
    trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts, process=False).export(path)
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    print(f'  wrote {path}: {m.num_tri():,} triangles, '
          f'{hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} x {hi[2] - lo[2]:.1f} mm, '
          f'{m.volume() / 1000:.0f} cm^3 solid')


def build_base(P, out_dir):
    from manifold3d import Manifold
    t = time.time()
    m = to_manifold(*mesh_sdf('base', P, BASE_BOUNDS, P.resolution)).simplify(0.02)
    pr, ch = P.peg_d / 2, 0.6
    for el in ELEPHANTS:
        peg = (Manifold.cylinder(P.peg_h + 1 - ch, pr, circular_segments=64)
               + Manifold.cylinder(ch, pr, pr - ch, circular_segments=64).translate((0, 0, P.peg_h + 1 - ch)))
        m += peg.translate((el.o[0], el.o[1], Z_TOP - 1.0))
    m -= text_solid([("GREAT A'TUIN", 13.0, (0, 14), 0), ("Chelys galactica", 7.5, (0, -3), 0),
                     ("THE TURTLE MOVES", 7.5, (0, -18), 0), (f'v{__version__}', 6.0, (0, -31), 0)], 0.6)
    export(m, os.path.join(out_dir, 'great_atuin_base.stl'))
    print(f'  ({time.time() - t:.0f}s)')


def build_disc(P, out_dir):
    from manifold3d import Manifold
    t = time.time()
    rp, R, H = disc_dims(P)
    bounds = ((-R - 3, -R - 3, -1.0), (R + 3, R + 3, H + 2.0))
    m = to_manifold(*mesh_sdf('disc', P, bounds, min(P.resolution, 0.3))).simplify(0.02)
    seg = 720
    ch = 1.2
    pocket = (Manifold.cylinder(H, rp, circular_segments=seg).translate((0, 0, P.floor))
              + Manifold.cylinder(ch + 1, rp, rp + ch + 1, circular_segments=seg).translate((0, 0, H - ch)))
    m -= pocket
    hr, hd = P.peg_d / 2 + P.peg_clearance, P.peg_h + 0.8
    names = []
    for el, name, a in zip(ELEPHANTS, EL_NAMES, EL_ANGLES):
        hole = (Manifold.cylinder(hd + 1, hr, circular_segments=64)
                + Manifold.cylinder(1.5, hr + 0.5, hr - 1.0, circular_segments=64).translate((0, 0, 1)))
        m -= hole.translate((el.o[0], el.o[1], -1.0))
        # each name sits just outside its elephant's hole; seen from below it is at 180 - a
        b = math.radians(180.0 - a)
        names.append((name, 5.5, ((EL_R + 13) * math.cos(b), (EL_R + 13) * math.sin(b)),
                      math.degrees(b) - 90 if math.sin(b) >= 0 else math.degrees(b) + 90))
    names.append(("THE TURTLE MOVES", 8.0, (0, 0), 0))
    names.append((f'v{__version__}', 6.0, (0, -11), 0))
    m -= text_solid(names, 0.6)
    export(m, os.path.join(out_dir, f'great_atuin_disc_{P.jar_diameter:.1f}mm.stl'))
    print(f'  ({time.time() - t:.0f}s)')


def _length(s):
    s = s.strip().lower()
    if s.endswith(('in', '"')):
        return float(s.rstrip('in"').strip()) * 25.4
    return float(s.rstrip('mm').strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jar-diameter', type=_length, default=Params.jar_diameter,
                    help='jar base diameter, mm (or e.g. 6.04in); default 152.4 (6 in)')
    ap.add_argument('--clearance', type=float, default=Params.clearance, help='gap per side, mm')
    ap.add_argument('--pocket-depth', type=float, default=Params.pocket_depth, help='mm')
    ap.add_argument('--parts', choices=('all', 'base', 'disc'), default='all')
    ap.add_argument('--resolution', type=float, default=Params.resolution,
                    help='voxel size in mm; 0.8 for a quick draft')
    ap.add_argument('--out', default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    P = Params(jar_diameter=a.jar_diameter, clearance=a.clearance,
               pocket_depth=a.pocket_depth, resolution=a.resolution)
    rp, R, H = disc_dims(P)
    print(f"Great A'Tuin jar stand v{__version__}")
    print(f'jar {P.jar_diameter:.1f} mm -> pocket {2 * rp:.1f} mm x {P.pocket_depth:.0f} mm deep, '
          f'disc {2 * R:.1f} mm; disc rests at z = {Z_TOP:.1f} mm')
    if 2 * (EL_R + P.peg_d) > 2 * R:
        raise SystemExit('jar is too small for the elephants to reach under the disc')
    if a.parts in ('all', 'base'):
        build_base(P, a.out)
    if a.parts in ('all', 'disc'):
        build_disc(P, a.out)


if __name__ == '__main__':
    main()
