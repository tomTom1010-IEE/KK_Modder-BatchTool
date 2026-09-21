"""Pure, name-independent weight-feature analysis and mass-preserving planning.

Roles and bone mappings are supplied by the caller, never inferred from mesh names.
IGNORE is a non-deforming mask. DROP explicitly discards an unwanted helper.
"""
import hashlib
import json
import math
from collections import Counter

ROLES = {"BODY", "DYNAMIC", "IGNORE", "DROP"}
BODY_REGIONS = {"TORSO", "ARM_L", "ARM_R", "LEG_L", "LEG_R"}


def redirect_body_samples(rows, replacements, regions, allowed):
    """Replace excluded target-body detail influences within their category.

    Explicit mappings (e.g. same-side bnip to bust) preserve sampled mass;
    source roles/budgets and dynamic weights are not changed here.
    """
    allowed=set(allowed);excluded=set(replacements)
    for src,mapping in replacements.items():
        if src not in regions or not mapping:raise ValueError('Missing body replacement region/mapping: '+src)
        if set(mapping)-allowed or set(mapping)&excluded:raise ValueError('Replacement must terminate at allowed body bones')
        if any(regions.get(n)!=regions[src] for n in mapping):raise ValueError('Cross-region body replacement')
        if abs(sum(checked(mapping).values())-1)>1e-8:raise ValueError('Replacement fractions must sum to one')
    result=[]
    for row in rows:
        out={}
        for n,w in checked(row).items():
            for dst,factor in replacements.get(n,{n:1.}).items():out[dst]=out.get(dst,0)+w*factor
        result.append(out)
    return result


def digest(value):
    canonical = json.loads(json.dumps(value, allow_nan=False))
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, allow_nan=False).encode()).hexdigest()


def checked(weights):
    result = {}
    for name, value in weights.items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid weight: {name}={value}")
        if value > 0:
            result[name] = float(value)
    return result


def normalized(weights):
    weights = checked(weights)
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()} if total else {}


def snapshot(rows, edges, roles, topology):
    rows = [checked(row) for row in rows]
    missing = set().union(*(set(row) for row in rows)) - roles.keys()
    if missing or any(role not in ROLES for role in roles.values()):
        raise ValueError(f"Explicit roles required; unclassified groups: {sorted(missing)}")
    value = {"schema": 1, "rows": rows, "edges": [list(e) for e in edges],
             "roles": dict(roles), "topology": topology}
    value["id"] = digest(value)
    return value


def verify_snapshot(source):
    if source.get("schema") != 1 or source.get("id") != digest({k: v for k, v in source.items() if k != "id"}):
        raise ValueError("Snapshot changed or unsupported schema")


def analyze(source, tolerance=0.015):
    verify_snapshot(source)
    profiles = []
    for row in source["rows"]:
        body = {k: v for k, v in row.items() if source["roles"][k] == "BODY"}
        dynamic = {k: v for k, v in row.items() if source["roles"][k] == "DYNAMIC"}
        total = sum(body.values()) + sum(dynamic.values())
        profiles.append({"body_share": sum(body.values()) / total if total else 0.,
                         "body_distribution": normalized(body), "dynamic": dynamic,
                         "valid_total": total})
    adjacency = [set() for _ in profiles]
    for a, b in source["edges"]:
        adjacency[a].add(b)
        adjacency[b].add(a)
    for i, profile in enumerate(profiles):
        share = profile["body_share"]
        if not profile["valid_total"]:
            feature = "UNWEIGHTED"
        elif share == 0:
            feature = "ZERO_BODY"
        elif share == 1:
            feature = "BODY_ONLY"
        else:
            def difference(j):
                other = profiles[j]
                a, b = profile["body_distribution"], other["body_distribution"]
                return max(abs(share - other["body_share"]),
                           sum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys()))
            feature = "STABLE_MIXED" if adjacency[i] and all(difference(j) <= tolerance for j in adjacency[i]) else "VARYING_MIXED"
        profile["feature"] = feature
    return profiles


def remap(weights, mapping):
    result = {}
    for name, weight in weights.items():
        if name not in mapping:
            raise ValueError(f"Missing bone mapping: {name}")
        targets = normalized(mapping[name])
        if not targets:
            raise ValueError(f"Empty bone mapping: {name}")
        for target, factor in targets.items():
            result[target] = result.get(target, 0.) + weight * factor
    return result


def plan(source, body_map, dynamic_map, body_groups, samples=None,
         confidence=None, indices=None, tolerance=0.015):
    """Return per-vertex writes. Geometry confidence is explicit, defaulting to 0.

    Stable mixed weights use semantic mapping, not geometric resampling. Features
    are evidence, not material/rigidity labels. No threshold erases small weights.
    """
    profiles = analyze(source, tolerance)
    samples, confidence = samples or {}, confidence or {}
    selected = sorted(set(range(len(profiles)) if indices is None else indices))
    body_groups = set(body_groups)
    source_managed = {n for n, role in source["roles"].items() if role != "IGNORE"}
    dynamic_groups = {k for targets in dynamic_map.values() for k in targets}
    if body_groups & dynamic_groups:
        raise ValueError("Body and retained dynamic targets must be disjoint")
    managed = source_managed | body_groups | dynamic_groups
    if managed & {n for n, role in source["roles"].items() if role == "IGNORE"}:
        raise ValueError("Destination conflicts with a preserved non-bone group")
    writes, skipped = {}, {}
    for i in selected:
        if i < 0 or i >= len(profiles):
            raise ValueError(f"Invalid vertex index {i}")
        p, row = profiles[i], source["rows"][i]
        if not p["valid_total"]:
            skipped[i] = "No BODY or DYNAMIC influence; unchanged"
            continue
        share = p["body_share"]
        mapped = remap({k: v for k, v in row.items() if source["roles"][k] == "BODY"}, body_map)
        sampled = checked(samples.get(i, {}))
        if (set(mapped) | set(sampled)) - body_groups:
            raise ValueError("Candidate contains non-body destination groups")
        alpha = float(confidence.get(i, 0.))
        if not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("Sampling confidence must be in [0, 1]")
        if p["feature"] in {"ZERO_BODY", "STABLE_MIXED"} or not sampled:
            alpha = 0.
        mapped, sampled = normalized(mapped), normalized(sampled)
        body = {k: share * ((1-alpha)*mapped.get(k, 0.) + alpha*sampled.get(k, 0.))
                for k in mapped.keys() | sampled.keys()}
        retained = remap(p["dynamic"], dynamic_map)
        dynamic = {k: v / p["valid_total"] for k, v in retained.items()}
        weights = checked(dict(body, **dynamic))
        if abs(sum(weights.values())-1.) > 1e-6 or abs(sum(body.values())-share) > 1e-6:
            raise ValueError("Per-vertex mass invariant failed")
        writes[i] = weights
    return {"snapshot_id": source["id"], "managed_groups": sorted(managed),
            "writes": writes, "skipped": skipped,
            "features": {i: profiles[i]["feature"] for i in selected},
            "body_shares": {i: profiles[i]["body_share"] for i in writes},
            "summary": dict(Counter(profiles[i]["feature"] for i in selected))}


def plan_regions(source, body_map, dynamic_map, body_groups, source_regions,
                 target_regions, samples=None, confidence=None, indices=None,
                 min_region_sample=0.05, finger_policy=None, protected_components=None, region_modes=None):
    """Preserve five anatomical budgets plus retained dynamics per vertex.

    Head/neck belong to TORSO. Region maps are explicit rig-specific inputs.
    Native samples are only candidates within a region, never budget setters.
    Weak/missing regional evidence falls back to semantic mapping. No inpainting.
    """
    if protected_components is not None:
        raise NotImplementedError('Protected intra-region components are reserved, not implemented; review stable-follow plus gradient mixtures before applying')
    if not math.isfinite(min_region_sample) or not 0 < min_region_sample <= 1:
        raise ValueError('Regional sample threshold must be in (0, 1]')
    source_body = {n for n, r in source['roles'].items() if r == 'BODY'}
    # Explicit rig metadata: labels such as THUMB_L are identifiers, not bone-name rules.
    policy = finger_policy or {}
    source_fingers = policy.get('source_fingers', {})
    target_fingers = policy.get('target_fingers', {})
    enabled = set(policy.get('enabled', []))
    disabled_map = policy.get('disabled_map', {})
    if (set(source_fingers)-source_body or set(target_fingers)-set(body_groups) or
            enabled-set(source_fingers.values())):
        raise ValueError('Finger policy contains unclassified bones or unknown enabled fingers')
    body_map = {n:dict(m) for n,m in body_map.items()}
    for n,label in source_fingers.items():
        if source_regions.get(n) not in {'ARM_L','ARM_R'}:
            raise ValueError('Finger must belong to an arm region')
        if label in enabled:
            if not body_map.get(n) or any(target_fingers.get(k)!=label for k in normalized(body_map[n])):
                raise ValueError('Enabled finger requires matching explicit target finger mapping')
        else:
            if not disabled_map.get(n) or set(disabled_map[n]) & set(target_fingers):
                raise ValueError('Disabled finger requires a non-finger redistribution mapping')
            body_map[n] = dict(disabled_map[n])
    for n,m in body_map.items():
        if n not in source_fingers and set(m) & set(target_fingers):
            raise ValueError('Non-finger source cannot introduce finger influence')
    if source_body - source_regions.keys() or set(body_groups) - target_regions.keys():
        raise ValueError('Explicit anatomical regions required for every body group')
    if any(r not in BODY_REGIONS for r in list(source_regions.values()) + list(target_regions.values())):
        raise ValueError('Unknown anatomical region')
    for n in source_body:
        for dest in normalized(body_map.get(n, {})):
            if target_regions.get(dest) != source_regions[n]:
                raise ValueError('Semantic mapping crosses anatomical regions')
    proposal = plan(source, body_map, dynamic_map, body_groups, indices=indices)
    profiles = analyze(source)
    samples, confidence = samples or {}, confidence or {}
    modes = {} if region_modes is None else {int(i):mode for i,mode in region_modes.items()}
    if any(not 0<=i<len(profiles) or mode not in {'UNIFORM','EDGE_GRADIENT'} for i,mode in modes.items()):
        raise ValueError('Invalid explicit region mode')
    budgets, fallback, finger_weights = {}, {}, {}
    for i, weights in proposal['writes'].items():
        p = profiles[i]
        raw_sample = checked(samples.get(i, {}))
        if set(raw_sample) - set(body_groups):
            raise ValueError('Sample contains non-body destinations')
        sampled = normalized({n:w for n,w in raw_sample.items() if n not in target_fingers})
        alpha = float(confidence.get(i, 0))
        if not math.isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError('Sampling confidence must be in [0, 1]')
        mixed=0<p['body_share']<1
        if region_modes is not None and mixed and i not in modes:
            raise ValueError('Mixed vertex lacks explicit reviewed mode: '+str(i))
        if p['feature']=='ZERO_BODY' or modes.get(i)=='UNIFORM' or (i not in modes and p['feature']=='STABLE_MIXED'):
            alpha = 0
        result = {n:w for n,w in weights.items() if n not in body_groups}
        budgets[i] = {r:0.0 for r in BODY_REGIONS}
        budgets[i]['DYNAMIC'] = sum(result.values())
        finger_weights[i] = {}
        for region in sorted(BODY_REGIONS):
            original = {n:w for n,w in source['rows'][i].items()
                        if source['roles'][n] == 'BODY' and source_regions[n] == region}
            budget = sum(original.values()) / p['valid_total']
            budgets[i][region] = budget
            if not budget:
                continue
            reserved = {n:w for n,w in original.items() if source_fingers.get(n) in enabled}
            finger_result = {n:w/p['valid_total'] for n,w in remap(reserved, body_map).items()}
            finger_weights[i].update(finger_result)
            result.update(finger_result)
            original = {n:w for n,w in original.items() if n not in reserved}
            free_budget = sum(original.values()) / p['valid_total']
            mapped = normalized(remap(original, body_map))
            candidate = {n:w for n,w in sampled.items() if target_regions[n] == region}
            amount = sum(candidate.values())
            local_alpha = alpha
            if amount < min_region_sample:
                local_alpha = 0
                if alpha and free_budget:
                    fallback.setdefault(i, []).append(region)
            candidate = normalized(candidate)
            for n in mapped.keys() | candidate.keys():
                value = free_budget * ((1-local_alpha)*mapped.get(n,0) + local_alpha*candidate.get(n,0))
                if value:
                    result[n] = value
            actual = sum(w for n,w in result.items() if target_regions.get(n) == region)
            if abs(actual-budget) > 1e-6:
                raise ValueError('Regional mass invariant failed')
        if abs(sum(result.values())-1) > 1e-6:
            raise ValueError('Total regional mass invariant failed')
        proposal['writes'][i] = result
    proposal.update(region_budgets=budgets, regional_fallback=fallback,
                    source_regions=dict(source_regions), target_regions=dict(target_regions),
                    min_region_sample=min_region_sample, finger_policy=policy,
                    preserved_finger_weights=finger_weights, region_modes=modes)
    return proposal
