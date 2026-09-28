# Global bone-name suffix compatibility

`kk_vrc_cloth_tools/bone_names.py` is the shared, non-mutating adapter. Neither `vrc_bone_rules.py` nor `bone_rules.py` stores importer aliases. Existing avatar membership, roles, hierarchy, and semantic mappings remain canonical.

## Resolution contract

1. Match an exact known rule name first.
2. For a maintained terminal `L`, `R`, or three-digit numeric suffix, try changing only the last `.` / `_` separator. Do not strip the suffix, normalize arbitrary underscores, fold case, or infer unknown bones as body/dynamic.
3. Manual `DOT` / `UNDERSCORE` modes restrict **additional actual spellings**; exact canonical names remain valid. `AUTO` accepts both.
4. Validate each real inventory before scanning or mutation. `Hand.L` and `Hand_L` in one rig are ambiguous even if one is an exact rule hit. Source and target inventories are checked separately.
5. Resolve canonical target/reference names back to unique **actual scene names** before constructing weight maps or pose controls. Weight arrays and vertex indices are never normalized by name.

For example, `Breast_R.001` matches `Breast_R_001`; `Breast_R.002` remains a different bone. `Something.L.001` can match `Something.L_001`, but not `Something_L_001`: multiple-separator conversion is deliberately outside this contract.

## API and integration

`key(actual, known, name_mode)` returns a canonical rule key; `lookup(table, actual, ...)` returns its value. `resolve(reference, actual_names, ...)` returns the real scene name. `assert_unique(names)` checks same-inventory spelling collisions. `audit_roles(...)` adapts canonical hierarchy/role audits and returns real names in diagnostics.

Standalone callers can explicitly pass `AUTO`, `DOT`, or `UNDERSCORE`. Inside Blender, omitted modes use `Scene.kkvrc_bone_name_mode`; outside Blender, they default to `AUTO`. The UI is defined separately in `bone_names_ui.py`, under **config → Bone Name Compatibility** and on scan panels. Garment and shoe configuration JSON includes `bone_name_mode`. Changing it invalidates preparation/checkpoints; rescan to refresh automatic suggestions.

Consumers include garment source/target recognition, semantic/finger initialization, dynamic root safety checks, graft attachment lookup, shoe target presets, MMD convention/asset recognition and preprocessing, and legacy body/breast/torso mapping and KK body safety predicates. Explicit user-configured scene references still must identify existing bones. This layer does not transplant a saved vertex mask or configuration between independently imported meshes.

MMD Japanese `name_j` and the existing side-name conversion are retained. Semantic alias conflicts remain REVIEW. Suffix compatibility cannot invent a missing anatomical mapping, repair a group's missing Blender bone binding, or settle body-versus-dynamic ownership for an unrecognized chain.

## Verification

`tests/test_bone_names.py` checks finite alias matching, manual modes, exact names, numeric identity, collisions, unchanged rule vocabularies, MMD recognition, and role/hierarchy audit adaptation. `tests/test_bone_names_blender.py` uses factory-startup scenes to verify Chocolat-like underscore source names with period-suffix KK targets, six-budget writeback using only actual target names, MMD scanning, breast graft protection, manual selection, collision preflight, and shoe/legacy mapping entry points. No test opens a production asset.
