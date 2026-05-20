# Repository Structure

This repository now separates three concerns clearly:

- `hypergraphrag/`: upstream baseline package and reusable core code
- `evaluation/`: experiment entrypoints, backends, and method runners
- `docs/`: project-facing documentation, reports, and figures

## Naming policy

### Keep `hypergraphrag/` as baseline code

The package name `hypergraphrag/` is intentionally kept unchanged.
It is the baseline implementation and also the current import path used by all scripts.
Renaming the package itself to `swhc/` would break reproducibility and blur the distinction between:

- baseline: `HyperGraphRAG`
- proposed method: `SWHC`

### Use `SWHC` for project-specific artifacts

Project-facing reports and method-specific experiment outputs should use `SWHC` in their names when they describe the proposed method rather than the baseline paper.

## Current top-level layout

```text
HyperGraphRAG/
├─ hypergraphrag/          # core package (baseline + extensions)
├─ evaluation/             # evaluation scripts, results backends, method runners
├─ logs/                   # archived historical logs
├─ docs/                   # reports, walkthroughs, figures
├─ expr/                   # root demo cache (legacy / quick start)
├─ figs/                   # upstream paper figures
├─ README.md               # upstream project README
└─ requirements.txt
```

## Docs layout

```text
docs/
├─ baselines/
│  └─ HyperGraphRAG_Code_Walkthrough.md
├─ figures/
│  └─ flowchart.png
└─ project/
   ├─ SWHC_项目进度汇报_2026-04-13.md
   └─ guidance.md
```

## Evaluation layout

See `evaluation/STRUCTURE.md` for the detailed convention used for:

- datasets
- contexts
- method runners
- cache/index artifacts
- results
- logs

## Archived historical logs

Historical top-level logs that are not tied to a single method runner are archived under:

```text
logs/
└─ archive/
   ├─ evaluation/
   │  └─ hypergraphrag.log
   └─ root/
      └─ hypergraphrag.log
```
