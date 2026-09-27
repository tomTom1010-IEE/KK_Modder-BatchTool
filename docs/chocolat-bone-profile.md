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
imports. They are not silently normalized: confirm their actual hierarchy and
binding before adding an explicit alias profile. A screenshot alone does not
establish that every punctuation substitution preserves bone identity.

The source repository and Blender's installed add-on are separate copies.
Updating these files does not hot-reload the running add-on.
