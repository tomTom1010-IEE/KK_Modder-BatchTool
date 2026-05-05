# KK/VRC Cloth Tools

This toolset helps convert VRC clothing to a Koikatsu/KK armature workflow. It currently contains two parts:

- Blender add-on: `kk_vrc_cloth_tools`, used for bone grafting, vertex group remapping, risky-area weight mixing, fitted-clothing weight transfer, and armature topology export.
- Unity Editor script: `UnityBoneImplant.cs`, used after importing the FBX into Unity to automatically add `BoneImplantProcess` components, with optional `DynamicBone` setup.

This guide assumes you downloaded these files from a GitHub Release:

- Blender add-on archive, for example `kk_vrc_cloth_tools.zip`
- Unity script file `UnityBoneImplant.cs`

## Blender Add-On Installation

Requirements:

- Blender 4.3 or newer
- A prepared KK Armature and VRC/clothing Armature, or clothing meshes already bound to the target armature

Installation:

1. Open Blender.
2. Go to `Edit > Preferences > Add-ons`.
3. Click the top-right menu or `Install from Disk...`.
4. Select `kk_vrc_cloth_tools.zip` from the Release files.
5. Enable the add-on `KK/VRC Cloth Tools`.
6. In the 3D View, press `N` to open the sidebar, then open the `KK/VRC Tools` tab.

If Blender is using a Chinese UI language, the add-on will automatically display Chinese UI text.

## Blender Workflow

Use the tools in the order shown in the panel. For every step, run `Preview` or `Scan Preview` first, check the Blender Console report, then run `Apply`.

### Step 1 - Graft Clothes Physical Bones To KK

Purpose: graft custom clothing physical bones into the KK Armature.

Basic usage:

1. Select the KK Armature and the VRC/clothing Armature.
2. Choose a graft parent mode. `Waist` is the recommended default.
3. Click `Scan Preview` to inspect the bone roots that will be grafted.
4. Click `Apply`.

Notes:

- `Pelvis / Waist / High Waist` controls where unknown clothing roots attach to the KK body chain.
- For skirts, waist accessories, and similar clothing parts, try `Waist` first.
- Breast, torso, waist, and butt areas should not rely only on direct one-to-one body remapping. Use the later dedicated weight steps for those areas.

### Step 2 - Remap Low-Risk Body Groups

Purpose: rename low-risk VRC humanoid vertex groups to KK body bone names.

This step handles areas such as neck, head, arms, legs, fingers, feet, and toes. It intentionally does not process:

- `Hips`
- `Spine`
- `Chest`
- `Butt.L`
- `Butt.R`

Use Step 3 for those excluded areas.

### Step 3 - Mix Torso / Hip / Butt Weights

Purpose: distribute torso, waist, hip, and butt weights across the KK body chain to reduce clipping around the lower torso, waistline, and back hip area.

Modes:

- `Balanced`: recommended default. Distributes weights across `hips / waist01 / waist02 / spine / siri` bones.
- `Conservative`: uses fewer target bones. Try this if Balanced feels too soft or stretches too much.

Options:

- `Remove source groups after apply`: removes the original VRC source groups after applying. Recommended.
- `Normalize affected vertices only`: normalizes only edited vertices. Recommended.
- Smoothing options: smooth the newly mixed risky area into surrounding vertices for a softer transition.

### Step 4A - Breast Simple Remap

Purpose: remap `Breast_root / Breast_1 / Breast_2` to the KK bust chain.

Modes:

- `Simple J Chain`: direct one-to-one mapping.
- `Distributed J Chain`: distributes each VRC breast group into adjacent KK bust bones for a smoother transition.

Useful for fitted breast cloth, bras, and upper-body clothing that should follow the KK bust bones.

### Step 4B - Breast Local Mix

Purpose: preserve some surrounding body influence while transferring breast physical weights into KK bust bones.

Recommended default:

- `Distributed J Chain`
- `Breast influence = 0.70`
- `Body influence = 0.30`

If the breast edge has hard creases or harsh deformation, try 4B before using 4A.

### Step 5 - Transfer KK Body Weights To Fitted Clothes

Purpose: directly transfer weights from the KK body mesh to fitted clothing.

Best for:

- Underwear
- Bodysuits
- Socks
- Gloves
- Tight shirts or tights

Not recommended for:

- Skirts
- Ribbons
- Capes
- Cloth strips
- Areas mainly controlled by custom clothing physical bones

Basic usage:

1. Set `Source body mesh` to the KK body mesh.
2. Select the clothing meshes that should receive body weights.
3. Run `Preview` and check the affected vertex count.
4. Run `Apply`.

`Physical weight threshold` protects vertices controlled by physical clothing bones. Lower values are more conservative and are less likely to overwrite dynamic-bone areas.

### Utilities - Export Armature Topology JSON

Purpose: export the selected armature's bone topology to JSON. This is useful for checking hierarchy, maintaining the standard KK bone list, or debugging future scripts.

## Unity Script Installation

Requirements:

- Your Unity project already includes the Koikatsu/KK modding tools you use.
- The project can resolve the `BoneImplantProcess` type.
- If you want automatic Dynamic Bone setup, the project must also contain `DynamicBone`.

Installation:

1. In your Unity project, create or locate the `Assets/Editor` folder.
2. Put `UnityBoneImplant.cs` into `Assets/Editor`.
3. Wait for Unity to compile.
4. Open `Tools > KK Mods > Auto Bone Implant` from the Unity menu bar.

## Unity Workflow

1. Import the FBX exported from Blender.
2. Drag the imported clothing prefab or the top-level scene object into `Root Object`.
3. Click `Scan Preview`.
4. Check the Preview list. It should show entries like:

```text
CustomClothBoneRoot -> KKParentBone
```

5. Click `Apply Preview`.

The script adds `BoneImplantProcess` components to the `Root Object`, not to each bone object. Each component stores:

- `trfSrc`: the custom clothing bone root
- `trfDst`: the target KK standard parent bone

## Unity Dynamic Bone Options

To add Dynamic Bone components during the same pass, enable:

```text
Add/Update Dynamic Bone components after implant
```

Bind modes:

- `ImplantRoots`: uses the implant root itself as the Dynamic Bone Root.
- `FirstLevelChildren`: uses each immediate child of the implant root as a Dynamic Bone Root.

Common choices:

- Use `ImplantRoots` when the whole physical chain should move from the root.
- Use `FirstLevelChildren` when the root is only an attachment point and the real swinging chain starts from the next bone.

Keep `Skip existing Dynamic Bone roots` enabled to avoid duplicate Dynamic Bone components for the same root.

## Export And Import Notes

- Before exporting FBX from Blender, make sure the clothing mesh Armature modifier points to the final KK Armature.
- Seeing the FBX root rotated 90 degrees on X in Unity is usually caused by Blender/Unity coordinate conversion. If the internal bones, mesh, and bindings behave correctly, it is usually harmless.
- For fitted clothing, prefer Step 5 body weight transfer.
- For skirts, ribbons, bows, capes, and other dynamic structures, preserve the custom physical bones and add `BoneImplantProcess` plus `DynamicBone` in Unity.
- Before large weight changes, keep a backup Blender file so you can compare different modes.

## Recommended Full Workflow

1. Blender: import or prepare the KK model and VRC clothing.
2. Blender Step 1: graft clothing physical bones.
3. Blender Step 2: remap low-risk body weights.
4. Blender Step 3: process torso, waist, hip, and butt weights.
5. Blender Step 4A or 4B: process breast weights.
6. Blender Step 5: transfer KK body weights for fitted clothing.
7. Blender: export FBX.
8. Unity: import FBX.
9. Unity: use `Auto Bone Implant` to add `BoneImplantProcess`.
10. Unity: add `DynamicBone` if needed.

## Troubleshooting

- Blender add-on is not visible: make sure it is enabled, then press `N` in the 3D View and open `KK/VRC Tools`.
- `Preview` finds no objects: make sure you selected a mesh or armature, and that the mesh Armature modifier points to the correct armature.
- Unity cannot find `BoneImplantProcess`: make sure KoikatsuModdingTools / ModBoneImplantor is imported.
- Unity cannot find `DynamicBone`: disable automatic Dynamic Bone creation if your project does not include Dynamic Bone.
- Preview finds too few bones: disable the prefix filter, or confirm the clothing physical bones are actually used by a SkinnedMeshRenderer.
- Preview finds too many bones: enable the prefix filter, or check whether non-clothing objects are being detected as custom bones.
