"""Explicit ownership and external-boundary planning; no Blender dependency."""
import math


def plan(bones, weighted, owned_roots=(), external=()):
    table={b['name']:b for b in bones};external=set(external);weighted=set(weighted)
    roots=set(owned_roots)
    if len(table)!=len(bones):raise ValueError('Duplicate bone names')
    if (roots|external|weighted)-table.keys():raise ValueError('Configuration contains nonexistent bones')
    children={n:[] for n in table}
    for n,b in table.items():
        if b.get('parent'):
            if b['parent'] not in table:raise ValueError('Missing parent: '+n)
            children[b['parent']].append(n)
        if set(b.get('dependencies',[]))-table.keys():raise ValueError('Missing dependency: '+n)
        seen={n};p=b.get('parent')
        while p:
            if p in seen:raise ValueError('Parent chain cycle')
            if p not in table:raise ValueError('Missing parent: '+n)
            seen.add(p);p=table[p].get('parent')
    owned=set();pending=list(roots)
    while pending:
        n=pending.pop()
        if n in owned:continue
        if n in external:raise ValueError('Owned chain contains external attachments; split ownership: '+n)
        owned.add(n);pending.extend(children[n])
    unknown=weighted-owned-external
    if unknown:raise ValueError('Weighted bone ownership is unknown; assign an owned chain or external attachment: '+', '.join(sorted(unknown)))
    keep=set(owned);anchors=weighted&external;pending=list(keep)
    while pending:
        n=pending.pop();b=table[n]
        refs=set(b.get('dependencies',[]))
        if b.get('parent'):refs.add(b['parent'])
        for d in refs:
            if d in external:anchors.add(d)
            elif d not in keep:
                # Required helpers may lie outside the selected subtree. An
                # unexplained parent boundary is not silently claimed as own.
                if d==b.get('parent') and not table[d].get('helper') and d not in owned:
                    raise ValueError('Parent ownership is unconfirmed; mark external attachments or extend owned chains: '+d)
                keep.add(d);pending.append(d)
    if not keep and not anchors:raise ValueError('No valid accessory bones or attachment points')
    return {'owned':sorted(keep),'anchors':sorted(anchors),'roots':sorted(roots),
            'remove':sorted(set(table)-keep-anchors),'multi_anchor':len(anchors)>1}


def remap(rows, mapping):
    result=[]
    for row in rows:
        out={}
        for name,value in row.items():
            if not math.isfinite(value) or value<0:raise ValueError('Invalid weights')
            key=mapping.get(name,name);out[key]=out.get(key,0.)+value
        if abs(sum(out.values())-sum(row.values()))>1e-6:raise ValueError('Total influence share is not conserved')
        result.append(out)
    return result
