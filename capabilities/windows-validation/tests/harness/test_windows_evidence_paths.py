r"""Hermetic tests for path portability in Windows evidence (F-012).

Covers AC-001..AC-008 / SCN-001..SCN-006 at two levels:

- Unit tests of the ``_reroot_under_canonical`` helper and the relaxed schema.
- Integration tests of ``validate_windows_evidence`` against an ``artifact_root``
  with real files in ``tmp_path``, varying the paths declared in
  ``log``/``artifacts`` (POSIX, UNC ``\\host\share\...``, drive ``J:\...`` and
  unsafe basenames) to verify the basename re-rooting.

Hermeticity (NFR): ``artifact_root`` and files in ``tmp_path``, no network, no
real Windows runner, and runnable on Linux.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from windows_validation import (
    WindowsEvidenceValidationError,
    _reroot_under_canonical,
    validate_windows_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "specs" / "schemas" / "windows-evidence.schema.json"

FEATURE_ID = "F-200"
TESTED_COMMIT = "abc1234"

ARTIFACT_BASENAMES = ("run.log", "capture.png", "state.json")


# ---------------------------------------------------------------------------
# Hermetic infrastructure
# ---------------------------------------------------------------------------


def _canonical_dir(artifact_root: Path, feature_id: str = FEATURE_ID) -> Path:
    canonical = artifact_root / "windows-tests" / feature_id
    canonical.mkdir(parents=True, exist_ok=True)
    return canonical


def _write_real_files(canonical: Path, basenames=ARTIFACT_BASENAMES) -> None:
    for name in basenames:
        (canonical / name).write_text(f"content-{name}\n", encoding="utf-8")


def _utc(offset_seconds: int = 0) -> str:
    moment = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )
    return moment.isoformat()


def _base_evidence(
    *,
    log: str,
    artifacts: list[str],
    feature_id: str = FEATURE_ID,
    tested_commit: str = TESTED_COMMIT,
    status: str = "PASS",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "runner_id": "windows-runner",
        "host": "test-host",
        "status": status,
        "tested_commit": tested_commit,
        "started_at": _utc(0),
        "completed_at": _utc(2),
        "checks": [
            {"id": "WIN-001", "name": "platform available", "status": "PASS"},
            {"id": "WIN-002", "name": "python available", "status": "PASS"},
            {"id": "WIN-003", "name": "workspace exists", "status": "PASS"},
        ],
        "log": log,
        "artifacts": list(artifacts),
        "metrics": {"checks": 3},
    }


def _write_evidence(canonical: Path, evidence: dict[str, Any]) -> Path:
    evidence_path = canonical / "latest.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence_path


def _validate(
    artifact_root: Path,
    evidence_path: Path,
    *,
    feature_id: str = FEATURE_ID,
    expected_commit: str = TESTED_COMMIT,
) -> dict[str, Any]:
    return validate_windows_evidence(
        repo_root=REPO_ROOT,
        artifact_root=artifact_root,
        feature={"id": feature_id, "windows_validation_required": True},
        expected_commit=expected_commit,
        evidence_path=evidence_path,
    )


# Native runner paths whose basenames match the real files.
UNC_LOG = "\\\\192.168.1.150\\share\\data\\windows-tests\\F-200\\run.log"
DRIVE_CAPTURE = "J:\\data\\poker-assistant\\artifacts\\windows-tests\\F-200\\capture.png"
UNC_STATE = "\\\\192.168.1.150\\share\\windows-tests\\F-200\\state.json"
MIXED_LOG = "\\\\host/share\\windows-tests/F-200\\run.log"


# ---------------------------------------------------------------------------
# Helper _reroot_under_canonical (AC-002, AC-005)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected_basename"),
    [
        (DRIVE_CAPTURE, "capture.png"),
        (UNC_LOG, "run.log"),
        ("/srv/agentic/workspace/data/windows-tests/F-200/state.json", "state.json"),
        (MIXED_LOG, "run.log"),
    ],
)
def test_reroot_extrae_basename_de_rutas_nativas(
    tmp_path: Path, value: str, expected_basename: str
) -> None:
    base = tmp_path / "windows-tests" / FEATURE_ID
    base.mkdir(parents=True)

    rerooted = _reroot_under_canonical(value, base)

    assert rerooted == (base.resolve() / expected_basename)
    assert rerooted.parent == base.resolve()


@pytest.mark.parametrize(
    "value",
    [
        "",
        ".",
        "..",
        "J:\\data\\windows-tests\\F-200\\",  # empty basename after trailing separator
        "\\\\host\\share\\",  # only separators after normalizing
        "/srv/data/..",  # basename ".."
        "/srv/data/.",  # basename "."
    ],
)
def test_reroot_rechaza_basenames_inseguros(tmp_path: Path, value: str) -> None:
    base = tmp_path / "windows-tests" / FEATURE_ID
    base.mkdir(parents=True)

    with pytest.raises(WindowsEvidenceValidationError):
        _reroot_under_canonical(value, base)


def test_reroot_confina_al_directorio_canonico(tmp_path: Path) -> None:
    base = tmp_path / "windows-tests" / FEATURE_ID
    base.mkdir(parents=True)
    # A sibling file outside the canonical dir that must NOT be reachable.
    outsider = tmp_path / "secret.txt"
    outsider.write_text("x", encoding="utf-8")

    # The simple basename always anchors under base; it never escapes.
    rerooted = _reroot_under_canonical("/whatever/path/secret.txt", base)
    assert rerooted == (base.resolve() / "secret.txt")
    assert rerooted != outsider.resolve()


# ---------------------------------------------------------------------------
# Relaxed schema (AC-001)
# ---------------------------------------------------------------------------


def _schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def test_esquema_acepta_rutas_windows_nativas() -> None:
    evidence = _base_evidence(
        log=UNC_LOG,
        artifacts=[DRIVE_CAPTURE, UNC_STATE],
    )

    errors = list(_schema_validator().iter_errors(evidence))

    assert errors == []


def test_esquema_no_impone_pattern_pos_ix() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "pattern" not in schema["properties"]["log"]
    assert schema["properties"]["log"]["minLength"] == 1
    assert "pattern" not in schema["properties"]["artifacts"]["items"]
    assert schema["properties"]["artifacts"]["items"]["minLength"] == 1
    assert schema["properties"]["artifacts"]["uniqueItems"] is True


def test_esquema_rechaza_log_vacio() -> None:
    evidence = _base_evidence(log="", artifacts=[DRIVE_CAPTURE])

    errors = list(_schema_validator().iter_errors(evidence))

    assert any("log" in list(error.absolute_path) for error in errors)


# ---------------------------------------------------------------------------
# SCN-001 / AC-001 + AC-002: evidence with native paths validates
# ---------------------------------------------------------------------------


def test_evidencia_con_rutas_nativas_valida(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    result = _validate(tmp_path, evidence_path)

    assert result["feature_id"] == FEATURE_ID
    assert result["status"] == "PASS"


def test_evidencia_con_rutas_posix_valida(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    # Happy POSIX path preserved (as emitted by collect_windows_evidence.py).
    posix_log = str(canonical / "run.log")
    posix_artifacts = [str(canonical / "capture.png"), str(canonical / "state.json")]
    evidence = _base_evidence(log=posix_log, artifacts=posix_artifacts)
    evidence_path = _write_evidence(canonical, evidence)

    result = _validate(tmp_path, evidence_path)

    assert result["status"] == "PASS"


def test_no_resuelve_cadena_nativa_contra_fs_local(tmp_path: Path) -> None:
    """Existence is anchored in the canonical dir, not in the native string.

    Even if a same-named file exists at some arbitrary POSIX path different from
    the canonical one, validation fails because only the canonical directory
    counts.
    """

    canonical = _canonical_dir(tmp_path)
    # We do not write run.log in the canonical dir, but we do write it elsewhere.
    decoy_dir = tmp_path / "decoy"
    decoy_dir.mkdir()
    (decoy_dir / "run.log").write_text("decoy", encoding="utf-8")
    for name in ("capture.png", "state.json"):
        (canonical / name).write_text("x", encoding="utf-8")

    evidence = _base_evidence(
        log=str(decoy_dir / "run.log"),
        artifacts=[str(canonical / "capture.png"), str(canonical / "state.json")],
    )
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="log"):
        _validate(tmp_path, evidence_path)


# ---------------------------------------------------------------------------
# SCN-003 / AC-004: real existence preserved (missing file)
# ---------------------------------------------------------------------------


def test_falta_artifact_falla_identificandolo(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    # state.json missing.
    _write_real_files(canonical, basenames=("run.log", "capture.png"))

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="state.json"):
        _validate(tmp_path, evidence_path)


def test_falta_log_falla_identificandolo(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    # run.log (the log) missing.
    _write_real_files(canonical, basenames=("capture.png", "state.json"))

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="log"):
        _validate(tmp_path, evidence_path)


def test_directorio_homonimo_no_cuenta_como_artifact(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    (canonical / "run.log").write_text("x", encoding="utf-8")
    (canonical / "state.json").write_text("x", encoding="utf-8")
    # capture.png exists as a DIRECTORY, not as a file.
    (canonical / "capture.png").mkdir()

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="capture.png"):
        _validate(tmp_path, evidence_path)


# ---------------------------------------------------------------------------
# SCN-004 / AC-005: unsafe or ambiguous basenames in the evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_log",
    [
        "J:\\data\\windows-tests\\F-200\\",  # empty basename
        "/srv/data/windows-tests/F-200/..",  # basename ".."
        "/srv/data/windows-tests/F-200/.",  # basename "."
        "\\\\host\\share\\",  # only separators
    ],
)
def test_log_con_basename_inseguro_se_rechaza(tmp_path: Path, bad_log: str) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=bad_log, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError):
        _validate(tmp_path, evidence_path)


def test_artifact_con_basename_inseguro_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(
        log=UNC_LOG,
        artifacts=["/srv/data/windows-tests/F-200/..", UNC_STATE],
    )
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError):
        _validate(tmp_path, evidence_path)


# ---------------------------------------------------------------------------
# SCN-005 / AC-006: substantive checks preserved (with files present)
# ---------------------------------------------------------------------------


def test_status_fail_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    # Global FAIL with checks at PASS avoids the schema's allOf conditional.
    evidence["status"] = "FAIL"
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="approved"):
        _validate(tmp_path, evidence_path)


def test_check_fail_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence["checks"][1]["status"] = "FAIL"
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError):
        _validate(tmp_path, evidence_path)


def test_checks_no_secuenciales_se_rechazan(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence["checks"][0]["id"] = "WIN-002"
    evidence["checks"][1]["id"] = "WIN-003"
    evidence["checks"][2]["id"] = "WIN-004"
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="sequential"):
        _validate(tmp_path, evidence_path)


def test_tested_commit_distinto_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="commit"):
        _validate(tmp_path, evidence_path, expected_commit="deadbee")


def test_feature_id_distinto_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    # The requested feature (F-201) does not match the evidence feature_id.
    other_canonical = tmp_path / "windows-tests" / "F-201"
    other_canonical.mkdir(parents=True)
    _write_real_files(other_canonical)

    with pytest.raises(WindowsEvidenceValidationError, match="feature"):
        _validate(tmp_path, evidence_path, feature_id="F-201")


def test_timestamp_sin_zona_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence["started_at"] = "2026-06-13T12:00:00"  # no timezone
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="timezone"):
        _validate(tmp_path, evidence_path)


def test_completed_anterior_a_started_se_rechaza(tmp_path: Path) -> None:
    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence["started_at"] = _utc(10)
    evidence["completed_at"] = _utc(0)
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match="started_at"):
        _validate(tmp_path, evidence_path)


# ---------------------------------------------------------------------------
# SCN-006 / AC-007: end-to-end Windows finalization (function level)
# ---------------------------------------------------------------------------


def test_finalizacion_e2e_con_rutas_nativas_preserva_invariante9(tmp_path: Path) -> None:
    """Reproduces the finalize_feature.py invocation (expected_commit = reviewed_commit).

    Validation passes with native paths only because the files exist at the
    canonical location; if they are removed, finalization would abort
    (invariant 9).
    """

    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    reviewed_commit = TESTED_COMMIT
    evidence = _base_evidence(log=UNC_LOG, artifacts=[DRIVE_CAPTURE, UNC_STATE])
    evidence_path = _write_evidence(canonical, evidence)

    # Happy case: files present in the canonical dir => validates.
    result = validate_windows_evidence(
        repo_root=REPO_ROOT,
        artifact_root=tmp_path,
        feature={"id": FEATURE_ID, "windows_validation_required": True},
        expected_commit=reviewed_commit,
        evidence_path=evidence_path,
    )
    assert result["status"] == "PASS"

    # Invariant 9: without real files in the canonical dir, it does not finalize.
    (canonical / "run.log").unlink()
    with pytest.raises(WindowsEvidenceValidationError):
        validate_windows_evidence(
            repo_root=REPO_ROOT,
            artifact_root=tmp_path,
            feature={"id": FEATURE_ID, "windows_validation_required": True},
            expected_commit=reviewed_commit,
            evidence_path=evidence_path,
        )


def test_basename_es_case_sensitive_en_linux(tmp_path: Path) -> None:
    """No case normalization is introduced: the Linux FS is case-sensitive."""

    canonical = _canonical_dir(tmp_path)
    _write_real_files(canonical)

    # The runner declares CAPTURE.PNG but the real file is capture.png.
    evidence = _base_evidence(
        log=UNC_LOG,
        artifacts=["J:\\data\\windows-tests\\F-200\\CAPTURE.PNG", UNC_STATE],
    )
    evidence_path = _write_evidence(canonical, evidence)

    with pytest.raises(WindowsEvidenceValidationError, match=re.escape("CAPTURE.PNG")):
        _validate(tmp_path, evidence_path)
