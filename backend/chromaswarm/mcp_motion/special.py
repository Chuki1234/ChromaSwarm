"""Motion MCP's declarative Three.js scene contract (no arbitrary executable scene code)."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

THREE_VERSION = '0.187.0'


def build_special(section_id: str, asset_id: str, scene: dict) -> dict:
    if not all(re.fullmatch(r'[a-z0-9-]{1,96}', value) for value in (section_id, asset_id)):
        return {'error': 'invalid section_id or asset_id'}
    if not scene.get('model_url') and not scene.get('objects'):
        return {'error': 'A model URL or measured scene objects are required; a canvas screenshot does not reveal its 3D geometry.'}
    def validate(value, key=''):
        if isinstance(value, dict):
            for k, v in value.items(): validate(v, k)
        elif isinstance(value, list):
            if len(value) > 256: raise ValueError('scene array too large')
            for v in value: validate(v, key)
        elif isinstance(value, (int, float)):
            if not math.isfinite(value) or abs(value)>1e6: raise ValueError('invalid scene number')
        elif key in ('model_url', 'texture', 'poster') and value:
            if not (str(value).startswith('/') and not str(value).startswith('//')) and urlparse(str(value)).scheme not in ('http','https'):
                raise ValueError('asset URLs must be HTTP(S) or local absolute paths')
    try:
        validate(scene)
        for obj in scene.get('objects', []):
            if obj.get('geometry') not in ('box','sphere','plane','torus','icosahedron'): raise ValueError('unsupported geometry')
        for track in scene.get('tracks', []):
            if track.get('property') not in ('rotation','position','scale') or track.get('duration',0)<=0: raise ValueError('invalid animation track')
        if len(json.dumps(scene)) > 200000: raise ValueError('scene too large')
    except (ValueError, TypeError) as error:
        return {'error': str(error)}
    component = ''.join(p.title() for p in f'{section_id}-{asset_id}'.split('-'))+'Asset'
    code = ('"use client";\nimport { ThreeAsset, type SceneSpec } from "@/components/motion/ThreeAsset";\n'
            f'const scene: SceneSpec = {json.dumps(scene)};\n'
            f'export function {component}() {{ return <ThreeAsset scene={{scene}} assetId="{asset_id}" '
            f'targetSelector=\'[data-swarm-section="{section_id}"] canvas[data-swarm-asset="{asset_id}"]\' />; }}\n')
    return {'kind': '3d-threejs', 'component': component, 'css': '', 'notes': 'Measured DOM host + declarative Three.js scene',
            'dependencies': {'three': THREE_VERSION}, 'dev_dependencies': {'@types/three': THREE_VERSION},
            'files': [{'path':'components/motion/ThreeAsset.tsx','content':Path(__file__).with_name('three_asset.tsx').read_text(encoding='utf-8')},
                      {'path':f'components/motion/{component}.tsx','content':code}]}
