# Same-input comparison: native transfer, six categories, final optimization

[Project](../README.md) · [Earlier optimization-only figure](performance-showcase.md) · [Measurement data](data/three-stage-comparison.json)

![Same-input three-stage comparison for VRC and MMD garments.](assets/three-stage-comparison.svg)

[High-resolution PNG](assets/three-stage-comparison.png) · [Vector SVG](assets/three-stage-comparison.svg)

## Experimental design

On September 21, 2026, we generated new native baselines in a separate background Blender 5.2 process and evaluated them alongside archived six-category and final weight sets. No open working scene, source `.blend`, or production weights were modified. These are local case studies, not a population benchmark.

Within each case and pose suite, all stages use identical fitted garment rest coordinates, target skeleton transforms, transported source references, held-out poses, and vertex scopes. The final column is the **same macro-plus-terminal result** evaluated on both suites. We did not take the baseline from one suite and compare it to the result of another.

1. **Native:** Blender's built-in Data Transfer, `POLYINTERP_NEAREST`, samples all supported target-body groups onto a clean garment copy. We normalize the resulting body distribution per vertex. This ordinary body-only baseline contains no retained clothing dynamics and no category, finger, or bnip policy.
2. **Six-category:** the archived initial transfer result, including reviewed region modes, semantic fallback, original dynamic influence, enabled finger preservation, and bnip-to-bust policy. This is the configured migration system before response optimization, not an isolated test of one constraint.
3. **Final:** the archived macro and terminal optimized weights. No new optimization was run or tuned to these comparison results.

To avoid attributing all benefit to simply retaining dynamics, we also evaluate a stronger **body/dynamic-preserving native baseline**: native body proportions are scaled to the original total body share, and the original dynamic weights are restored. It still has no torso/limb category constraints or reviewed finger/bnip policies. Its complete numbers appear below and in the JSON.

## Held-out motion response

RMS is the root mean squared Euclidean position residual against the same transported source-motion reference, in scene units. Pure dynamic vertices are excluded from body-response RMS. Terminal suites additionally restrict evaluation to the archived local refinement scope. Bars use native RMS = 100 independently in each panel; absolute values and scopes differ, so panels must not be pooled.

| Case / suite | Scope | Held-out poses | Native RMS | Six-category RMS | Final RMS | Final reduction vs native |
|---|---:|---:|---:|---:|---:|---:|
| VRC jacket / macro | 8,885 | 3 | 0.00221691165 | 0.00215018032 | 0.00209410628 | 5.539% |
| VRC jacket / terminal | 1,514 | 4 | 0.00494374909 | 0.00461595509 | 0.00243553546 | 50.735% |
| MMD skirt outfit / macro | 4,009 | 4 | 0.00382886028 | 0.00335088950 | 0.00334121201 | 12.736% |
| MMD skirt outfit / terminal | 986 | 8 | 0.00737330818 | 0.00737330849 | 0.00737243417 | 0.012% |

Six-category initialization reduces macro RMS by approximately 3.01% for VRC and 12.48% for MMD relative to plain native transfer. Its MMD terminal RMS is essentially unchanged and is very slightly higher before optimization; not every scope improves at every stage. The final VRC terminal result shows the largest response improvement in these comparisons.

The earlier optimization-only figure used the macro result as the terminal-stage baseline. Here, **six-category always means the original six-category initialization**, even on the terminal suite. This accounts for small differences from previously reported terminal baselines.

## What six-category protection contributes

![Six-category constraint results: 100% reduction in wrong-category vertices in both measured cases.](assets/six-category-showcase.svg)

[Standalone PNG](assets/six-category-showcase.png) · [Standalone SVG](assets/six-category-showcase.svg). Regenerate with `python tools/build_six_category_showcase.py`.

A wrong-category vertex has at least one body category with source budget at most `1e-8` but transferred share greater than `1e-5`. Counts cover all garment vertices, including pure dynamic regions. They measure a semantic-budget violation, not a visually confirmed tear or a collision count.

| Case / measurement | Native | Six-category | Final |
|---|---:|---:|---:|
| VRC / wrong-category vertices | 28 | 0 | 0 |
| VRC / maximum category-share error | 0.9678756 | 5.03e-8 | 4.57e-8 |
| VRC / maximum retained dynamic-weight error | 0.9380324 | 0 | 0 |
| MMD / wrong-category vertices | 2,175 | 0 | 0 |
| MMD / maximum category-share error | 1.0 | 4.47e-8 | 4.28e-8 |
| MMD / maximum retained dynamic-weight error | 1.0 | 0 | 0 |
| MMD / pure dynamic vertices receiving body weights | 1,855 | 0 | 0 |

Category-share errors are absolute weight fractions, not percentages. Values near `1e-8` reflect floating-point writeback precision. The goal is preservation of the source allocation, not minimizing each category's share.

### Stronger native baseline: preserve total body/dynamic influence

| Case / measurement | Body/dynamic-preserving native | Six-category | Final |
|---|---:|---:|---:|
| VRC / wrong-category vertices | 28 | 0 | 0 |
| MMD / wrong-category vertices | 320 | 0 | 0 |
| VRC / maximum category-share error | 0.9586544 | 5.03e-8 | 4.57e-8 |
| MMD / maximum category-share error | 0.4703098 | 4.47e-8 | 4.28e-8 |
| VRC / macro RMS | 0.00221691165 | 0.00215018032 | 0.00209410628 |
| VRC / terminal RMS | 0.00494374909 | 0.00461595509 | 0.00243553546 |
| MMD / macro RMS | 0.00345576656 | 0.00335088950 | 0.00334121201 |
| MMD / terminal RMS | 0.00737330818 | 0.00737330849 | 0.00737243417 |

This auxiliary baseline preserves dynamic weights exactly and introduces no body influence into pure dynamic vertices. Remaining wrong-category vertices demonstrate why conserving only the total body/dynamic split is insufficient. In the VRC sampled suites, preserving dynamics alone changes motion RMS negligibly despite improving semantic metrics; those poses do not expose every possible dynamic failure. The suites are not a comprehensive physics test.

## Replay checks and limitations

Archived target matrices were reproduced exactly on shared bones. Replaying archived body weights against body pose samples differed by less than `6e-7` scene units. Numerical native-baseline LBS matched Blender evaluation within `4e-7`. Archived reference digests were checked, and the original six-category macro RMS and final terminal RMS were reproduced within `1e-8`.

The VRC archive uses the saved original body-weight snapshot rather than trusting the later scene's full object stamp. Sampling geometry comes from the archived neutral body pose with checked topology. The MMD body object stamp matches its archived context. Target bones newly used by native transfer are evaluated on the same rig and pose controls instead of being silently discarded to fit the optimizer's candidate list.

The MMD source reference is the fitted mesh with original MMD weights frozen before transfer, not the pre-fitting garment shape. Existing cap intersections were user-reviewed in the historical result; strict collision validation did not pass. This comparison does not re-run collision tests, report a collision-free result, or evaluate runtime inertia and damping. Finger and bnip policies differ between unfiltered native transfer and the configured six-category pipeline, so response gains cannot all be attributed to the six-budget constraint alone.

## Provenance

The measurement archive is `algorithm-ablation/20260921` in the local Neon Vertex test project. It contains the background Blender script `measure.py`, both result records, and all four dense weight sets per case. VRC references come from `close-no-bnip/stage1` and `stage2`; MMD references come from `20260921-liv-skirt` and `wrist-terminal`. Private model assets are not redistributed.

The public [measurement extract](data/three-stage-comparison.json) records replay checks, exact values, evaluation pose names, baseline definitions, and hashes of the local result records. Regenerate the figure with Python and Matplotlib:

```sh
python tools/build_three_stage_comparison.py
```
