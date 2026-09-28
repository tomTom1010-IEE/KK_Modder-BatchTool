# Chocolat source bone profile

## Evidence and scope

The profile was checked against the Blender objects `Chocolat` (268 bones) and
`Chocolat_kaihen` (270 bones) on 2026-09-27. Each has 20 bound meshes, including
the supplied clothes, hair and avatar appendages. Inspection was read-only;
no scene object, mesh, weight, pose, selection or imported asset was edited.

`tests/fixtures/chocolat_rigs.json` records observed parent names and positive
weight-group membership. It contains no mesh geometry, textures or per-vertex
weight arrays. This is evidence for these imported variants, not a universal
VRChat naming convention or a runtime physics configuration.

## Rules and profile membership

`vrc_bone_rules.py` remains the source of structured rules. Its `VrcBoneRule`
fields and existing Shinano definitions are preserved.

- Shared names extend the existing `avatars` membership with
  `AVATAR_CHOCOLAT`: torso/head, shoulders, hands, feet, toes and eyes.
- Existing `UpperArm`, `LowerArm`, `UpperLeg`, `LowerLeg` dotted-side entries
  retain their generic membership and also belong to Chocolat.
- Compact finger names such as `ThumbProximal.L` and the observed breast names
  are registered with `avatars=(AVATAR_CHOCOLAT,)`. Shinano's spaced finger
  names, underscored limb names and `Breast_1.L` remain separate entries.
- A shared name does not guarantee the same parent. `Hand.L/R` follows
  `LowerArm.L/R` in Chocolat, while Shinano uses `Lower_arm.L/R`; the equivalent
  difference applies to `Foot.L/R`. `VRC_BONE_PARENT_OVERRIDES` records these
  alternatives without replacing the historical `parent` field.
  `vrc_bone_parents(name, avatar)` selects the profile-specific parent, and
  the role audit accepts only declared alternatives when no profile is given.

The new profile contains the union of observed body-related bones in the two
variants; membership does not assert that every variant contains every bone.
The full source hierarchy must still be checked at runtime.

## Breast chain evidence

Both imported rigs contain:

```text
Chest
  Breast_L_Root
    Breast_L.001
      Breast_L.002
        Breast_L.002_end
  Breast_R_Root
    Breast_R.001
      Breast_R.002
        Breast_R.002_end
```

On each side of each `Body_base` mesh, `.001` affects 788 vertices with a maximum
weight of 1.0, and `.002` affects 503 vertices with a maximum weight of about
0.210783. Both bones also weight `Bra`, `Shirt` and `SailorCollar`. The root and
end marker have no positive weights on any of the inspected bound meshes.
No pose constraints or armature drivers were present in either imported rig;
this does not describe external Unity/VRChat physics settings.

The root and two working bones are body helpers (`ROLE_ASSIST`) with breast
region, explicit side, body-replacement and graft-stop tags. Their weight
policy is `BODY / TORSO`, preserving each source bone's deformation contribution
and its own reference anchor. They are not tagged as Unity Humanoid slots and
are not copied as clothing bones. The unweighted end marker is `ROLE_ANCHOR /
REVIEW`, with a graft-stop tag; it is not granted a body weight budget merely
because the importer set `use_deform=True`.

## Clothing and variant differences

- `Body_base` has 55 positively weighted groups; `Body_base.001` has 43. All are
  covered by body policies. The separate head meshes each have three weighted
  groups (`Head`, `LeftEye`, `RightEye`); eye rules retain their existing review
  policy rather than being silently treated as torso clothing weights.
- The original has distal finger bones and `Toe.L/R`; kaihen does not. Its
  `*Intermediate.L/R_end` and `Foot.L/R_end` markers have no positive weights.
  These markers are protected body endpoints, not aliases of the missing
  distal/forefoot deformers. Missing influences must not be invented.
- All 254 shared bone names have identical parents between the imported rigs.
  The original has 14 unique names and kaihen has 16, including differences
  in eye/hair end markers. These are observed variants, not reasons to alter
  the common anatomy or overwrite either model.
- Skirt, sleeve, collar, ribbon and choker chains have clothing-specific weight
  membership. Hair, ears, wings and tail have their own mesh membership. These
  chains are not added to the body table or automatically declared dynamic;
  their retention and body-follow modes still require the existing review.

## Integration and remaining boundaries

As of 2026-09-28, source names are assigned shared anatomical slots by
`VRC_BODY_SEMANTICS` in `vrc_bone_rules.py`. `vrc_kk_mapping.py` maps those slots
to one common set of KK defaults. Spaced Shinano fingers and compact Chocolat
fingers, and the corresponding limb aliases, share the same target entries.
There is no separate Chocolat transfer algorithm. `VRC_MOTION_SEMANTICS` keeps
its existing macro-preset slots; adding mapping semantics does not add new
motion controls or budgets.

The six-budget scan, legacy body-weight mapping, beginner finger setup and
graft limb attachments consume this shared mapping. The legacy body-remap
operator retains its non-torso scope. Breast-root **attachment** defaults are
also derived from the source breast-chain tags and shared with Shinano, while
breast **weight/motion** mapping remains explicitly configured for both.
All previously mapped source names retain their previous target names.

Fixture-based Blender checks cover automatic mapping and configuration of all
non-breast weighted body bones in both Chocolat variants (51 and 39 groups).
The four remaining weighted breast groups in each variant retain the same
manual mapping boundary as Shinano. Full-scene source topology, target positive
weight admission and motion/collision acceptance are still separate checks.
The existing six-budget, optimization and four-influence layers are reused
without changing their numerical behavior.

The six-budget and shoe scanners consume `VRC_WEIGHT_POLICIES` generated from
these records. Graft exclusion now consumes the common `TAG_VRC_GRAFT_STOP`
set, including compact fingers and body endpoints; its historical variable
name `VRC_HUMANOID_BONES` does not make all exclusions Humanoid bones.

This change registers source anatomy and protects the graft boundary. It does
not invent a one-to-one breast-to-KK-bust correspondence or change numerical
budgets, optimizer objectives, mesh fitting or scene weights. Target weight
and motion mappings still need valid entries; target weight destinations must
have positive weights on the target body.

The earlier user screenshot uses `Breast_R_001`, `LowerArm_L` and other
underscore spellings. These exact spellings are absent from both current
imports. The shared [bone-name compatibility layer](bone-name-compatibility.md)
now accepts the controlled final-suffix variants against these canonical rules,
without adding duplicate avatar entries or renaming the scene. This does not
establish the cause of the importer's spelling change, validate a different
hierarchy, or authorize arbitrary punctuation substitutions. Exact binding
between mesh groups and scene bones remains required.

The source repository and Blender's installed add-on are separate copies.
Updating these files does not hot-reload the running add-on.
