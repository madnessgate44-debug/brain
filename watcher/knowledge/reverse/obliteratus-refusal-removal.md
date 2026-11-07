# Reverse-engineering finding: OBLITERATUS (abliteration — refusal removal)

Source: `https://github.com/elder-plinius/OBLITERATUS` (9,253★, 1,643 forks, Python, AGPL-3.0,
version 0.1.4, requires Python ≥3.11). Read via GitHub API + raw file fetch 2026-11-07; live
Space and Colab notebook both probed HTTP 200. Clone not needed — the pipeline is described in
`README.md` and the source tree is public.

Owner-supplied entry points, both verified reachable this session:

- Hugging Face Space: `https://huggingface.co/spaces/pliny-the-prompter/obliteratus`
  (API HTTP 200, Gradio SDK, ZeroGPU, `gated:false`, 624 likes).
- Colab: `https://colab.research.google.com/github/elder-plinius/OBLITERATUS/blob/main/notebooks/abliterate.ipynb`
  (raw notebook HTTP 200, 13 cells).

## What it is

OBLITERATUS is the most complete open-source implementation of **abliteration** — removing the
internal representations that make an instruction-tuned model refuse, without retraining. It is
the packaged form of the published technique from Arditi et al. (2024, "Refusal in LLMs is
mediated by a single direction"), extended with Gabliteration, whitened-SVD, and norm-preserving
biprojection. It is a *weight-surgery* tool, not a prompt trick: it edits the model, then saves a
new model.

## The pipeline (the part worth understanding)

Six stages, run by one command:

```
SUMMON  → load model + tokenizer
PROBE   → collect hidden-state activations on restricted vs. unrestricted prompts
DISTILL → extract the "refusal direction" via SVD / mean-difference / PCA
EXCISE  → project that direction out of the weights (norm-preserving)
VERIFY  → perplexity + coherence checks — confirm capabilities survived
REBIRTH → save the liberated model with full metadata
```

The core idea is geometric. A refusal is (approximately) one direction in activation space.
Collect activations for harmful and harmless prompts, take the difference, and you get a vector.
Project the model's write matrices away from that vector and the model stops refusing. The whole
difficulty is doing it *precisely* so reasoning and knowledge survive — hence the SVD variants,
the layer selection, the KL-divergence co-optimization, and the iterative re-probing.

## Novel techniques it adds over the 2024 baseline

| Technique | One-line description |
|---|---|
| Expert-Granular Abliteration (EGA) | per-expert refusal removal for MoE models via router logits |
| CoT-Aware Ablation | orthogonalize the refusal direction against reasoning directions |
| COSMIC layer selection | pick layers where harmful/harmless activations are most separable |
| Whitened SVD | covariance-normalize before extraction so the signal separates from noise |
| KL co-optimization | restore any layer whose removal diverges from the pristine model |
| LoRA-based reversible ablation | rank-1 adapters instead of permanent surgery (reversible) |
| True iterative refinement | re-probe after each pass to catch rotated residual directions |
| Bias-term projection | remove refusal from bias vectors, not just weights (others miss this) |

## Ways to use it (six, from zero-code to full API)

1. **Hugging Face Space** — no install, ZeroGPU (visitor's own HF quota), eight-tab Gradio UI.
2. **Local web UI** — `pip install -e ".[spaces]"` then `obliteratus ui` (your own GPU).
3. **Colab** — open the notebook, Run All; free T4 works up to ~8B params.
4. **CLI** — `obliteratus obliterate meta-llama/Llama-3.1-8B-Instruct --method advanced`.
5. **Python API** — `AbliterationPipeline(...).run()`, exposes directions/metrics as tensors.
6. **YAML configs** — reproducible studies versioned in git.

## Where it intersects our work

- **The Watcher/Shadow loop is a refusal-adjacent problem, not a model problem.** Nothing here
  is needed to run Watcher. OBLITERATUS only matters if we ever *own* an open-weights model.
- **brain's model path is hosted (Gemini).** Gemini is a closed model; abliteration is
  impossible on it by construction. So this finding is **knowledge, not an integration** — it
  does not change `brain/` code, the connector, or the Vercel deploy.
- **The genuine transferable idea is the verification discipline**, not the surgery:
  - **PROBE then VERIFY** is the same shape as Shadow's audit: establish a baseline, make a
    change, measure that the change did what you claim and broke nothing.
  - **KL co-optimization** (measure divergence from a pristine baseline, roll back layers that
    diverge too far) is exactly the "smallest complete change + preserve what works" rule we
    already follow, expressed as a numeric budget. Worth borrowing as a *concept* for how
    Shadow grades a Watcher change: a hard, measured budget instead of a vibe.
  - **Iterative re-probing** mirrors our loop: after each pass, re-check the live state instead
    of trusting the plan.

## What is worth implementing (ranked)

1. **Borrow the budget idea for Shadow's audit (concept only, ~0 code).** Shadow already returns
   VERIFIED / REJECTED / PARTIAL. Add one measured number to each verdict where a number exists
   (test count, diff size, files touched) so a verdict carries a quantity, not only a word.
   *Status: proposal only — not implemented here.*
2. **Nothing else.** There is no engine in our stack to attach the surgery to.

## What to skip

- The whole weight-surgery engine (torch/transformers/SVD, GPU-bound). No owned open-weights
  model in the org means there is nothing to abliterate.
- The Space and Colab as *our* infrastructure — they run on the visitor's HF quota and are
  AGPL-3.0. Fine to point a human at; not something to depend on.

## Responsible-use note (recorded, not editorializing)

OBLITERATUS is a published alignment-research tool and its own README states who it is *not*
for. The techniques are public research (Arditi et al.); the tool's stated purpose is studying
how safety is encoded. We use the finding as **knowledge for architecture**, not as a route to
generate harmful content. Recorded here so the boundary is explicit for any future reader.

## Confidence and risk

- Confidence: **HIGH** on what the tool is and does (README + source tree read).
- Confidence: **HIGH** that it is not integrable into brain (closed hosted models).
- Risk of adopting anything from it: **LOW** — the only proposed change is a wording/format
  tweak to Shadow's verdict, no dependency, no license entanglement.

## Verification done this session

- `GET /repos/elder-plinius/OBLITERATUS` → `default_branch=main`, AGPL-3.0, 9,253★.
- Git tree (1,041 blobs) read; `obliteratus/*.py` module list inspected (pipeline, presets,
  informed_pipeline, refusal_metrics, mcp_server, …).
- `README.md` (69 KB) read: pipeline, six usage paths, novel-technique table, responsible-use.
- `notebooks/abliterate.ipynb` fetched and cell-by-cell inspected (13 cells, 6-stage pipeline).
- `hf-spaces/README.md` read: ZeroGPU "bring your own quota" model, Gradio 6.31.0.
- Live probes: HF Space API `http=200`; Colab raw notebook `http=200`.
