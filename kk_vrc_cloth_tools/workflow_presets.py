from .ui_messages import format_message as _fmt
"""Pure graph discovery and semantic motion templates (no scene mutation)."""

def discover_roots(parents, roles, weighted, known_body=()):
    """Walk the full skeleton, including unweighted first segments.

    Unknown subtrees are candidates only. A known/explicit BODY or IGNORE bone
    is a boundary; a candidate never absorbs its body-bone descendants.
    """
    boundary=set(known_body)|{n for n,r in roles.items() if r in {'BODY','IGNORE'}}
    roots={}
    for name in sorted(set(weighted)-boundary):
        if name not in parents:continue
        root=name;seen={name}
        while parents.get(root) is not None and parents[root] not in boundary:
            parent=parents[root]
            if parent in seen:raise ValueError('Armature parent chain contains a cycle')
            seen.add(parent);root=parent
        roots.setdefault(root,[]).append(name)
    # An unweighted fan-out above several chains is often an organizational
    # node, not the first physical segment. Split it into candidate chains;
    # keep explicitly confirmed DYNAMIC roots intact. All candidates still
    # require review because topology alone cannot prove physics semantics.
    weighted=set(weighted)
    def split(root,names):
        branches={}
        for name in names:
            child=name
            while child!=root and parents.get(child)!=root:
                child=parents[child]
            if child!=root:branches.setdefault(child,[]).append(name)
        if root not in weighted and roles.get(root)!='DYNAMIC' and len(branches)>1:
            result={}
            for child,descendants in branches.items():result.update(split(child,descendants))
            return result
        return {root:names}
    result={}
    for root,names in roots.items():result.update(split(root,names))
    return result


# axis names refer to an anatomical rest frame, not fixed world XYZ.
def motion_templates(preset):
    out=[]
    if preset in {'UPPER','FULL'}:
        for side in ['L','R']:
            out += [(f'UPPER_ARM_{side}',_fmt('{v0} Arm raise', v0=side),'forward',35,False),
                    (f'UPPER_ARM_{side}',_fmt('{v0} Arm swing', v0=side),'right',30,False),
                    (f'LOWER_ARM_{side}',_fmt('{v0} Elbow bend', v0=side),'up',55,False)]
        out += [('CHEST','Torso bend','right',15,False),('CHEST','Torso side bend','forward',12,False),('CHEST','Torso twist','up',15,False)]
    if preset in {'LOWER','FULL'}:
        for side in ['L','R']:
            out += [(f'UPPER_LEG_{side}',_fmt('{v0} Leg raise', v0=side),'right',35,False),
                    (f'UPPER_LEG_{side}',_fmt('{v0} Leg abduction', v0=side),'forward',20,False),
                    (f'LOWER_LEG_{side}',_fmt('{v0} Knee bend', v0=side),'right',55,False)]
        if preset=='LOWER':out += [('CHEST','Torso bend','right',15,False),('CHEST','Torso side bend','forward',12,False)]
    if preset=='WRIST':
        for side in ['L','R']:
            out += [(f'HAND_{side}',_fmt('{v0} Wrist twist', v0=side),'limb',50,True),
                    (f'HAND_{side}',_fmt('{v0} Wrist bend', v0=side),'forward',30,True),
                    (f'HAND_{side}',_fmt('{v0} Wrist tilt', v0=side),'up',30,True)]
    if not out:raise ValueError('Unknown motion preset')
    return out
