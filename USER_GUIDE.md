# KK Modder BatchTool User Guide

[Project showcase](README.md) · [Technical report](docs/technical-report.md)

**Updated for source version 2.5.1, September 28, 2026**, including total-influence controls and the Stage 3 panel-drawing fix. Updating the add-on does not automatically modify existing scene weights or repair earlier results.

The garment execution controls below follow the current source UI. English labels have Simplified Chinese localization; see [localization notes](LOCALIZATION.md). Older screenshots and the historical [0.2.20 workflow notes](docs/WEIGHT_WORKFLOW_0_2_20_CN.md) may use different wording. Repository changes take effect in Blender only after updating the installed add-on and reloading it.

## 1. Installation and entry points

The declared minimum is Blender 4.3. Local case studies used Blender 5.2; not every intervening version has been verified.

1. Download the appropriate package from [Releases](https://github.com/tomTom1010-IEE/KK_Modder-BatchTool/releases). To build from source, run `python tools/build_addon.py /path/to/kk_vrc_cloth_tools-2.5.1.zip`, replacing the output path with your preferred location. The builder includes the required bone-profile JSON files. Do not ZIP only the source package folder or install the entire repository ZIP.
2. Use **Edit → Preferences → Add-ons → Install from Disk…** and enable **KK/VRC Cloth Tools**. Reload the add-on or restart Blender after upgrading; check the installed version.
3. Press **N** in the 3D Viewport and open **KK/VRC Tools**.

| Panel order | Purpose |
|---|---|
| Garment Weights · Beginner Preset | Guided parameters with required region review |
| Dynamic Garment Weight Transfer | Six-category initialization, macro optimization, optional terminal refinement |
| Complex Flat-Shoe Weight Transfer | Native sampling, toe extension, continuity repair, and A/B separation refinement |
| Manual Editing | Bone grafting, chain editing, glove alignment, and utilities |
| Pre-export Dynamic Bone Cleanup | Protect KK body bones and clean complete non-body root chains |

MMD preparation uses a separate **model preprocess** tab.

### Solver environment: automatic detection and one-click setup

Garment main and terminal optimization require external NumPy, SciPy, and OSQP.
Starting with **0.2.26**, solver setup is centralized in the **config → Solver Environment** sidebar panel:

1. The plugin checks existing environments automatically. **Detect automatically** repeats the check without downloading or installing anything.
2. If no working environment is available, click **Install isolated environment**. This downloads the setup tool and solver packages from PyPI, and obtains Python 3.12 through uv if a suitable interpreter is missing. Internet access is required; administrator access is not.
3. Wait for **Solver environment ready**. Installation runs in the background with progress, cancellation, and an installation log. A real numerical solve is checked before the new environment becomes active.

The managed environment is stored outside the add-on and survives plugin updates:
Windows `%LOCALAPPDATA%/KKModderBatchTool/solver`, macOS `~/Library/Application Support/KKModderBatchTool/solver`, or Linux `$XDG_DATA_HOME/KKModderBatchTool/solver` (default `~/.local/share`). Existing system and Blender Python installations are not modified. A failed or canceled replacement leaves the previous active environment intact; incomplete installation directories are not activated.

**Configure Python manually** keeps the existing interpreter/dependency-path workflow available. Dependencies may still be installed with `python -m pip install -r requirements-optimizer.txt`. Manual mode overrides automatic selection. Environments are detected in this order: validated managed environment, configured interpreter, then system Python candidates. No automatic download happens during detection.

Automatic installation has been tested on Windows x64, including the missing-Python path. macOS and Linux download selection is implemented but not yet end-to-end tested. Network failures can be diagnosed with **Open installation log**; retry after resolving connectivity. The installer uses [uv-managed Python environments](https://docs.astral.sh/uv/guides/install-python/).

Six-category initialization, preprocessing, manual tools, and shoes do not require this external environment. The installer is included in release ZIPs; Python and solver binaries are downloaded only when the user starts installation.

### Global bone suffix compatibility

**config → Bone Name Compatibility** provides one scene-wide setting, also shown beside the garment and shoe scan controls. It applies to source recognition (VRC and MMD), target bone lookup, and the supported mapping/grafting tools. It does not rename bones or vertex groups.

- **Automatic (. / _)** (default): accept exact maintained names, then try the alternate final suffix separator. Examples: `LowerArm.L` / `LowerArm_L`, `Breast_R.001` / `Breast_R_001`, and target `cf_j_hand_L` / `cf_j_hand.L`.
- **Period (.)**: keep exact maintained names valid; accept additional imported spellings only when their final separator is a period.
- **Underscore (_)**: keep exact maintained names valid; accept additional imported spellings only when their final separator is an underscore.

Only terminal `L`, `R`, and three-digit numeric suffixes are compatible. Internal separators, numeric values, capitalization, and unknown names are preserved. MMD's existing Japanese names and `name_j` recognition remain available; side suffix variants such as `腕.L` / `腕_L` use the same global policy. This is spelling compatibility, not a new anatomical or breast-to-bust mapping.

If both equivalent names exist in the same bone or vertex-group inventory, automatic scanning stops for disambiguation. The resolver never merges them. Bone/vertex-group binding inside each imported asset must still be valid in Blender; this option does not repair unbound groups. Rescan after changing the setting. Garment and shoe configuration exports record the mode; older files default to Automatic when imported. Importing the mode changes the shared scene setting, so it also affects other workflows in that scene.

The implementation is in [`bone_names.py`](kk_vrc_cloth_tools/bone_names.py), separate from VRC, MMD, and KK rule data. Numerical stages consume resolved real names; the six budgets, optimization objectives, and four-influence policy are unchanged. [Developer contract](docs/bone-name-compatibility.md).

## 2. Prepare three inputs

| Input | Requirements |
|---|---|
| Original Garment / Original Shoe | Complete original weights and source rig; not a previous transfer result |
| Fitted Garment / Fitted Shoe | Static fitting and required dynamic-bone grafting completed; original vertex indices and topology preserved |
| Target Body | Bound to the target rig, with trustworthy body weights |

The original and fitted garment must have vertex correspondence; the source and target bodies may have different topology. Weight processing does not perform static fitting. Save the project first. Input meshes must be editable and must not share Mesh data. The standard optimizer requires a single Armature modifier and verifiable linear blend skinning.

Active shape keys, envelopes, Preserve Volume skinning, complex drivers or constraints, and animation require separate preparation or evaluation support. Do not delete them just to bypass checks. MMD preprocessing does not necessarily make an asset optimizer-ready.

## 3. Dynamic garments: beginner workflow

Use this branch for jackets and garments with secondary-motion attachments. A skirt with body-following attachment weights and a dynamic hem also belongs here. The archived MMD skirt-outfit experiment provides limited cross-rig evidence; broader skirt-specific validation remains open.

1. In **Garment Weights · Beginner Preset**, specify the three inputs and output directory. Choose upper-body, lower-body, full-body, or automatic motion coverage. Decide whether to preserve source finger influence according to the original design.
2. Click **1. Apply conservative preset and scan**.
3. Review every dynamic region. Use **Highlight Region**, optionally **Confirm This Chain as Retained Dynamic Bones**, and then **Confirm Region Mode**. If highlighting enters Edit Mode, press Tab to return to Object Mode.
4. Resolve uncertain roles, regions, and mappings. The preset does not automatically approve unknown bones as clothing dynamics.
5. In **Runtime influence compatibility**, choose four or unlimited and leave dynamic compression off unless explicitly needed. Click **3. Solve → validate → create copies**. This uses the detailed workflow's initialization, solver, and validation backends. Failed validation stops execution rather than writing a failed optimized result. Preserved influence-limit exceptions are reported separately: a written copy can still require runtime review.
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

The on-screen section is **3 · Six-class transfer and main optimization**. It is a section box, not a collapsed header. If only its title is visible, follow the panel-error troubleshooting entry below.

#### Choose a total influence policy

The **Runtime influence compatibility** box is shared by the beginner, garment, and shoe panels. New configurations use **Four (body + dynamics + fingers)**; legacy saved configurations and imported JSON without this policy use **Unlimited (legacy)**. You can change either explicitly. **Allow approximate dynamic compression** defaults to off. Changing these settings invalidates prepared plans and shoe checkpoints; preview or generate A again.

| Control | How to use it |
|---|---|
| **Total influences per vertex → Four (body + dynamics + fingers)** | Use for a deployment that requires at most four bone weights. Includes every final positive body, dynamic, and enabled finger weight. |
| **Total influences per vertex → Unlimited (legacy)** | Keep the dense method when the actual importer/runtime permits it. Does not retroactively restore weights already reduced in another run; start again from the original complete source. |
| **Allow approximate dynamic compression** | Optional, default off; displayed in Four mode. Enable only to test resolving slot conflicts by approximating individual dynamic contributions. It does not guarantee that every conflict is solvable. |
| **Dynamic response tolerance / mesh span** | Displayed only when compression is enabled. Default 0.002 is a normalized displacement threshold, not an absolute distance or a percentage of weight to delete. |

For the project's stated deployment variants, select **Four** for the Unity 5.6 target and **Unlimited** for the Unity 2019.4.6 target configured to accept unrestricted influences. These are choices for those target setups, not a claim that every application using either Unity version has the same limit. There is no engine-version preset selector; verify the actual import and runtime settings separately.

Use **Scan influence counts** to inspect the latest result (or fitted input before a result exists), and **Select over-limit vertices** to inspect its exceptions in Edit Mode. Return to Object Mode before solving. Four is the combined total, not four body bones plus additional dynamic/finger bones. Tiny positive category budgets are not discarded to make the count pass.

1. Set **Run Output Directory**. Blender's native nearest-face interpolation is the default. Expand **Advanced Solver Parameters** to choose an existing target distribution or semantic mapping alone.
2. Click **Preview six-class initialization**, inspect it, then **Write initialization copy**.
3. Click **Generate preset poses (add missing entries)**. Enable pose-preset editing to change motion coverage or individual poses. Axes and multi-bone target distribution are under advanced pose settings. After **Preview pose**, click **Restore pose**.
4. Choose the collision policy and contact-constraint iterations as appropriate, then click **Solve main weights**.
5. Run **Independent validation**, then **Write main copy** after acceptance. Solver completion alone is not acceptance.

The six categories are torso including head/neck, left arm, right arm, left leg, right leg, and retained dynamics. Shares remain fixed per vertex. By default, each dynamic weight and enabled finger contribution stays fixed; optimization redistributes remaining body weights within categories. With four influences enabled, the plugin selects feasible bone combinations before fitting, retaining a separate dense initialization reference. Do not follow this workflow with legacy body-weight erasure, all-group normalization, or unreviewed global top-four cleanup.

If fixed dynamics/fingers and positive body categories cannot fit, those vertices remain unchanged. Other feasible vertices continue. `RUNTIME_REVIEW_REQUIRED` means the copy is **not** strictly four-influence compatible; collision review does not waive that condition. `STRICT_FOUR` reports numerical support compatibility only, not a Unity import test. `UNLIMITED` retains the dense workflow.

Optional dynamic compression only targets slot conflicts. It reserves body/finger slots, rescales retained dynamic weights within the original dynamic total, and checks independent bend/twist probes. Fingers remain fixed. Missing or failed probe/collision evidence prevents accepted compressed writeback; a shoe candidate can fall back to unchanged exception vertices. The tolerance is normalized by garment span and needs asset review. See [implementation details and report fields](docs/influence-limits.md).

**Read the result before export.** Scan the final object again after manual weight edits or a policy change; the current UI's previous scan text is not an automatically refreshed certificate. `STRICT_FOUR` checks the weight count, while motion/contact acceptance is a separate result and Unity runtime validation is not automated. `RUNTIME_REVIEW_REQUIRED` means some unchanged vertices still exceed four; inspect them with **Select over-limit vertices**. Do not use global Normalize All or a blind Limit Total cleanup to hide them. Either review the exceptions, test optional compression and revalidate, or use the unlimited target when that deployment permits it.

**Expected cost and fidelity.** In the two-jacket [controlled dry run](docs/influence-limit-benchmark.md), unlimited output matched the old weights exactly. Four-mode macro solves took about 1.8–2.0 times as long; the complete numeric path took 53 and 65 seconds in single runs. The open jacket's terminal RMS increased 8.68%, despite slightly better macro RMS. These are case measurements, not a progress estimate or a quality guarantee for other assets. The current UI shows a general running message; per-stage diagnostics are in `solver.log`, not a new progress dashboard. Press Esc to cancel a running solve.

### Stage 4 · Local terminal refinement in T-pose (optional)

Use this for confirmed wrist/hand problems, not every garment. Click **Capture terminal vertex selection**, mark candidates as **Allow Terminal Optimization** in target-bone advanced settings, and mark relevant poses as terminal poses. Run **Solve terminal weights → Independent validation → Write terminal copy**.

Unrelated macro controls remain at baseline, and weights outside the permitted scope are frozen. Transition-ring count and small-angle settings are under **Advanced Solver Parameters**. Terminal fitting obeys the same total limit and local correction bounds. UI-generated terminal runs additionally validate the earlier macro holdouts, without using those holdouts for fitting.

## 5. Complex flat shoes

This branch targets the new foot's spatial weight distribution and motion-dependent separation rather than requiring the original shoe's kinematics. High-heel fitting through a target pose is outside the current workflow.

1. **Inputs and Scan:** specify the three inputs and click **Scan Bones and Lace-Root Regions**.
2. **Review Body and Lace Regions:** inspect each chain's side, role, and mixing pattern. Use **Confirm This Root Chain as Dynamic**, inspect its mesh region, and enable **Region and Shares Reviewed**. Unrecognized cases require per-vertex analysis and a documented conclusion in manual-analysis mode. Confirm **Use Target-Foot Spatial Distribution and Preserve Source Body/Dynamic Shares**.
3. **Directions, Extension, and Continuity:** scanning infers world directions from ankle, forefoot, and shin reference positions. If inference fails, **Manually Set Foot Bones and Directions** expands with a diagnostic. Review motion bones, up direction, and forefoot direction before using direction inference. These are not simply bone-local Y axes.
4. **Flat-Shoe Pose Presets and Optimization:** defaults normally suffice. Enable **Edit Pose Presets** to expose random count, weight, and seed. **Include Gap Optimization B in One-Click Run** controls the combined workflow.
5. **Run and Results:** set the directory and click **Check configuration**. Run **Build A: sampling and continuity → Optimize B from A**, or **Run all (preserve original shoes)**. B resumes a valid A checkpoint without repeating sampling; changed inputs or checkpoints invalidate reuse.
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

The shoe compatibility box constrains the final body-plus-lace weights. A retains a dense reference, selects a permitted support, and repeats continuity repair within it; B uses that support throughout projection. Exception rows remain frozen. `influence-support.json` records A's decisions, and `report.json` includes full-mesh A/B counts. A field result still requires ordinary geometric/visual inspection.

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
| Stage 3 shows only its title; shoe controls may also stop drawing | This is not a foldout. Install the current 2.5.1 source patch and reload/restart Blender. An earlier draw callback tried to write `influence_version` during drawing, producing `Writing to ID classes in this context is not allowed`; the patch makes drawing read-only. Do not clear your configuration to work around it. |
| An old file unexpectedly defaults to Four after a partial hot reload | Check the actual installed package and perform a complete reload/restart so the saved-configuration migration callback is registered. Review the policy before preparing weights. |
| Solve succeeded but `RUNTIME_REVIEW_REQUIRED` remains | Inspect unchanged over-limit vertices. Motion/contact acceptance does not certify four-influence compatibility. |
| Scan still describes a previous object or weights | Run **Scan influence counts** on the current workflow result again; inspect the object name in the report. |
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
