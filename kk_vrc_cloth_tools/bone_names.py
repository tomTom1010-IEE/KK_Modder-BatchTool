"""Rig-independent, non-mutating compatibility for terminal bone suffixes.

Rule/profile data stays canonical. Resolve rule names to *actual* scene names
before building maps; never normalize weight dictionaries or rename datablocks.
Only the final .L/.R or .<three digits> separator has an underscore alias.
The Blender scene supplies a global default; standalone callers pass mode.
"""
import re
import sys

MODES = ('AUTO', 'DOT', 'UNDERSCORE')
_SUFFIX = re.compile(r'^(.*)([._])(L|R|[0-9]{3})$')


def mode(value=None):
    if value is None:
        bpy = sys.modules.get('bpy')
        scene = getattr(getattr(bpy, 'context', None), 'scene', None)
        value = getattr(scene, 'kkvrc_bone_name_mode', 'AUTO')
    if value not in MODES:
        raise ValueError('Unknown bone suffix mode: ' + str(value))
    return value


def alternate(name):
    """Return one spelling variant, keeping internal separators and digits."""
    match = _SUFFIX.fullmatch(name or '')
    if not match:
        return None
    stem, separator, suffix = match.groups()
    return stem + ('_' if separator == '.' else '.') + suffix


def _admitted(name, value):
    match = _SUFFIX.fullmatch(name or '')
    return bool(match and (value == 'AUTO' or match[2] == ('.' if value == 'DOT' else '_')))


def key(actual, known, name_mode=None):
    """Look up a scene spelling in a finite maintained vocabulary.

    Exact rule names always win, including in manual modes. The selected mode
    only restricts additional imported spellings. No fuzzy/case-fold matching.
    """
    value = mode(name_mode)
    if actual in known:
        return actual
    other = alternate(actual)
    return other if other in known and _admitted(actual, value) else None


def lookup(table, actual, default=None, name_mode=None):
    canonical = key(actual, table, name_mode)
    return table[canonical] if canonical is not None else default


def canonical(actual, known, name_mode=None):
    return key(actual, known, name_mode) or actual


def assert_unique(actual_names):
    """Reject same-inventory aliases even when one spelling is an exact hit."""
    names = set(actual_names)
    conflicts = sorted((n, alternate(n)) for n in names if alternate(n) in names and n < alternate(n))
    if conflicts:
        raise ValueError('Ambiguous bone suffix aliases; choose explicit distinct names before scanning: ' + str(conflicts))


def resolve(reference, actual_names, default=None, name_mode=None):
    """Resolve a profile/config reference to a unique actual scene name."""
    value = mode(name_mode)
    if not reference:
        return default
    other = alternate(reference)
    if other is not None and reference in actual_names and other in actual_names:
        raise ValueError('Ambiguous bone suffix aliases: ' + str((reference, other)))
    if reference in actual_names:
        return reference
    return other if other is not None and other in actual_names and _admitted(other, value) else default


def remap_table(table, source_names, target_names):
    """Resolve a finite legacy source -> [(target, factor)] table to real names."""
    assert_unique(source_names)
    assert_unique(target_names)
    return {resolve(src, source_names, default=src):
            tuple((resolve(dst, target_names, default=dst), value) for dst, value in targets)
            for src, targets in table.items()}


def rule_test(module, predicate, actual, *args):
    """Compatibility adapter for legacy KK predicates, leaving rule data pure."""
    return getattr(module, predicate)(canonical(actual, module.KK_STANDARD_BODY_BONES), *args)


def region_groups(module, actual_names, region, invert=False):
    return {n for n in actual_names if rule_test(module, 'is_transfer_region_bone', n, region) != invert}


def first(references, actual_names, default='', name_mode=None):
    for reference in references:
        found = resolve(reference, actual_names, name_mode=name_mode)
        if found is not None:
            return found
    return default


def matched(actual_names, known, name_mode=None):
    actual_names = set(actual_names)
    assert_unique(actual_names)
    return {n for n in actual_names if key(n, known, name_mode) is not None}


def side_to_dot(name, name_mode=None):
    """MMD's existing side-to-Japanese converter accepts the same suffix policy."""
    if name.endswith(('_L', '_R')) and _admitted(name, mode(name_mode)):
        return alternate(name)
    return name


def audit_roles(audit, rows, bones, roles, known):
    """Adapt a canonical-table audit without changing its table or real keys."""
    assert_unique(bones)
    assert_unique({n for row in rows for n in row})
    names = {n: canonical(n, known) for n in set(bones) | set(roles) | {n for r in rows for n in r}}
    reverse = {v: k for k, v in names.items()}
    result = audit([{names[n]: w for n, w in row.items()} for row in rows],
                   {names[n]: dict(b, parent=canonical(b.get('parent'), known)) for n, b in bones.items()},
                   {names[n]: role for n, role in roles.items()})
    for field in ('discarded_deform_bones', 'profile_parent_mismatches', 'unknown_weighted_names'):
        result[field] = [reverse.get(n, n) for n in result[field]]
    result['known_weighted_bones'] = {reverse.get(n, n): v for n, v in result['known_weighted_bones'].items()}
    return result
