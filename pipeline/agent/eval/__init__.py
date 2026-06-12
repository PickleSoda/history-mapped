"""Reproducible evaluation harness for the agentic pipeline.

Resets the database to a blank baseline, runs the pipeline over a set of
transcripts, probes the resulting database, applies automatable quality
heuristics, and writes a JSON + Markdown report so a run can be reproduced and
compared across iterations.

CLI: ``py -m pipeline.agent.eval --help``
"""
