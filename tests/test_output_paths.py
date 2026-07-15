from pathlib import Path

import pytest

from tslab.services.output_paths import (
    browse_url_for,
    output_ref,
    relative_output_path,
    resolve_output_dir_arg,
)


def test_output_ref_from_absolute_under_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    run = tmp_path / "output" / "TSA_ex_beispiel"
    run.mkdir(parents=True)
    assert output_ref(run) == "TSA_ex_beispiel"


def test_output_ref_from_relative_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    (tmp_path / "output").mkdir()
    assert output_ref("CORR_ex_a_vs_b_2020-01-01_to_2021-01-01") == "CORR_ex_a_vs_b_2020-01-01_to_2021-01-01"


def test_output_ref_strips_legacy_output_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    (tmp_path / "output").mkdir()
    assert output_ref("output/TSA_ex_beispiel") == "TSA_ex_beispiel"


def test_output_ref_rejects_foreign_absolute_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    (tmp_path / "output").mkdir()
    foreign = Path("C:/alt/projekt/output/TSA_ex_beispiel")
    with pytest.raises(ValueError):
        output_ref(foreign)


def test_resolve_output_dir_arg_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    run = tmp_path / "output" / "TSA_ex_beispiel"
    run.mkdir(parents=True)
    ref = output_ref(run)
    assert resolve_output_dir_arg(ref) == run.resolve()


def test_browse_url_for_rejects_foreign_absolute_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    (tmp_path / "output").mkdir()
    foreign = Path("C:/alt/projekt/output/TSA_ex_beispiel")
    assert browse_url_for(str(foreign)) is None


def test_browse_url_for_accepts_relative_ref(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    out = tmp_path / "output" / "TSA_ex_beispiel"
    out.mkdir(parents=True)
    assert browse_url_for("TSA_ex_beispiel") == "/output/browse/TSA_ex_beispiel"


def test_relative_output_path_returns_none_for_foreign_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tslab.services.output_paths.resolve_output_dir",
        lambda cfg=None: tmp_path / "output",
    )
    (tmp_path / "output").mkdir()
    assert relative_output_path("C:/fremd/output/run") is None
