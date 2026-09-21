# Optimization Results: VRC and MMD Case Studies

[Project](../README.md) · [Technical report](technical-report.md) · [User guide](../USER_GUIDE.md)

![VRC and MMD optimization outcomes, with independent baselines and preservation checks.](assets/performance-showcase.svg)

[Download PNG](assets/performance-showcase.png) · [Vector SVG](assets/performance-showcase.svg) · [Reviewed data](data/performance-showcase.json)

## What is measured

This figure summarizes historical local runs, not a new benchmark or a comparison with competing methods. Here, performance means deformation quality and preservation, not execution speed. Each bar starts at zero and uses its own pre-optimization error as 100. Reduction is `100 × (1 − after / before)`. Absolute RMS values are in scene units. Different rows have different poses, scopes, or objectives; they must not be averaged into a single score.

| Source and case | Stage | Held-out RMS before | Held-out RMS after | Reduction |
|---|---|---:|---:|---:|
| VRC · Neon Vertex closed jacket | Macro response | 0.0021501803 | 0.0020941063 | 2.61% |
| VRC · Neon Vertex closed jacket | Terminal response | 0.0046159550 | 0.0024355355 | 47.24% |
| VRC · Neon Vertex flat shoes | Field A → separation-refined B | 0.0006319864 | 0.0006004512 | 4.99% |
| MMD · Liv skirt outfit | Macro response | 0.0033508895 | 0.0033412119 | 0.29% |
| MMD · Liv skirt outfit | Terminal response | 0.0073733269 | 0.0073724342 | 0.012% |

The VRC terminal case shows the largest measured improvement here. The MMD example demonstrates extension to a different source-rig convention with small incremental improvements; it is not evidence of a large optimization gain or general superiority. The flat-shoe row measures separation error, whereas garment rows measure transported motion-response error.

## Preservation and validation

- **VRC shoes:** all four held-out poses had zero detected in-scope intersections and penetrating samples. Actual writeback body-budget error was at most `4.47e-8`, and retained dynamic-weight error at most `2.98e-8`. These measurements used seven standard training poses, before random auxiliary poses were introduced.
- **MMD macro:** 4,009 body-influenced vertices; 18 evaluated poses, including four held-out poses. Actual writeback budget error was `4.284083843231201e-8`, fixed dynamic error was zero, and excluded bnip influence remained zero. Geometry, UVs, materials, and normals were unchanged.
- **MMD terminal:** 986 vertices; 29 evaluated poses, including eight held-out poses. The final audit measured zero dynamic-weight and geometry changes, with exterior vertex weights exactly preserved. The pose totals include training and validation; they are not counts of independent held-out poses.

MMD source motion used evaluated constraint-aware sampling. Its source reference was the **already-fitted mesh with complete original MMD weights**, frozen before transfer. It therefore does not measure recovery of the garment's pre-fitting geometry.

### Collision review is not a collision-free result

The MMD strict validation records retain `accepted: false` and `contact_ok: false`. The macro result was subsequently written after explicit user approval of existing wrist-cap intersections, with non-collision checks passing. The terminal audit found no new contact vertices outside the cap exemption, but six existing non-exempt vertices remained flagged. The figure does not report a global pass rate or zero MMD collisions.

These results cover sampled poses and configured scope. They do not establish continuous-time collision freedom, runtime secondary-motion behavior, or statistically significant improvements across a model population.

## Provenance and regeneration

VRC values are drawn from the previously published [case-study extract](data/case-study-summary.json): `close-no-bnip/stage1/validation.json`, `close-no-bnip/stage2/validation.json`, and `shoe-transfer/flat-round-02/{report.json,actual-writeback-audit.json}`.

MMD values come from the local archive `weight-transfer/20260921-liv-skirt/`: `validation.json`, `optimized-write-report.json`, `wrist-terminal/validation.json`, and `wrist-terminal/final-audit.json`. The reviewed JSON retains numeric fields, relative record identities, and hashes for the two MMD validation files. Third-party meshes and private scene files are not redistributed.

Regenerate the SVG and 3200 × 2100 PNG with Python and Matplotlib:

```sh
python tools/build_performance_showcase.py
```

The generator reads the checked-in measurement extract; it does not run Blender, modify weights, or reproduce the private model experiments.
