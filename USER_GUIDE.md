# KK Modder BatchTool User Guide

[Project showcase](README.md) · [Technical report](docs/technical-report.md)

**Based on source version 0.2.17, September 20, 2026.** Updating the add-on does not automatically modify existing scene weights or repair earlier results.

The workflow walkthrough below describes the 0.2.17 snapshot. Version 0.2.24 provides English source labels and Simplified Chinese localization; see [localization notes](LOCALIZATION.md). Later MMD and collision-review additions are documented in the [0.2.20 workflow update](docs/WEIGHT_WORKFLOW_0_2_20_CN.md) (Chinese). Some control wording and panel organization have changed since this walkthrough.

## 1. Installation and entry points

The declared minimum is Blender 4.3. Local case studies used Blender 5.2; not every intervening version has been verified.

1. Download the appropriate package from [Releases](https://github.com/tomTom1010-IEE/KK_Modder-BatchTool/releases). To build from source, run `python tools/build_addon.py /path/to/kk_vrc_cloth_tools-0.2.24.zip`, replacing the output path with your preferred location. The builder includes the required bone-profile JSON files. Do not ZIP only the source package folder or install the entire repository ZIP.
2. Use **Edit → Preferences → Add-ons → Install from Disk…** and enable **KK/VRC Cloth Tools**. Reload the add-on or restart Blender after upgrading; check the installed version.
3. Press **N** in the 3D Viewport and open **KK/VRC Tools**.

| Panel order | Purpose |
|---|---|
| Garment Weights · Conservative Beginner Preset | Guided parameters with required region review |
| Dynamic Garment Weight Transfer | Six-category initialization, macro optimization, optional terminal refinement |
| Complex Flat-Shoe Weight Transfer | Native sampling, toe extension, continuity repair, and A/B separation refinement |
| Manual Editing | Bone grafting, chain editing, glove alignment, and utilities |
| Pre-export Dynamic Bone Cleanup | Protect KK body bones and clean complete non-body root chains |

MMD preparation uses a separate **model preprocess** tab.

### External Python for garment optimization

Six-category initialization and shoe processing do not require external OSQP. **Garment macro and terminal optimization** require an external Python interpreter with NumPy, SciPy, and OSQP. From the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-optimizer.txt
```

Expand **Runtime and Configuration Files** at the bottom of the garment panel. Point **External Python** to this environment's interpreter and click **Check Solver Dependencies**. The beginner panel also has **Python and Dependency Settings**. Leave **Dependency Directory (Optional)** empty when packages are already installed in that environment; it is intended for separately installed dependencies. Blender preprocessing and shoe processing do not require this external environment.

## 2. Prepare three inputs

| Input | Requirements |
|---|---|
| Original Garment / Original Shoe | Complete original weights and source rig; not a previous transfer result |
| Fitted Garment / Fitted Shoe | Static fitting and required dynamic-bone grafting completed; original vertex indices and topology preserved |
| Target Body | Bound to the target rig, with trustworthy body weights |

The original and fitted garment must have vertex correspondence; the source and target bodies may have different topology. Weight processing does not perform static fitting. Save the project first. Input meshes must be editable and must not share Mesh data. The standard optimizer requires a single Armature modifier and verifiable linear blend skinning.

Active shape keys, envelopes, Preserve Volume skinning, complex drivers or constraints, and animation require separate preparation or evaluation support. Do not delete them just to bypass checks. MMD preprocessing does not necessarily make an asset optimizer-ready.

## 3. Dynamic garments: beginner workflow

Use this branch for jackets and garments with secondary-motion attachments. A skirt with body-following attachment weights and a dynamic hem also belongs here, although this project has no completed skirt case study.

1. In **Garment Weights · Conservative Beginner Preset**, specify the three inputs and output directory. Choose upper-body, lower-body, full-body, or automatic motion coverage. Decide whether to preserve source finger influence according to the original design.
2. Click **① Apply Conservative Preset and Scan**.
3. Review every dynamic region. Use **Highlight Region**, optionally **Confirm This Chain as Retained Dynamic Bones**, and then **Confirm Region Mode**. If highlighting enters Edit Mode, press Tab to return to Object Mode.
4. Resolve uncertain roles, regions, and mappings. The preset does not automatically approve unknown bones as clothing dynamics.
5. Click **③ Compute → Validate → Create Copy**. This uses the detailed workflow's initialization, solver, and validation backends. Failed validation stops execution rather than writing a failed optimized result.
6. Inspect copies and reports, preview relevant poses, and save the `.blend`. Press Esc to cancel a running operation.

Terminal refinement is off by default. Before enabling **Continue with Terminal Refinement in the Specified Region**, configure its vertex scope, terminal poses, and allowed bones in the detailed panel.

### Review body-following patterns

| Mode | Source characteristics | Action |
|---|---|---|
| Uniform Body Following | Stable body share and internal semantic distribution in a dynamic region | Review, then initialize through semantic mapping |
| Attachment-Edge Gradient | Body influence decays from attachment to free region | Preserve shares and permit trusted native sampling |
| Needs Analysis | Insufficient evidence, overlapping modes, or another structure | Stop automatic processing; use per-vertex Agent analysis or manual treatment |

Classify observed weights, not part names such as ribbon or hem. Pure dynamic vertices retain zero body share. A stable base component combined with a different gradient is not automatically supported: `protected_components` remains unimplemented. Do not relabel a mixture to bypass review.

Select the chain root and inspect its actual weighted extent; individual selection of every bone is unnecessary. An unweighted branching organization node can produce several candidate chains. Check their extents before confirmation.

## 4. Dynamic garments: detailed workflow

### Stage 1 · Inputs and bone inspection

Specify the three inputs and click **Scan Bones and Dynamic-Root Regions**.

### Stage 2 · Review body and dynamic regions

Use **Confirm This Root Chain as Dynamic**, **View Mesh Region**, and **Region Mode Reviewed** for each region. Expand **Show Body Bones and Candidates** to correct roles. Source mappings and target-bone details have separate expandable sections. After role edits, click **Refresh Dynamic Regions After Role Changes**. Use **Add Missing Root Regions** to supplement the list and **Reclassify Patterns** to refresh statistical suggestions.

Target weight candidates must carry positive weights on the target body. Pose-control bones need not be weight recipients. Do not discard effective source body helpers merely because of their names, or classify source breast chains as clothing dynamics by default.

Under **Statistics and Advanced Region Settings**, capture the current vertex selection or restore root-chain scope. Finish with **Check Regions and Mappings**.

Target sampling does not automatically introduce finger influence. Explicitly enabled source fingers preserve mapped contributions. Disabled source finger shares return to the same-side non-finger budget without global renormalization changing dynamic shares.

### Stage 3 · Six-category transfer and macro optimization

1. Set **Run Output Directory**. Blender's native nearest-face interpolation is the default. Expand **Advanced Solver Parameters** to choose an existing target distribution or semantic mapping alone.
2. Click **Preview Six-Category Initialization**, inspect it, then **Write Initial Copy**.
3. Click **Generate Preset Poses (Add Missing Entries)**. Enable **Edit Pose Presets** to change motion coverage or individual poses. Axes and multi-bone target distribution are under **Advanced Pose Settings**. After **Preview Pose**, click **Restore Pose**.
4. Keep **Enable Collision-Constraint Iterations** as appropriate and click **Solve Macro Weights**.
5. Run **Independent Validation**, then **Write Macro Copy** after acceptance. Solver completion alone is not acceptance.

The six categories are torso including head/neck, left arm, right arm, left leg, right leg, and retained dynamics. Shares remain fixed per vertex. Dynamic weights and enabled finger contributions stay fixed; optimization redistributes remaining body weights within categories. Do not follow this workflow with legacy body-weight erasure in dynamic regions or all-group normalization.

### Stage 4 · Local terminal refinement in T-pose (optional)

Use this for confirmed wrist/hand problems, not every garment. Capture **Terminal Vertex Selection**, mark candidates as **Allow Terminal Optimization** in target-bone advanced settings, and mark relevant poses as terminal poses. Run **Solve Terminal Weights → Independent Validation → Write Terminal Copy**.

Unrelated macro controls remain at baseline, and weights outside the permitted scope are frozen. Transition-ring count and small-angle settings are under **Advanced Solver Parameters**.

## 5. Complex flat shoes

This branch targets the new foot's spatial weight distribution and motion-dependent separation rather than requiring the original shoe's kinematics. High-heel fitting through a target pose is outside the current workflow.

1. **Inputs and Scan:** specify the three inputs and click **Scan Bones and Lace-Root Regions**.
2. **Review Body and Lace Regions:** inspect each chain's side, role, and mixing pattern. Use **Confirm This Root Chain as Dynamic**, inspect its mesh region, and enable **Region and Shares Reviewed**. Unrecognized cases require per-vertex analysis and a documented conclusion in manual-analysis mode. Confirm **Use Target-Foot Spatial Distribution and Preserve Source Body/Dynamic Shares**.
3. **Directions, Extension, and Continuity:** scanning infers world directions from ankle, forefoot, and shin reference positions. If inference fails, **Manually Set Foot Bones and Directions** expands with a diagnostic. Review motion bones, up direction, and forefoot direction before using direction inference. These are not simply bone-local Y axes.
4. **Flat-Shoe Pose Presets and Optimization:** defaults normally suffice. Enable **Edit Pose Presets** to expose random count, weight, and seed. **Include Gap Optimization B in One-Click Run** controls the combined workflow.
5. **Execution and Results:** set the directory and click **Check Configuration**. Run **Generate A: Sampling and Continuity → Optimize B from A**, or **Run All (Keep Original Shoe)**. B resumes a valid A checkpoint without repeating sampling; changed inputs or checkpoints invalidate reuse.
6. Compare using **Original / A / B**, inspect RMS, and use **Open Run Report Directory**. Failed B validation leaves A available and prevents accepted-result writeback of B.

JSON is optional. **Configuration Files and Naming** provides import/export and copy prefixes. Review current objects and regions after importing.

| Setting | Default or behavior |
|---|---|
| Standard training | Seven poses, weight 1 each |
| Independent validation | Four poses excluded from fitting |
| Random auxiliary poses | Six poses, weight 0.15 each, seed 20260919 |
| Random ranges | Ankle ±15°, forefoot −8° to +12°, inclination ±6°; bounded combined amplitude |
| Total random weight | At most 20% of the standard total; higher counts may reduce per-pose weight |
| Long toe-box extension | Enabled; extends internal proportions without moving final vertices |
| Continuity strength / Candidate rings | 0.7 / 2 under **Advanced Sampling and Optimization Parameters** |
| Minimum trusted sample mass / Preserve-A strength | 0.01 / 0.1 under the same advanced section |

The whole-forefoot `toes` bone is not an individual-finger control. A shin control can receive weights only if supported by actual body groups; do not force weights onto an unweighted `cf_j_leg03`. Continuity repair does not connect opposite feet or bridge disconnected layers through spatial proximity. Pure dynamic laces retain zero body budget.

## 6. MMD preparation

Open **model preprocess → MMD Garment Preprocessing**:

1. Select the garment, click **Use Active Mesh**, and set a backup/result directory.
2. Click **1. Scan Cleanup Preview**. Expand **Retention Rules and Cleanup Preview** and review body bones, weighted bones, and dependencies. Unknown bones are retained by default; removals require review.
3. Click **2. Back Up and Create Pose Candidate**. Adjust the pose on the independent candidate rig. Do not edit mesh geometry, weights, or the rest skeleton at this stage.
4. Return to Object Mode, confirm the pose, and run **3. Bake T-Pose, Clean Up, and Validate**.
5. Inspect readiness. If constraint-sampling adaptation is still required, do not enter the standard optimizer. MMD preprocessing saves a result copy; garment and shoe workflows require an explicit `.blend` save.

Shape keys and SDEF are outside the first preprocessing implementation. Additional [MMD preprocessing notes](MMD_PREPROCESS_CN.md) are available in Chinese.

## 7. Manual editing, export cleanup, and Unity

**Manual Editing → Bone Setup** provides grafting, splitting, deletion, simplification, and parallel-chain merging. Preview or scan before applying a graft. Source body bones are not clothing dynamic chains. Legacy torso/breast mixing and body-weight erasure are not required stages of the new workflow.

Use **Pre-export Dynamic Bone Cleanup** on a separate export copy. Select one export rig and its meshes, or a bound mesh, and click **Automatically Scan Export Structure**. All bound meshes, including hidden ones, are scanned. Exact KK body-bone definitions protect body bones. A non-body root chain is retained if any node carries weights or has a recognized dependency. After review, click **Clean Selected Root Chains (Automatic Backup)**. Useful chains keep their unweighted intermediate nodes.

Blender checks cannot establish all Unity runtime dependencies. Review external physics configuration before export.

For the Unity companion, place [UnityBoneImplant.cs](UnityBoneImplant.cs) in `Assets/Editor/`. Open **Tools → KK Mods → Auto Bone Implant**, specify the model root, and use **Scan Preview → Apply Preview**. Your project must supply `BoneImplantProcess` and optional `DynamicBone`; the script does not include those libraries. Mark explicit roots in Blender with **Add _TOMDBR to Selected Bones**. Validate physics and collisions in the target runtime.

## 8. Results, saving, and troubleshooting

Garments produce initial, macro, and terminal copies; shoes produce A and an accepted B. Output directories contain configurations, snapshots, solver outputs, and validation reports. **Reports are not complete model backups. Save the `.blend` after processing.**

| Symptom | Action |
|---|---|
| Missing direction/random settings | Expand manual directions, pose editing, or advanced settings |
| Old Step 1–5 interface | Check installed path, version, and reload status; repository changes do not update Blender's installed copy |
| Unresolved region blocks processing | Inspect chain and per-vertex weights; do not arbitrarily approve a gradient or dynamic role |
| Source bones/configuration changed | Rescan and review; do not force stale signatures or A checkpoints |
| Positive budget without candidates | Check real body support and mappings; do not fill unweighted helpers |
| Solver unavailable | Check external Python and dependencies; shoes need no external OSQP |
| Solve completed but writeback blocked | Inspect validation; never edit `accepted` to bypass failure |
| Better A/B distance but remaining intersections | Check absolute counts and depths; non-worsening is not collision-free |
| Pure dynamic hem intersects body | Body fitting has no variables there; inspect static fitting, chains, or runtime collisions |

Acceptance covers sampled poses and configured collision objects, not every continuous motion, self-collision, clothing layer, or physics simulation. Inspect results in the target runtime.

## 9. Development and maintenance

UI and Agent calls share backends. Maintain definitions centrally in `bone_rules.py` for KK, `vrc_bone_rules.py` for VRC, and structured MMD rules.

The [technical report](docs/technical-report.md) describes the algorithms in English. Supplementary developer notes remain in Chinese: [six-category core](WEIGHT_FEATURES_CN.md), [optimizer](WEIGHT_OPTIMIZER_CN.md), and [shoe implementation](FLAT_SHOE_WORKFLOW_CN.md). For current navigation, use this guide rather than older screenshots or JSON-only instructions.
