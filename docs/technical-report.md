# Garment Skinning Transfer with Semantic Influence Budgets

**KK Modder BatchTool — Technical Report**  
Implementation snapshot: **0.2.17** · September 20, 2026  
Project: [tomTom1010-IEE/KK_Modder-BatchTool](https://github.com/tomTom1010-IEE/KK_Modder-BatchTool)

[Project page](../README.md) · [User manual](../USER_GUIDE.md)

**September 21 extension:** the [VRC/MMD performance showcase](performance-showcase.md) adds the later constraint-aware MMD skirt-outfit experiment and its collision-review qualifications. The implementation discussion below retains its September 20 snapshot; references to untested skirts describe that earlier snapshot.

*A short implementation report, not a peer-reviewed publication. The notation and section structure follow conventional graphics papers; the method is distinct from SSDR.*

## Abstract

Transferring a garment to a different character requires reconciling a new body shape with an existing skinning design. Purely spatial transfer can assign arm influence to a nearby collar, overwrite a secondary-motion attachment, or produce discontinuous weights on an extended shoe. We describe a constrained workflow that preserves per-vertex semantic influence budgets while adapting the distribution within each body region. A first formulation transports source garment motion through paired rest geometry and anatomical frames, then fits target body weights with a sparse quadratic program. A second formulation targets flat shoes: native body-weight samples are extended and regularized over the shoe surface, followed by optional pose-based separation refinement. Retained dynamic weights and selected source finger contributions remain fixed. Independent pose evaluation, body-support checks, and collision diagnostics gate writeback. Local jacket and shoe case studies illustrate the implementation; they do not establish generalization or superiority over existing skinning methods.

**Keywords:** skinning transfer; garment retargeting; semantic constraints; quadratic programming; secondary-motion attachments.

## 1. Introduction and related work

An authored garment encodes more than a surface-to-skeleton association. Its weights determine how much a vertex follows the body and how much remains controlled by clothing bones. When the body and skeleton change, replacing all weights discards that allocation. Conversely, renaming the old groups does not reproduce the target body's distributed deformation.

We separate two questions: **how much influence belongs to each semantic region**, and **which target bones distribute that influence**. The former is inherited from the source; the latter is estimated for the target. Spatial proximity supplies initialization rather than unrestricted semantic authority.

SSDR recovers bone transformations and a sparse convex weight map from example deformations through alternating optimization [1]. Our skeletons and sampled transforms are given. We solve for a restricted subset of weights, preserve source influence budgets, and do not infer bones or impose SSDR's sparse-bone decomposition model. Bounded biharmonic weights demonstrate smooth constrained influence fields [2]; our shoe branch instead regularizes a surface graph initialized by Blender's native transfer. We do not implement a volumetric biharmonic solve. The garment quadratic subproblems use OSQP [3].

The contribution of this implementation is the integration of semantic conservation, task-dependent fitting objectives, and guarded writeback into an inspectable transfer workflow. We do not claim a new general-purpose skinning decomposition algorithm.

## 2. Inputs and semantic invariants

Let $x_i^s$ and $x_i^t$ denote the original and fitted garment rest vertices. Their topology and indices correspond; the two body meshes need not share topology. Let $w_{ij}^s$ be the original effective weights and $T_j^p$ the fixed target skinning transform of bone $j$ at pose $p$. Target linear blend skinning is

$$
y_i^p(W)=\sum_j w_{ij}T_j^p\bar{x}_i^t,
\qquad w_{ij}\geq0,
$$

where homogeneous notation is used and the spatial coordinates are retained. Static fitting is an input, not an optimization variable.

### 2.1 Roles and six budgets

Every source influence is reviewed as body, retained dynamic, explicitly discarded, or non-deforming. Effective body helper bones must not be silently discarded. A non-Humanoid name is not evidence that a bone belongs to clothing physics.

The six categories are torso (including head/neck), left arm, right arm, left leg, right leg, and retained dynamic bones. For valid source body and dynamic sets $\mathcal B_s$ and $\mathcal D_s$, define

$$
s_i=\sum_{j\in\mathcal B_s\cup\mathcal D_s}w_{ij}^s,
\qquad
b_{ir}=\frac{\sum_{j\in\mathcal C_r^s}w_{ij}^s}{s_i}.
$$

Unweighted vertices require review; division by zero is not treated as zero body influence. The target must satisfy

$$
\sum_{j\in\mathcal C_r^t}w_{ij}=b_{ir}
\quad\text{for each vertex and category}.
$$

Thus a collar with zero source arm budget cannot acquire arm weights through a nearby sleeve. Dynamic weights are preserved individually, after valid-source normalization and the approved correspondence, rather than merely preserving their total. The current optimization adapter retains dynamic bone names.

**Body-bone admission is asymmetric.** Source evaluation retains all effective deformation contributions. Target body weights may be assigned only to bones with positive weights on the target body, with clothing dynamics admitted separately. A control bone can drive a test pose without being an admissible weight recipient.

### 2.2 Following patterns and fingers

Dynamic-root masks are obtained from actual source weights and optionally refined by explicit vertex selections. The supported garment patterns are uniform body following and attachment-edge decay. Statistical suggestions examine normalized body shares, internal body distributions, connected components, and decay versus topological distance. Suggestions require review; variance alone does not identify a physical mode.

A stable per-bone following component superimposed on a different gradient is not automatically resolved. The reserved `protected_components` interface remains unimplemented. Such a region requires per-vertex analysis or manual treatment before automatic transfer.

Finger sampling is filtered separately from the six categories. Explicitly enabled source fingers reserve their original normalized contributions and map to corresponding target fingers; the residual same-side body budget is then distributed. Disabled source fingers require an explicit same-side non-finger redistribution. This prevents new finger influence without changing dynamic shares. Whole-forefoot bones are not treated as individual fingers.

## 3. Garment response fitting

### 3.1 Initialization

Body samples are generated on temporary meshes with Blender's native `POLYINTERP_NEAREST` vertex-group transfer. A reviewed uniform-following region favors semantic mapping; an edge-gradient region can use trusted body sampling. Samples are normalized within their allowed category and multiplied by its residual budget. Weak or missing category support invokes a reviewed mapping rather than amplifying negligible samples. Candidate admission and selected finger reservations are applied before optimization.

### 3.2 Transporting motion across body proportions

World-space source positions are not suitable regression targets when limbs and garment proportions differ. For each garment vertex, the implementation fits a local rest-geometry Jacobian $J_i$ from corresponding incident edges and normal information. A regularized skeleton prior is used when the local map is degenerate, reflected, or outside the allowed scale range.

Let $H_i^{s,p}$ and $H_i^{t,p}$ be rigid source and target anatomical frames; their rotation blocks are $R_i^{s,p}$ and $R_i^{t,p}$. Define

$$
q_i^{s,p}=(H_i^{s,p})^{-1}\bar y_i^{s,p},
\quad q_i^{t,0}=(H_i^{t,0})^{-1}\bar x_i^t,
\quad A_i=(R_i^{t,0})^T J_iR_i^{s,0}.
$$

Using the spatial coordinates of $q$, the target reference is

$$
\widehat y_i^p=H_i^{t,p}
\begin{bmatrix}
q_i^{t,0}+A_i(q_i^{s,p}-q_i^{s,0})\\1
\end{bmatrix}.
$$

Only the source local motion residual is transported. In particular, $\widehat y_i^0=x_i^t$: sculpted target rest geometry is preserved exactly. An anatomical reference anchor may be a helper bone's parent, but source deformation still uses that helper bone's own evaluated transform.

### 3.3 Constrained weight solve

For pose weights $\alpha_p$, vertex weights $\omega_i$, a residual scale $\ell$, and initialization $W_0$, the body-weight objective is

$$
E(W)=\sum_{p,i}\frac{\alpha_p\omega_i}{\ell^2}
\|y_i^p(W)-\widehat y_i^p\|^2
+\lambda\|W-W_0\|_F^2
+\mu\|L(W-W_0)\|_F^2.
$$

Here $L$ is an edge-incidence operator over the chosen smoothing graph. The regularizer smooths **corrections**, not the source dynamic budget. Nonnegativity, category sums, fixed dynamic/finger weights, candidate masks, and trust bounds constrain the solve. With transforms and references fixed, this is a sparse convex quadratic program. Vertices are coupled through graph regularization and contact samples; this is not a collection of independent unconstrained regressions.

When enabled, a sequential contact pass builds local linearized inequalities against posed body surfaces. Samples can include vertices and barycentric edge/face locations. Fixed contacts that cannot be corrected without violating preserved weights are reported. These subproblems do not provide a global collision-free guarantee.

### 3.4 Terminal refinement

A second optional stage starts from the accepted macro solution. Only reviewed endpoint controls move from the neutral body pose. A selected vertex core, transition rings, allowed same-side body bones, and per-vertex correction limits restrict the solve. The exterior is frozen. This stage addresses local wrist/hand response without re-fitting unrelated macro motion; it is not required for every garment.

An ordinary skirt with an attachment gradient and a dynamic free hem is a prospective lower-body application of this garment formulation. No shoe-style distance objective is required merely because the garment is a skirt, and no skirt evaluation is claimed here.

## 4. Flat-shoe spatial fitting

Large toe-box extensions can make source motion preservation an unsuitable primary objective. The shoe branch keeps the original body/dynamic allocation but estimates the body's internal distribution from the target foot.

### 4.1 Extended native samples and graph repair

For a side with body share $b_i$, let $p_i$ be its conditional body proportions, so $w_{ij}=b_ip_{ij}$ and $\sum_jp_{ij}=1$. Vertices with exactly zero body share are excluded. A query beyond the forward extent of the weighted target-foot surface is projected back along the reviewed forefoot direction before native transfer. This extends the sampled field without moving the actual shoe. Insufficient sampling elsewhere stops for review rather than silently producing unweighted vertices.

The field-only result A minimizes a graph/data energy of the form

$$
E_A(P)=\sum_i c_i\|p_i-p_i^0\|^2
+\eta\sum_{(i,k)\in\mathcal E}\|p_i-p_k\|^2,
\quad p_i\geq0,\quad\mathbf1^Tp_i=1.
$$

Confidence $c_i$ decreases with separation and local disagreement. The graph follows same-side mesh edges in nonzero-body scope; it does not connect nearby layers by spatial KNN. Candidate support starts at native nonzero samples and expands through a bounded number of topology rings. This prevents globally admissible but locally unobserved knee bones from entering shoe weights. Projected Jacobi updates preserve the simplex and stop on an iterate-change tolerance.

### 4.2 Optional pose-based separation refinement

Each vertex receives a reference point $a_i^p$ on a corresponding posed body triangle, defined by fixed rest barycentric coordinates, and a triangle frame $F_i^p$. The fitted rest offset is $o_i=(F_i^0)^T(x_i^t-a_i^0)$. The transported reference is $g_i^p=a_i^p+F_i^po_i$.

Result B fits a quadratic offset surrogate,

$$
E_B(P)=\sum_{p,i}\alpha_pc_i'
\|D(F_i^p)^T(y_i^p(P)-g_i^p)/\ell_i\|^2
+\lambda_B\|P-P_A\|_F^2
+\mu_B\|LP\|_F^2,
$$

where the current implementation uses

$$
D^T D =
\begin{bmatrix}
0.03 & 0 & 0 \\
0 & 0.03 & 0 \\
0 & 0 & 1
\end{bmatrix}.
$$

Normal separation dominates; weak tangential terms discourage sliding. Remote vertices receive lower reference confidence. Dynamic weights and body budgets stay fixed. A projected-gradient solver with a conservative Hessian/graph bound handles the simplex and candidate constraints using NumPy. Convergence is an operational iterate-change criterion, not a reported global optimality certificate.

This fixed-reference quadratic is **not** exact minimization of nearest-surface distance. Independent validation re-queries actual posed body surfaces. Shoe collisions currently act as acceptance gates, not active collision-repair constraints. A pre-existing collision can remain even when B does not worsen A.

### 4.3 Pose preset

Seven standard poses train ankle flexion at ±20°, mirrored side inclination at ±10°, forefoot flexion at +18°/−12°, and combined ankle +12° with forefoot +10°. Four separate validation poses are neutral, (+13°, +7°), (−14°, −8°), and (+5°, +11°, mirrored 7° inclination). Axes are constructed from reviewed anatomical directions, not copied bone-local Euler axes.

The current preset optionally adds six reproducible random training poses with weight 0.15 each, versus 1 per standard pose. Per-side ranges are ankle ±15°, forefoot −8° to +12°, and inclination ±6°. Compound samples are contracted toward neutral to satisfy an ellipsoidal bound. Total auxiliary weight is capped at 20% of the standard total; increasing count can lower the effective per-pose weight. Seed, generated controls, and actual weights are saved. Validation poses are not added to training.

## 5. Implementation and acceptance

The Blender adapter checks topology, bone admission, state signatures, and supported LBS conditions. Numerical source/target skinning is compared with Blender evaluation before trusting motion references. Garment subproblems run in an external NumPy/SciPy/OSQP process; shoe iterations use Blender's NumPy. UI and scripted calls share these backends.

Acceptance requires more than a solver status: budget and fixed-weight errors, motion or separation metrics, selected-scope invariants, and collision diagnostics are evaluated independently. Collision checks include triangle crossings and oriented side tests at vertices, edge midpoints, and face centers. Their reliability depends on usable body surface orientation. Only accepted optimized candidates are written to new copies; original inputs and temporary poses are checked for restoration. Shoe A checkpoints permit later B refinement without repeating native sampling, subject to stale-state checks.

An Agent can inspect uncertain roles, review region masks, propose mappings, and configure candidates or poses. It does not replace conservation constraints or independently validated writeback. Unsupported mixture patterns require explicit analysis; changing a statistical label is not a solution.

## 6. Local case studies

The following values were read from saved development reports. They are historical case runs, not a fresh benchmark of every change through 0.2.17. Coordinates are in scene units, not an asserted physical unit. Different rows use different scopes and objectives and must not be compared as a single aggregate score.

| Case | Evaluation scope | RMS before | RMS after | Relative reduction |
|---|---|---:|---:|---:|
| Closed jacket, macro | 8,885 vertices, held-out response | 0.0021501803 | 0.0020941063 | 2.61% |
| Closed jacket, terminal | 1,514 selected vertices, held-out response | 0.0046159550 | 0.0024355355 | 47.24% |
| Flat shoes, A → B | Body-influenced vertices, four held-out poses | 0.0006319864 | 0.0006004512 | 4.99% |

The closed-jacket example included an explicit within-torso nipple-to-bust sampling policy; the response objective was not a body-shape-editing benchmark. Its terminal stage has different poses and normalization/scope from its macro stage. The source-LBS maximum discrepancies recorded by the two validations were approximately $3.95\times10^{-7}$ and $2.87\times10^{-7}$.

The shoe pair contains 24,082 vertices. Each side had 153 vertices beyond the sampled foot's forward boundary. A reduced the recorded mean squared neighbor-proportion difference by approximately 45.3% on each side. B passed all four reported validation poses with zero detected in-scope triangle crossings and penetrating samples. Actual body-budget writeback error was at most $4.47\times10^{-8}$; dynamic-weight error was at most $2.98\times10^{-8}$. Geometry was unchanged. These figures come from the standard-only seven-pose run, **before** random auxiliary poses were introduced.

Provenance: `close-no-bnip/stage1/validation.json`, `close-no-bnip/stage2/validation.json`, and `shoe-transfer/flat-round-02/{report.json,actual-writeback-audit.json}` in the local test archive. The repository includes an [extracted measurement summary](data/case-study-summary.json), not the third-party asset files or full private scene archive. The [shoe example configuration](../examples/flat_shoe_neon_vertex.json) now enables the later random preset; exact historical reproduction requires the archived configuration, including its original world axes and disabled auxiliary sampling. Automatic direction inference in the newer UI can change those axes. Public summary numbers alone are not a reproducible asset benchmark.

## 7. Limitations and future work

The garment branch assumes paired original/fitted garment vertices and fixed, verifiable skinning transforms. Active shape keys, unsupported constraints/drivers, SDEF, envelopes, and dual-quaternion/preserve-volume behavior require separate adapters. More body segments can improve the available distribution, but do not remove semantic ambiguity or pose-retargeting uncertainty.

Discrete poses cannot certify continuous-time collision avoidance. Pure dynamic regions are excluded from body-weight fitting; secondary-motion inertia, damping, runtime collisions, self-collisions, and other clothing layers are not reconstructed by this optimizer. Fixed dynamic contributions can make a contact infeasible. Weight cleanup that enforces a later bone-count cap would require revalidation; the current method does not promise SSDR-style sparsity.

Stable-plus-gradient protected components, high-heel pose transfer, explicit links between disconnected layers, and skirt-specific evaluation remain future work. The random shoe preset is implemented and tested for reproducibility and bounds, but no accuracy gain from it is established by the reported case studies. There is no controlled baseline study, runtime scaling experiment, or claim of state-of-the-art performance.

## 8. Code correspondence

| Component | Implementation |
|---|---|
| Budget/finger planning and Blender writeback | [weight_features.py](../kk_vrc_cloth_tools/weight_features.py), [weights_features.py](../kk_vrc_cloth_tools/weights_features.py) |
| Roles and root-region review | [vrc_bone_rules.py](../kk_vrc_cloth_tools/vrc_bone_rules.py), [workflow_regions.py](../kk_vrc_cloth_tools/workflow_regions.py), [region_patterns.py](../kk_vrc_cloth_tools/region_patterns.py) |
| Rest transport and garment QP | [weight_optimizer.py](../kk_vrc_cloth_tools/weight_optimizer.py), [weights_optimization.py](../kk_vrc_cloth_tools/weights_optimization.py) |
| Independent garment validation | [optimizer_validation.py](../kk_vrc_cloth_tools/optimizer_validation.py), [optimizer_scope.py](../kk_vrc_cloth_tools/optimizer_scope.py) |
| Shoe graph and gap fitting | [shoe_field.py](../kk_vrc_cloth_tools/shoe_field.py), [shoe_workflow.py](../kk_vrc_cloth_tools/shoe_workflow.py) |
| Shoe preset and current UI | [shoe_presets.py](../kk_vrc_cloth_tools/shoe_presets.py), [shoe_ui.py](../kk_vrc_cloth_tools/shoe_ui.py) |

## References

1. Binh Huy Le and Zhigang Deng. 2012. **Smooth Skinning Decomposition with Rigid Bones.** ACM Transactions on Graphics 31(6), Article 199. [Author project page](https://binh.graphics/papers/2012sa-ssdr/) · [DOI](https://doi.org/10.1145/2366145.2366218).
2. Alec Jacobson, Ilya Baran, Jovan Popović, and Olga Sorkine. 2011. **Bounded Biharmonic Weights for Real-Time Deformation.** ACM Transactions on Graphics 30(4). [Author project page](https://igl.ethz.ch/projects/bbw/).
3. **OSQP solver documentation.** Convex quadratic programming formulation and solver details. [Official documentation](https://osqp.org/docs/solver/index.html). Accessed September 20, 2026.
