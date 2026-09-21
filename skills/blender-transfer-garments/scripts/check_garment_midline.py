"""Read-only source-corresponded midline diagnostics; coordinates share units.

Usage: python check_garment_midline.py input.json --output report.json
See the garment-transfer skill's references/midline-check.md for the schema.
"""
import argparse
import json
import math
from pathlib import Path


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def length(a):
    return math.sqrt(dot(a, a))


def vector(a):
    if len(a) != 3 or not all(math.isfinite(float(x)) for x in a):
        raise ValueError('Expected a finite 3-vector')
    return [float(x) for x in a]


def plane(p):
    origin, normal = vector(p['origin']), vector(p['normal'])
    n = length(normal)
    if n == 0:
        raise ValueError('Plane normal is zero')
    return origin, [x/n for x in normal]


def vertices(mesh):
    return [vector(v) for v in mesh['vertices']]


def edges(mesh, count):
    out = set()
    for pair in mesh['edges']:
        if len(pair) != 2 or any(type(i) is not int or not 0 <= i < count for i in pair):
            raise ValueError('Invalid edge indices')
        if pair[0] == pair[1]:
            raise ValueError('Self-loop edge')
        out.add(tuple(sorted(pair)))
    return out


def audit(data):
    source, target = vertices(data['source']), vertices(data['target'])
    se, te = edges(data['source'], len(source)), edges(data['target'], len(target))
    so, sn = plane(data['source_plane'])
    to, tn = plane(data['target_plane'])
    tolerance = float(data['tolerance'])
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('tolerance must be positive, in coordinate units')
    ids = data['center_ids']
    if len(ids) != len(set(ids)) or any(type(i) is not int or not 0 <= i < len(source) for i in ids):
        raise ValueError('Invalid or duplicate source center_ids')
    mapping = data['source_to_target']
    if len(mapping) != len(source):
        raise ValueError('Mapping must have one entry per source vertex; use null for missing')
    mapped = [i for i in mapping if i is not None]
    if any(type(i) is not int or not 0 <= i < len(target) for i in mapped) or len(mapped) != len(set(mapped)):
        raise ValueError('Mapping must be one-to-one with valid target indices')
    dist = lambda p, o, n: dot(sub(p, o), n)
    if any(abs(dist(source[i], so, sn)) > tolerance for i in ids):
        raise ValueError('Declared source centerline is not on source plane within tolerance')
    report = {'status': 'pass', 'tolerance': tolerance, 'source_center_count': len(ids),
              'missing_center_ids': [], 'off_plane': [], 'lateral_kinks': [],
              'missing_center_edges': [], 'pair_imbalance': [], 'missing_pairs': []}
    ds = {}
    for i in ids:
        j = mapping[i]
        if j is None:
            report['missing_center_ids'].append(i)
            continue
        ds[i] = dist(target[j], to, tn)
        if abs(ds[i]) > tolerance:
            report['off_plane'].append({'source': i, 'target': j, 'signed_distance': ds[i]})
    selected = set(ids)
    ce = sorted(e for e in se if set(e) <= selected)
    for a, b in ce:
        if a not in ds or b not in ds:
            continue
        if tuple(sorted((mapping[a], mapping[b]))) not in te:
            report['missing_center_edges'].append([a, b])
            continue
        jump = abs(ds[a]-ds[b])
        if jump > tolerance:
            report['lateral_kinks'].append({'source_edge': [a, b], 'lateral_jump': jump})
    for a, b in data.get('mirror_pairs', []):
        if not all(type(i) is int and 0 <= i < len(source) for i in (a, b)) or a == b:
            raise ValueError('Invalid mirror pair')
        sd = dist(source[a], so, sn)
        reflection = [x-2*sd*n for x, n in zip(source[a], sn)]
        if length(sub(reflection, source[b])) > tolerance:
            raise ValueError('Declared source pair is not mirrored within tolerance')
        if mapping[a] is None or mapping[b] is None:
            report['missing_pairs'].append([a, b])
            continue
        pa, pb = target[mapping[a]], target[mapping[b]]
        da, db = dist(pa, to, tn), dist(pb, to, tn)
        error = length(sub([x-2*da*n for x, n in zip(pa, tn)], pb))
        crossed = abs(sd) > tolerance and (da*sd < -tolerance*abs(sd) or db*sd > tolerance*abs(sd))
        if error > tolerance or crossed:
            report['pair_imbalance'].append({'source_pair': [a, b], 'reflection_error': error,
                                              'side_reversal': crossed})
    report['checked_center_count'] = len(ds)
    report['source_center_edge_count'] = len(ce)
    report['max_plane_distance'] = max((abs(x) for x in ds.values()), default=None)
    warnings = ('off_plane', 'lateral_kinks', 'pair_imbalance')
    incomplete = (len(ids) < 2 or not ce or report['missing_center_ids'] or
                  report['missing_center_edges'] or report['missing_pairs'])
    if any(report[k] for k in warnings):
        report['status'] = 'warning'
    elif incomplete:
        report['status'] = 'inconclusive'
    report['coverage_complete'] = not bool(incomplete)
    report['scope'] = 'Plane drift, lateral edge jumps and supplied mirror pairs only; not a full mesh-quality pass.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Output must differ from input')
    try:
        report = audit(json.loads(args.input.read_text(encoding='utf-8-sig')))
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        report = {'status': 'invalid_input', 'error': str(exc)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(report['status'])
    return {'pass': 0, 'warning': 1, 'inconclusive': 2, 'invalid_input': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
