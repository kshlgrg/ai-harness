"""Tests for Benchmark Suite and Ablations."""
from forge.benchmark.ablations import AblationStudy
from forge.benchmark.cases import SAMPLE_BENCHMARK_TASKS
from forge.benchmark.runner import BenchmarkRunner


def test_benchmark_runner():
    runner = BenchmarkRunner()
    table = runner.run_suite(SAMPLE_BENCHMARK_TASKS[:2])
    assert table is not None
    assert len(runner.results) == 4  # 2 tasks * (Baseline + FORGE)


def test_ablation_study():
    study = AblationStudy()
    table = study.run_ablations()
    assert table is not None
    assert len(study.DEFAULT_ABLATIONS) == 7
