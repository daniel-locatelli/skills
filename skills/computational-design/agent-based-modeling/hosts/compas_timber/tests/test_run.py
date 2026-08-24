import json
import subprocess
import sys

import pytest

from run import build_config, run


def test_run_reports_realised_and_nominal_counts_separately():
    """algorithm.md 1: 'Every per-agent statistic must be reported against the realised count.'"""
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--no-timber"]))
    assert out["nominal_count"] == 150
    assert 125 <= out["realised_count"] <= 135
    assert out["realised_count"] != out["nominal_count"]


def test_alignment_is_reported_with_its_pair_count():
    out = run(build_config(["--surface", "monge", "--agents", "150", "--seed", "hex",
                            "--no-timber"]))
    assert "alignment_pairs" in out and out["alignment_pairs"] > 0


def test_sphere_reports_zero_alignment_pairs_not_a_bare_zero():
    """A sphere is umbilic, so the anisotropy gate admits no pair. Absent population."""
    out = run(build_config(["--surface", "sphere", "--agents", "60", "--seed", "random",
                            "--no-timber"]))
    assert out["alignment_pairs"] == 0
    assert out["alignment_mean"] == 0.0


def test_identities_are_labelled_as_identities():
    """algorithm.md 8c: 'report, never assert as evidence'. The report must say so."""
    out = run(build_config(["--surface", "sphere", "--agents", "60", "--seed", "random",
                            "--no-timber"]))
    assert "identities" in out
    assert set(out["identities"]) >= {"euler", "valence_defect_sum", "triangle_count"}
    assert "euler" not in out                      # only inside the identities block


def test_json_output_round_trips(tmp_path):
    path = tmp_path / "run.json"
    run(build_config(["--surface", "monge", "--agents", "60", "--seed", "hex",
                      "--no-timber", "--json", str(path)]))
    data = json.loads(path.read_text())
    assert data["realised_count"] > 0


def test_cli_entry_point_runs(tmp_path):
    path = tmp_path / "cli.json"
    proc = subprocess.run([sys.executable, "run.py", "--surface", "monge", "--agents", "60",
                           "--seed", "hex", "--no-timber", "--json", str(path)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "over" in proc.stdout and "pairs" in proc.stdout
