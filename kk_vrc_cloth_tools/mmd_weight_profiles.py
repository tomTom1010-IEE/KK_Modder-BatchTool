"""Runtime candidate recognition using the maintained research tables.

Unknowns and physics evidence are never automatic DYNAMIC authorization.
"""
import json
from pathlib import Path
from .mmd_preprocess_rules import canonical
from .weight_features import digest

def load(profile='MMD', asset_path=''):
    repo=Path(__file__).resolve().parent.parent/'bone_profiles'
    root=repo if (repo/'mmd_conventions_v1.json').is_file() else Path(__file__).with_name('bone_profiles')
    conventions=json.loads((root/'mmd_conventions_v1.json').read_text(encoding='utf-8-sig'))
    if conventions.get('schema')!='mmd_bone_conventions_v1':raise ValueError('Unsupported MMD conventions schema')
    asset=None
    if profile=='MMD_LIV' or asset_path:
        path=Path(asset_path) if asset_path else root/'mmd_r4_liv_v1.json'
        asset=json.loads(path.read_text(encoding='utf-8-sig'))
        if asset.get('schema')!='mmd_asset_bone_profile_v1':raise ValueError('Unsupported MMD asset profile schema')
    return conventions,asset,digest([conventions,asset])

def recognize(records, conventions, asset=None):
    entries={canonical(n):v for n,v in conventions['entries'].items()}
    aliases={}
    for b in records:
        for n in {canonical(b['name']),canonical(b.get('name_j',''))}- {''}:
            aliases.setdefault(n,set()).add(b['name'])
    historical={b['name']:b for b in (asset or {}).get('bones',[])}
    result={}
    for b in records:
        keys={canonical(b['name']),canonical(b.get('name_j',''))}-{''}
        matches={k for k in keys if k in entries}
        collision=any(len(aliases[k])>1 for k in keys)
        info={'role':'REVIEW','reason':'Unknown or needs asset ownership review'}
        if collision or len(matches)>1:
            info['reason']='Alias collision or real-name / name_j conflict'
        elif matches:
            entry=entries[next(iter(matches))]
            info.update(entry)
            if entry['kind'] in {'BODY','BODY_SUPPORT','FINGER'} and entry.get('budget_region'):
                info['role']='BODY';info['reason']='Maintained convention candidate; review mappings and hierarchy'
        historical_bone=historical.get(b['name'])
        if historical_bone:
            info['asset_evidence']={'candidate_kind':historical_bone['candidate_kind'],
                'same_parent':historical_bone.get('parent')==b.get('parent'),
                'issues':historical_bone.get('issues',[])}
        result[b['name']]=info
    return result
