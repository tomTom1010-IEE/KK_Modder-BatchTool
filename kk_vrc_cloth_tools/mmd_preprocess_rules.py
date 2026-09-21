"""Conservative asset-scoped bone dependency planning. No Blender dependency."""
import unicodedata


# Retention policy, NOT a weight-role classifier. Exact, finite conventions:
# unknown names are retained pending review, never inferred to be physics bones.
PROTECTED_BODY_NAMES = frozenset(
    ['下半身', '上半身', '上半身2', '首', '頭', '腰',
     '全ての親', 'センター', 'グルーブ', '両目', '左目', '右目']
    + [side + stem for side in ('左', '右') for stem in (
        '肩', '腕', 'ひじ', '手首', '足', 'ひざ', '足首', 'つま先',
        '肩P', '肩C', '腕捩', '腕捩1', '腕捩2', '腕捩3',
        '手捩', '手捩1', '手捩2', '手捩3', '足D', 'ひざD', '足首D', '足先EX',
        '足IK親', '足IK', 'つま先IK', '腰キャンセル',
        '親指0', '親指1', '親指2',
        '人指1', '人指2', '人指3', '中指1', '中指2', '中指3',
        '薬指1', '薬指2', '薬指3', '小指1', '小指2', '小指3')]
    + ['腰キャンセル左', '腰キャンセル右']
)
# Observed body extension in the project, not asserted to be an MMD standard.
PROTECTED_BODY_EXTENSIONS = frozenset(['上半身3'])


def names(value):
    return sorted({n.strip() for n in value.replace('\n', ',').replace('，', ',').split(',') if n.strip()})


def canonical(name):
    name = unicodedata.normalize('NFKC', name).strip()
    if name.endswith(('.L', '.R')):
        name = ('左' if name.endswith('.L') else '右') + name[:-2]
    # Common spelling variants, still exact matching (no prefixes/substrings).
    return name.replace('ＩＫ', 'IK').replace('足ik', '足IK').replace('先ik', '先IK').replace('肘', 'ひじ').replace('膝', 'ひざ').replace('人差指', '人指')


def protected_body(bones):
    protected = {}
    for b in bones:
        aliases = {canonical(n) for n in (b['name'], b.get('name_j', '')) if n}
        matched = aliases & (PROTECTED_BODY_NAMES | PROTECTED_BODY_EXTENSIONS)
        if matched:
            protected[b['name']] = sorted(matched)
    # Ambiguous aliases protect ALL matches; they do not justify choosing a
    # T-pose mapping or merging bones/weights.
    return protected


def arm_mapping(bones):
    aliases = {}
    for b in bones:
        for n in (b['name'], b.get('name_j', '')):
            if n: aliases.setdefault(canonical(n), set()).add(b['name'])
    result = {}
    for side, jp in [('L', '左'), ('R', '右')]:
        for key, stem in [('upper', '腕'), ('lower', 'ひじ'), ('hand', '手首')]:
            candidates = aliases.get(jp + stem, set())
            result[key + '_' + side] = next(iter(candidates)) if len(candidates) == 1 else ''
    return result


def plan(bones, weighted, pins=(), chains=(), excluded=(), preserve_tips=True, confirmed_removals=()):
    """Exclusions cannot override body protection, weights, pins or dependencies."""
    weighted, pins, chains, excluded = map(set, (weighted, pins, chains, excluded))
    confirmed_removals = set(confirmed_removals)
    table = {b['name']: b for b in bones}
    if len(table) != len(bones): raise ValueError('Duplicate bone names')
    children = {n: [] for n in table}
    for b in bones:
        if b.get('parent'):
            if b['parent'] not in table: raise ValueError('Missing bone parent: ' + b['name'])
            children[b['parent']].append(b['name'])
        for d in b.get('dependencies', []):
            if d not in table: raise ValueError('Missing bone dependency: ' + b['name'] + ' → ' + d)
    for b in bones:
        seen = {b['name']}; p = b.get('parent')
        while p:
            if p in seen: raise ValueError('Parent chain cycle: ' + p)
            seen.add(p); p = table[p].get('parent')
    for n in weighted | pins | chains | excluded | confirmed_removals:
        if n not in table: raise ValueError('Configured bone does not exist: ' + n)

    def subtree(root):
        found = set(); pending = [root]
        while pending:
            n = pending.pop()
            if n in found: continue
            found.add(n); pending.extend(children[n])
        return found

    blocked = set().union(*(subtree(n) for n in excluded)) if excluded else set()
    authorized = blocked | confirmed_removals
    keep = {}

    def add(n, why): keep.setdefault(n, set()).add(why)
    protected = protected_body(bones)
    for n, aliases in protected.items(): add(n, 'Body bone unconditionally protected: ' + ', '.join(aliases))
    for n in weighted: add(n, 'Actual garment weights')
    for n in pins: add(n, 'Explicit protection/anatomical reference')
    for root in chains:
        for n in subtree(root) - blocked: add(n, 'Confirmed complete chain: ' + root)
    if preserve_tips:
        # Only direct leaf children of weighted bones, not every descendant.
        for n in weighted:
            for child in children[n]:
                if not children[child] and child not in authorized and not table[child].get('helper'):
                    add(child, 'Candidate tip (may be overridden by excluded branches)')
    def close_dependencies():
        pending = list(keep)
        while pending:
            n = pending.pop(); b = table[n]
            deps = set(b.get('dependencies', []))
            if b.get('parent'): deps.add(b['parent'])
            for d in deps:
                if d not in keep: pending.append(d)
                add(d, 'Required dependency: ' + n)
    close_dependencies()
    # A missing name/role match is not evidence of irrelevance. Keep unknown
    # nodes, then close dependencies AGAIN: a retained unknown may depend on
    # a node that was explicitly proposed for deletion.
    review = set(table) - keep.keys() - authorized
    for n in review: add(n, 'Purpose unconfirmed; preserved pending review')
    close_dependencies()
    conflict = authorized & keep.keys()
    if conflict: raise ValueError('Removal request includes protected body bones, pinned bones, weighted bones, or required dependencies: ' + ', '.join(sorted(conflict)))
    return {'keep': {n: sorted(v) for n, v in sorted(keep.items())},
            'protected_body': protected,
            'review_required': sorted(review),
            'confirmed_removals': sorted(confirmed_removals),
            'remove': sorted(set(table) - keep.keys()),
            'weighted': sorted(weighted), 'excluded': sorted(blocked),
            'zero_weight_kept': sorted(keep.keys() - set(weighted))}
