#!/usr/bin/env python3
"""Build a ready-to-print Bambu Studio project with each part on its own filament.

    .venv/bin/python tools/make_3mf.py [--jar-diameter 152.4] [--slice]

Writes great_atuin_<D>mm.3mf:
  plate 1  the base, as two parts: the turtle on filament 1, the elephants on filament 2
  plate 2  the Disc on filament 3
Filament presets and colours come from filaments.json.

The project is written as a plain 3MF with Bambu's part/filament metadata, then
loaded and re-saved by the Bambu Studio command line, so the result is a native
project with complete printer, process and filament settings. Needs Bambu Studio
(set BAMBU_STUDIO if it isn't in /Applications). --slice also slices it with Bambu
Studio and prints the time, filament and colour changes per plate.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import atuin  # noqa: E402

BAMBU = os.environ.get('BAMBU_STUDIO', '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio')
PROFILES = os.path.join(os.path.dirname(os.path.dirname(BAMBU)), 'Resources', 'profiles', 'BBL')
BED, PLATE_PITCH = 256.0, 256.0 * 1.2     # Bambu Studio lays plates out 1.2 bed-widths apart
CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PROD = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'


def mesh_xml(oid, name, m):
    v = '\n'.join(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in m.vertices)
    t = '\n'.join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
    return (f'  <object id="{oid}" name="{name}" type="model">\n   <mesh>\n    <vertices>\n{v}\n'
            f'    </vertices>\n    <triangles>\n{t}\n    </triangles>\n   </mesh>\n  </object>\n')


def raw_3mf(path, objects):
    """objects: [(name, plate, [(part_name, mesh, filament), ...])], meshes in model coordinates."""
    meshes, comps, items, settings, plates = [], [], [], [], {}
    oid = 0
    for name, plate, parts in objects:
        lo = np.min([m.bounds[0] for _, m, _ in parts], axis=0)
        hi = np.max([m.bounds[1] for _, m, _ in parts], axis=0)
        tx = (plate - 1) * PLATE_PITCH + BED / 2 - (lo[0] + hi[0]) / 2
        ty = BED / 2 - (lo[1] + hi[1]) / 2
        part_ids, xml_parts = [], []
        for part_name, m, filament in parts:
            oid += 1
            part_ids.append(oid)
            meshes.append(mesh_xml(oid, part_name, m))
            xml_parts.append(f'    <part id="{oid}" subtype="normal_part">\n'
                             f'      <metadata key="name" value="{part_name}"/>\n'
                             f'      <metadata key="extruder" value="{filament}"/>\n    </part>\n')
        oid += 1
        comps.append(f'  <object id="{oid}" type="model">\n   <components>\n' + ''.join(
            f'    <component p:path="/3D/Objects/parts.model" objectid="{i}"/>\n' for i in part_ids)
            + '   </components>\n  </object>\n')
        items.append(f'  <item objectid="{oid}" transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0" printable="1"/>\n')
        settings.append(f'  <object id="{oid}">\n    <metadata key="name" value="{name}"/>\n'
                        f'    <metadata key="extruder" value="{parts[0][2]}"/>\n' + ''.join(xml_parts) + '  </object>\n')
        plates.setdefault(plate, []).append(oid)
    for p, oids in sorted(plates.items()):
        settings.append(f'  <plate>\n    <metadata key="plater_id" value="{p}"/>\n' + ''.join(
            f'    <model_instance>\n      <metadata key="object_id" value="{o}"/>\n'
            f'      <metadata key="instance_id" value="0"/>\n    </model_instance>\n' for o in oids) + '  </plate>\n')
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', head + (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
            '</Types>\n'))
        z.writestr('_rels/.rels', head + (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n'))
        z.writestr('3D/_rels/3dmodel.model.rels', head + (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/Objects/parts.model" Id="rel-1" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n'))
        z.writestr('3D/Objects/parts.model', head + (
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}">\n <resources>\n'
            + ''.join(meshes) + ' </resources>\n <build/>\n</model>\n'))
        z.writestr('3D/3dmodel.model', head + (
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" xmlns:p="{PROD}" requiredextensions="p">\n'
            f' <metadata name="Title">Great A\'Tuin jar stand v{atuin.__version__}</metadata>\n'
            ' <resources>\n' + ''.join(comps) + ' </resources>\n <build>\n' + ''.join(items) + ' </build>\n</model>\n'))
        z.writestr('Metadata/model_settings.config', head + '<config>\n' + ''.join(settings) + '</config>\n')


def resolved_profile(kind, name):
    """A system profile with its `inherits` chain and its G-code templates merged in. The
    command line follows neither: without this it falls back to defaults (a 200 mm bed,
    no prime tower) and generic start/end G-code that is wrong for the printer."""
    d = json.load(open(os.path.join(PROFILES, kind, f'{name}.json')))
    parent = d.pop('inherits', None)
    if parent:
        merged = resolved_profile(kind, parent)
        merged.update(d)
        d = merged
    for path in glob.glob(os.path.join(PROFILES, kind, glob.escape(name) + ' template *.json')):
        d.update({k: v for k, v in json.load(open(path)).items() if k not in ('name', 'instantiation')})
    return d


def flush_matrix(colours):
    """Purge volumes (mm^3) for every colour change, as an N x N matrix. The GUI computes
    these from the colours; the command line needs them supplied. Each change takes the
    measured value from Bambu's table for the most similar pair of reference colours."""
    lines = open(os.path.join(os.path.dirname(PROFILES), '..', 'flush', 'flush_data_standard.txt')).read().split('\n')
    rgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)
    pairs = [(rgb(a), rgb(b), int(v)) for a, b, v in (l.split() for l in lines[3:] if len(l.split()) == 3)]

    def purge(src, dst):
        a, b = rgb(src), rgb(dst)
        return min(pairs, key=lambda t: np.linalg.norm(t[0] - a) + np.linalg.norm(t[1] - b))[2]
    return [str(0 if i == j else purge(ci, cj)) for i, ci in enumerate(colours) for j, cj in enumerate(colours)]


def finish_project(path, colours, bed='Textured PEI Plate', tower=(218, 200)):
    """Patch the saved project settings: our filament colours and their purge volumes, the
    P2S's stock plate, and a prime tower in the empty back-right corner of plate 1."""
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'Metadata/project_settings.config':
                cfg = json.loads(data)
                cfg['filament_colour'] = colours
                cfg['flush_volumes_matrix'] = flush_matrix(colours)
                cfg['curr_bed_type'] = bed
                cfg['wipe_tower_x'], cfg['wipe_tower_y'] = [str(tower[0])], [str(tower[1])]
                data = json.dumps(cfg, indent=4).encode()
            zout.writestr(item, data)
    os.replace(tmp, path)


def slice_report(path):
    """Slice every plate with Bambu Studio and summarise its own estimates."""
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([BAMBU, '--slice', '0', '--outputdir', tmp, path], capture_output=True, text=True, cwd=tmp)
        result = json.load(open(os.path.join(tmp, 'result.json')))
    if r.returncode != 0:
        sys.exit(f"slicing failed: {result.get('error_string')}")
    for p in result['sliced_plates']:
        t = p['main_predication']
        used = ', '.join(f"filament {f['id']} {f['total_used_g']:.0f} g" for f in p['filaments'])
        purge = sum(v for k, v in p['feature_type_times'].items() if k in ('Flush', 'Prime tower'))
        print(f"  plate {p['id']}: {int(t // 3600)} h {int(t % 3600 // 60):02d} m, {used}, "
              f"{p['filament_change_times']} filament changes ({purge / 60:.0f} min of purging and prime tower)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jar-diameter', type=atuin._length, default=atuin.Params.jar_diameter)
    ap.add_argument('--slice', action='store_true', help='slice with Bambu Studio and report')
    a = ap.parse_args()
    jar = f'{a.jar_diameter:.1f}'
    cfg = json.load(open(os.path.join(ROOT, 'filaments.json')))
    parts = {p['part']: p for p in cfg['parts']}
    load = {k: trimesh.load(os.path.join(ROOT, p['stl'].format(jar=jar))) for k, p in parts.items()}
    order = ['turtle', 'elephants', 'disc']                 # filament 1, 2, 3
    fil = {k: i + 1 for i, k in enumerate(order)}
    out = os.path.join(ROOT, f'great_atuin_{jar}mm.3mf')
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, 'raw.3mf')
        raw_3mf(raw, [("Great A'Tuin", 1, [(parts[k]['label'], load[k], fil[k]) for k in ('turtle', 'elephants')]),
                      ('The Disc', 2, [(parts['disc']['label'], load['disc'], fil['disc'])])])
        def flat(kind, name):
            path = os.path.join(tmp, f'{kind}_{len(os.listdir(tmp))}.json')
            json.dump(resolved_profile(kind, name), open(path, 'w'))
            return path
        settings = ';'.join([flat('machine', cfg['printer']), flat('process', cfg['process'])])
        filaments = ';'.join(flat('filament', parts[k]['preset']) for k in order)
        cmd = [BAMBU, '--arrange', '0', '--load-settings', settings, '--load-filaments', filaments,
               '--export-3mf', out, raw]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)   # it drops result.json in cwd
        if r.returncode != 0 or not os.path.exists(out):
            sys.exit(f'Bambu Studio failed ({r.returncode}):\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    finish_project(out, [parts[k]['hex'] for k in order])
    print(f'wrote {out}')
    for k in order:
        p = parts[k]
        print(f"  filament {fil[k]}: {p['label']:16s} {p['filament']} {p['color']} ({p['code']}) {p['hex']}")
    if a.slice:
        slice_report(out)


if __name__ == '__main__':
    main()
