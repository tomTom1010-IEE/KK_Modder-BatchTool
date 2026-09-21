"""Explicit reviewed regions; no spatial guesses and no Blender dependency."""

MODES = {'UNIFORM', 'EDGE_GRADIENT'}


def resolve_regions(rows, roles, regions):
    """Resolve bone-derived or explicit vertex masks to per-vertex strategies.

    A region's `bones` is an already-expanded chain. An explicit `vertices`
    mask takes precedence so a single chain can be split into several regions.
    Unknown, uncovered mixed vertices and conflicting overlaps are errors.
    """
    modes = {}; owners = {}; errors = []
    for region in regions:
        name = region['name']; mode = region['mode']
        bones = set(region.get('bones', []))
        if any(roles.get(n) != 'DYNAMIC' for n in bones):
            errors.append(f'{name}: selected chain contains non-dynamic bones')
        vertices = region.get('vertices')
        if vertices is None:
            vertices = [i for i,row in enumerate(rows) if any(row.get(n,0)>0 for n in bones)]
        if not vertices:errors.append(f'{name}: empty influence region')
        for i in vertices:
            if type(i) is not int or not 0 <= i < len(rows):
                errors.append(f'{name}: invalid vertex {i}');continue
            if mode not in MODES:
                errors.append(f'{name}: needs Agent/manual analysis; unsupported or unreviewed mode');break
            if i in modes and modes[i] != mode:
                errors.append(f'vertex {i}: conflicting regions {owners[i]} / {name}')
            modes[i] = mode;owners[i] = name
    uncovered = [i for i,row in enumerate(rows)
                 if any(roles.get(n)=='BODY' and w>0 for n,w in row.items())
                 and any(roles.get(n)=='DYNAMIC' and w>0 for n,w in row.items()) and i not in modes]
    if uncovered:errors.append(f'{len(uncovered)} mixed vertices lack a reviewed region (first: {uncovered[:8]})')
    if errors:raise ValueError('; '.join(dict.fromkeys(errors))[:1600])
    return modes
