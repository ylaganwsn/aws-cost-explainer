# aws-cost-explainer

A weekly report that explains why your AWS bill changed.

**Rule:** Python decides what changed, the LLM only explains it, and the report still works if the LLM fails.

> Status: Phase 1 (local logic). AWS, Lambda and Terraform come in later phases.

## Quick start (no AWS needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m cost_explainer --sample
pytest
```
