"""Render the README images with Blender (4.x) from the generated STLs.

    blender -b -P tools/render.py -- [--jar-diameter 152.4] [--views hero,base] [--res 1400]

Writes renders/<view>.png. Views: hero assembled base elephants exploded head rimfall
underside_base underside_disc (default: all). Parts are coloured with the filaments
in filaments.json, and the elephants are placed with atuin.placement().
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import atuin  # noqa: E402  (numpy only at import time, which Blender bundles)

VIEWS = ('hero', 'assembled', 'base', 'elephants', 'exploded', 'head', 'rimfall', 'underside_base',
         'underside_disc')
FLOOR, JAR_H = atuin.Params.floor, 130.0   # JAR_H is just for show

ap = argparse.ArgumentParser()
ap.add_argument('--jar-diameter', type=float, default=152.4)
ap.add_argument('--views', default=','.join(VIEWS))
ap.add_argument('--res', type=int, default=1400)
ap.add_argument('--samples', type=int, default=64)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = True
    scene.cycles.device = 'GPU'
except Exception:
    pass
scene.render.resolution_x = args.res
scene.render.resolution_y = int(args.res * 0.75)
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 0.4

world = bpy.data.worlds.new('space')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.015, 0.018, 0.04, 1)
scene.world = world


def material(name, color, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    return m


def filament_material(f):
    """A material that looks like the filament: matte, or with Galaxy's glitter."""
    lin = [(c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4
           for c in (int(f['hex'][i:i + 2], 16) for i in (1, 3, 5))]
    if f['filament'] == 'PLA Matte':
        return material(f['part'], lin, 0.85)
    m = material(f['part'], lin, 0.4, 0.1)
    if f['filament'] == 'PLA Galaxy':     # gold sparkle: tiny metallic flecks
        nt = m.node_tree
        coord = nt.nodes.new('ShaderNodeTexCoord')    # object space, so the flecks are mm-sized
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.inputs['Scale'].default_value = 1.2
        nt.links.new(coord.outputs['Object'], vor.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.06
        ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
        ramp.color_ramp.elements[1].position = 0.08
        ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
        nt.links.new(vor.outputs['Distance'], ramp.inputs['Fac'])
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = (*lin, 1)
        mix.inputs['B'].default_value = (0.9, 0.65, 0.25, 1)
        nt.links.new(ramp.outputs['Color'], mix.inputs['Factor'])
        bsdf = nt.nodes['Principled BSDF']
        nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        nt.links.new(ramp.outputs['Color'], bsdf.inputs['Metallic'])
    return m


def load(path, mat):
    bpy.ops.wm.stl_import(filepath=path)
    o = bpy.context.selected_objects[0]
    o.data.shade_smooth()
    o.data.set_sharp_from_angle(angle=math.radians(35))
    o.data.materials.append(mat)
    return o


FIL = {f['part']: f for f in json.load(open(os.path.join(ROOT, 'filaments.json')))['parts']}
def light(name, kind, energy, loc=None, rot=None, size=None, target=None):
    o = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
    o.data.energy = energy
    if size:
        o.data.size = size
    if loc:
        o.location = loc
    if rot:
        o.rotation_euler = rot
    if target:
        o.rotation_euler = (Vector(target) - o.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(o)
    return o


base = load(os.path.join(ROOT, FIL['turtle']['stl']), filament_material(FIL['turtle']))
elephants = [load(os.path.join(ROOT, FIL['elephants']['stl']), filament_material(FIL['elephants']))]
elephants += [bpy.data.objects.new(f'elephant{i}', elephants[0].data) for i in (1, 2, 3)]
for o, a in zip(elephants, atuin.EL_ANGLES):
    if o.name not in scene.collection.objects:
        scene.collection.objects.link(o)
    o.matrix_world = Matrix(atuin.placement(a).tolist())
disc_z = atuin.Z_TOP
disc = load(os.path.join(ROOT, FIL['disc']['stl'].format(jar=f'{args.jar_diameter:.1f}')),
            filament_material(FIL['disc']))

bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=args.jar_diameter / 2, depth=JAR_H)
jar = bpy.context.object
bevel = jar.modifiers.new('bevel', 'BEVEL')
bevel.width = 6
bevel.segments = 6
jar.data.shade_smooth()
glass = material('glass', (0.88, 0.94, 0.97), 0.06)
glass.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value = 0.95
glass.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value = 1.45
jar.data.materials.append(glass)

bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, -0.01))
floor = bpy.context.object
floor.data.materials.append(material('floor', (0.06, 0.06, 0.075), 0.7))

light('sun', 'SUN', 4.0, rot=(math.radians(42), math.radians(-22), math.radians(-35))).data.angle = math.radians(6)
light('fill', 'AREA', 500000, loc=(-320, 260, 220), size=400, target=(0, 0, 60))
light('rim', 'AREA', 350000, loc=(260, 320, 260), size=250, target=(0, 0, 80))
below = light('below', 'AREA', 900000, loc=(0, 0, -400), size=500, target=(0, 0, 0))

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.clip_end = 10000


def shoot(name, target, az, el, dist, lens=60, ortho=None, show=(), rot=None, disc_at=None, lift=0.0):
    objs = {'base': base, 'disc': disc, 'jar': jar, 'floor': floor}
    for key, o in objs.items():
        o.hide_render = key not in show
    for o in elephants:
        o.hide_render = 'base' not in show
        o.location.z = atuin.EL_SOLE_Z + lift
    below.hide_render = 'floor' in show
    disc.location.z = disc_z if disc_at is None else disc_at
    jar.location = (0, 0, disc_z + FLOOR + JAR_H / 2)
    t = Vector(target)
    a, e = math.radians(az), math.radians(el)
    cam.location = t + dist * Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    cam.rotation_euler = rot or (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens
    os.makedirs(os.path.join(ROOT, 'renders'), exist_ok=True)
    scene.render.filepath = os.path.join(ROOT, 'renders', f'{name}.png')
    bpy.ops.render.render(write_still=True)


# looking straight up, so pin the roll: image right = -x, the way you'd see it flipped over
UP = (0, math.pi, 0)
SHOTS = {
    'hero': dict(target=(0, 0, 105), az=-38, el=12, dist=760, lens=50, show=('base', 'disc', 'jar', 'floor')),
    'assembled': dict(target=(0, 0, 55), az=28, el=16, dist=640, lens=50, show=('base', 'disc', 'floor')),
    'base': dict(target=(5, 0, 42), az=-40, el=28, dist=400, lens=50, show=('base', 'floor')),
    'elephants': dict(target=(12, 8, 66), az=35, el=16, dist=360, lens=60, show=('base', 'floor')),
    'exploded': dict(target=(5, 0, 72), az=-40, el=14, dist=470, lens=50, show=('base', 'floor'), lift=40),
    'head': dict(target=(105, 0, 32), az=-28, el=10, dist=290, lens=60, show=('base', 'floor')),
    'rimfall': dict(target=(55, -45, 10), az=-55, el=20, dist=280, lens=60, show=('disc', 'floor'), disc_at=0),
    'underside_base': dict(target=(0, 0, 0), az=0, el=-90, dist=1000, ortho=262, show=('base',), rot=UP),
    'underside_disc': dict(target=(0, 0, 0), az=0, el=-90, dist=1000, ortho=190, show=('disc',), rot=UP,
                           disc_at=0),
}
for v in args.views.split(','):
    shoot(v, **SHOTS[v])
