# Total-influence deployment study

September 28, 2026 · SBCST 2.5.1 numerical snapshot

[Project](../README.md) · [User guide](../USER_GUIDE.md#choose-a-total-influence-policy) · [Method extension](influence-limits.md) · [Public measurements](data/influence-limit-benchmark.json) · [Paper](paper/SBCST.pdf)

Release naming note: this numerical snapshot was measured under the development label `0.3.0` and is distributed as **2.5.1**. The original label remains in the JSON provenance; source hashes and measurements are unchanged.

## Question and protocol

This read-only dry run asks whether the optional four-influence constraint changes fitting cost or fidelity, and whether disabling it preserves the legacy method. It compares the pre-limit solver at commit `ccdadc0dd10137e7532044b08c12933b6ad334fd`, the current unlimited path, and the current four-influence path. **Dynamic compression is disabled throughout.** No scene weights are written and no Unity import or frame-rate test is performed.

The two archived inputs are a closed jacket with 8,885 vertices and 47 target bone columns, and an open jacket with 8,969 vertices and 78 columns. Original/fitted rest geometry, source weights, matrices, semantic budgets, fixed contributions, candidates, and references are held constant. Array/metadata digests and source/target LBS replay checks pass. The snapshots and archive hashes are recorded in the public extract without redistributing third-party meshes.

Macro fitting uses 12 training poses and 3 independent holdouts; terminal fitting uses 15 training poses and 4 holdouts. Terminal scopes contain 1,514 and 1,562 vertices. Contacts remain enabled with the same archived training-contact samples. Holdouts never choose supports or fit weights. Macro coefficients are prior 0.002, graph 0.002, trust 0.15, at most four contact iterations; terminal coefficients are prior 0.00005, graph 0.00003, residual scale 0.15, trust 0.35, at most eight iterations. Local correction masks and bounds are preserved.

Numerical runs use Python 3.12 on Windows 11, NumPy/SciPy/OSQP, and identical single-thread BLAS settings. Macro timings use three serial repeats with rotated mode order. All repeated outputs are exactly deterministic in these runs. Timers include support selection, QP assembly/solving, and contact queries; they exclude shared input/reference preparation, native transfer, scene sampling, serialization, and independent validation. These are per-case measurements, not a runtime scaling study or Unity rendering measurements.

## Same-input macro ablation

The isolated ablation supplies the same dense initial weights to all three solvers. Values are median seconds; brackets give the observed minimum–maximum, not confidence intervals.

| Case | Legacy | New unlimited | Change | Four | Change vs legacy | Four support-search median |
|---|---:|---:|---:|---:|---:|---:|
| Closed | 26.53 [24.49–27.29] | 26.96 [24.48–27.54] | +1.64% | 47.60 [42.35–48.10] | +79.45% | 19.91 |
| Open | 25.41 [23.80–25.51] | 25.48 [23.74–26.02] | +0.28% | 51.31 [48.02–52.23] | +101.92% | 25.06 |

Unlimited weights match the legacy weights **element for element**, both after the macro solve and after chaining its result into terminal refinement. The maximum absolute difference is zero. The small timing differences lie within the observed repeat ranges; this supports parity for these inputs, not a universal equivalence claim about unrelated adapters or assets. Most of the four-mode overhead is its discrete support search.

## Complete numerical workflow

The UI-like four-mode path also invokes the initialization support selector, keeps the original dense reference, and feeds each mode's macro result into terminal refinement. Bone columns are aligned by name; selected terminal masks remain unchanged. It reuses archived pose matrices rather than exporting a new scene. It does **not** perform the intermediate float32 Blender writeback, and therefore is not a click-through UI/Unity test.

| Case | Legacy macro + terminal | Four initialization | Four macro | Four terminal | Four total | Change |
|---|---:|---:|---:|---:|---:|---:|
| Closed | 37.39 s | 2.62 s | 38.99 s | 11.84 s | 53.45 s | +42.96% |
| Open | 36.87 s | 4.86 s | 44.62 s | 15.17 s | 64.65 s | +75.33% |

These full-path timings are **single runs**, not the three-repeat macro statistics above. Initialization reduces the starting support for subsequent selection, and the measured costs must not be interchanged with the dense-input ablation.

### Independent response fidelity

All distances are in archived world-coordinate units. Each row evaluates its own pose suite and vertex scope; macro and terminal errors should not be pooled into a universal accuracy score. “Dense” is the identical legacy/unlimited result. Four is the complete numerical workflow above.

| Case / scope | Dense RMS | Four RMS | RMS change | Dense P95 | Four P95 | Dense max | Four max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Closed / macro | 0.0020941063 | 0.0020824558 | −0.56% | 0.0050541745 | 0.0050268206 | 0.018295442 | 0.018384087 |
| Open / macro | 0.0012521321 | 0.0012302737 | −1.75% | 0.0025904145 | 0.0025623906 | 0.017759792 | 0.018030927 |
| Closed / terminal | 0.0024355353 | 0.00080254738 | −67.05% | 0.0052565419 | 0.0013010230 | 0.019179155 | 0.010471281 |
| Open / terminal | 0.00077742774 | 0.00084493956 | +8.68% | 0.0012645969 | 0.0014097684 | 0.010471279 | 0.010471279 |

The lower macro RMS does not mean every vertex improves: maximum macro error increases 0.48% and 1.53%. The open terminal scope has 8.68% higher RMS and 11.48% higher P95, despite essentially unchanged maximum error. Both four-mode stages pass their motion gates against their own stage inputs; that is distinct from matching the dense optimum. The isolated dense-input four path gives a slightly different open terminal result (+9.17% RMS), emphasizing that initialization and bounded support search matter. No optimality claim is made for the selected supports.

## Preservation, counts, and contacts

| Four-mode final result | Closed | Open |
|---|---:|---:|
| Maximum positive influences | 4 | 9 |
| Vertices exceeding four | 0 | 140 |
| Maximum six-budget error | 3.99e−8 | 3.99e−8 |
| Maximum fixed-weight change | 0 | 0 |
| Maximum dynamic-weight change | 0 | 0 |

The 140 open-jacket exceptions violate the lower bound imposed by fixed positive contributions plus positive residual categories. Their complete weight rows remain unchanged; they are not hidden by a threshold or globally renormalized. **The open result is `RUNTIME_REVIEW_REQUIRED`, not `STRICT_FOUR`.** Successful preservation checks do not establish export compatibility for those vertices.

An independent factory Blender 5.2 process runs triangle-crossing and oriented vertex/edge-midpoint/face-centre checks, with tolerance `1e-4` world units. Each final result is tested on all seven held-out macro/terminal poses, over body-influenced vertices and boundary faces. No additional body-vertex exemption mask is used. Legacy, unlimited, and four-mode results all have zero detected in-scope triangle crossings and penetrating samples; pure dynamic geometry remains outside this body-fitting acceptance scope. This is sampled-pose evidence, not continuous-time collision freedom.

## Limits of the evidence

- Two jacket inputs do not establish a universal speed/accuracy tradeoff. A local improvement under a smaller support is possible but is not guaranteed.
- There is no new cap ablation for MMD or shoes here. Historical dense MMD/shoe figures remain separate evidence.
- Optional dynamic compression is implemented and covered by functional tests, but its real-asset approximation quality is not measured in this comparison.
- No engine imports, target-device frame rates, continuous animation, or runtime secondary-motion simulation are evaluated.
- Public JSON and the paper table generator reproduce the reported arithmetic. Full private contexts, assets, and source pose scenes are not redistributed.

Choose four for a target requiring four influences, and unlimited for a target configured to accept the dense result. Confirm the actual engine/import settings rather than inferring them from a version name alone.
