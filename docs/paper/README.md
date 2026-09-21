# SBCST paper

**Semantic Budget-Constrained Skinning Transfer for Garment Retargeting**

Tom Xu, September 2026. Independent technical manuscript; not peer reviewed.

[Read the paper (PDF)](SBCST.pdf) · [LaTeX source](sbcst.tex) · [Project](../../README.md) · [Implementation report](../technical-report.md)

The paper presents the general semantic-budget formulation, feature-aware initialization, proportion-aware response transport, constrained body-weight optimization, terminal refinement, and the alternative flat-footwear spatial objective. It includes 30 numbered equations, three vector figures, and three numerical tables in a 10-page two-column layout.

## Evidence and scope

The paper uses the archived same-input jacket/skirt-outfit comparisons and the complex flat-shoe study. The four garment methods are native transfer, native transfer with the body/dynamic split preserved, SBCST initialization, and the final macro-plus-terminal result. The MMD-style case is a limited cross-rig applicability experiment, with explicit local contact review and recorded residual contacts; it is not presented as a strict global collision pass. The footwear study uses the standard-only pose set. Low-weight random sampling is implemented, but its incremental benefit is not claimed here.

Public inputs:

- [Same-input measurements](../data/three-stage-comparison.json)
- [Historical stage and shoe measurements](../data/performance-showcase.json)
- [Detailed comparison protocol](../three-stage-comparison.md)

The public files reproduce the figures, table values, and manuscript. Third-party model assets and complete private Blender archives are not included, so these files alone do not reproduce the underlying scene experiments.

## Build

Install a LaTeX distribution with `pdflatex` and the packages listed in `sbcst.tex`. Python requires NumPy and Matplotlib. From this directory:

```sh
python build_paper.py --build-dir /path/to/cache/sbcst
```

The script regenerates vector figures and numeric table macros from the public JSON, runs LaTeX twice, checks for overflow/unresolved references, and writes `SBCST.pdf` here. Supply a real scratch directory in place of `/path/to/cache/sbcst`; intermediates stay there. Review the rendered pages after changing text, figures, font packages, or layout.

For just the figures and data tables:

```sh
python build_figures.py
```

The pipeline diagram is explanatory. The bar charts show recorded measurements, not synthesized examples. The source and vector figure files are included for editing and rebuilding.

## Citation

```bibtex
@misc{xu2026sbcst,
  author = {Tom Xu},
  title = {Semantic Budget-Constrained Skinning Transfer for Garment Retargeting},
  year = {2026},
  month = sep,
  note = {Independent technical manuscript},
  url = {https://github.com/tomTom1010-IEE/KK_Modder-BatchTool/blob/main/docs/paper/SBCST.pdf}
}
```
