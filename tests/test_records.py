"""VibeBB Record Protocol: typed writers, stdlib hook mirror and Stop enforcement."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng import records

SCRIPTS = Path(__file__).parents[1] / "plugins" / "prodeng" / "hooks" / "scripts"
HOOK = SCRIPTS / "require_records.py"

IMPRESSION = (
    "The control plan reads as a coherent production sheet: each operation has an "
    "inspection method, a documented sampling level, and a linked characteristic. "
    "What worries me is that the torque check still depends on an operator recording "
    "a value without a clear reaction step when the result is out of limit. A line "
    "operator could follow the listed sequence, although the containment action is "
    "not yet prominent enough to prevent a missed escalation. Next I would make the "
    "reaction step explicit and re-render the plan to confirm it is easy to locate. "
    "Overall the sheet communicates the inspection intent, with the remaining risk "
    "concentrated in the response to a failed measurement."
)
IMPRESSION_JA = (
    "管理計画には作業と検査の順序が明確に記され、特性ごとの確認方法も追跡できる。"
    "ただし不適合時の封じ込めとエスカレーションが曖昧で、担当者による解釈の差が残る。"
    "現場の作業者は通常の検査を進められるが、異常値を見つけたときの次の行動には迷う可能性がある。"
    "次の工程では反応計画を明記し、改訂後の帳票で注意事項が見つけやすいことを確かめたい。"
    "全体として検査意図は読み取れるものの、封じ込め手順が品質リスクの中心に残っている。"
    "ロット識別と記録欄の関係は追跡可能であり、作業後の確認にも使える構成である。"
    "サンプリング水準の根拠は承認済み要求に結び付け、作業者が独自に変更しないようにしたい。"
    "異常時の保留場所と通知先が定義されれば、次の担当者へ情報を確実に渡せる。"
    "帳票の改訂番号は見える位置にあり、古い版を誤使用する危険は抑えられている。"
    "最後に、重要特性と検査結果を照合する導線を整え、運用開始前に現場で確認することを提案する。"
)


def _hook_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("_records", SCRIPTS / "_records.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK_RECORDS = _hook_module()


def _decision(evidence_path: str) -> dict[str, Any]:
    return {
        "id": "line-balance-split",
        "stage": "contract",
        "question": "How should the press and inspection work be split across stations?",
        "principles": [
            "Takt time is the maximum sustainable interval between completed units",
            "Quality checks must detect the characteristic before the next process step",
        ],
        "options": [
            {"name": "single-station", "pros": ["simple handoff"], "cons": ["cycle exceeds takt"]},
            {"name": "split-stations", "pros": ["balances cycle time"], "cons": ["extra handoff"]},
        ],
        "chosen": "split-stations",
        "rationale": (
            "The combined press and inspection cycle exceeds the available takt, so leaving "
            "both tasks at one station would create a sustained queue and make the planned "
            "production rate unattainable. Splitting the inspection step reduces the work "
            "content at the press station while retaining a defined quality check before "
            "downstream assembly. The handoff adds a traceability requirement, which can be "
            "managed with a shared lot and operation identifier."
        ),
        "evidence": [{"path": evidence_path}, {"reference": "approved cycle-time study"}],
        "assumptions": ["the inspection station has capacity for the additional operation"],
        "unknowns": ["measured operator time after the station split"],
        "risks": ["the handoff may lose lot or operation traceability"],
        "revisit_when": "a time study shows the new balance exceeds takt",
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "renders").mkdir()
    (tmp_path / "out" / "control-plan.csv").write_text("operation,check\n", encoding="utf-8")
    (tmp_path / "out" / "renders" / "control-plan.png").write_bytes(b"\x89PNG fake")
    return tmp_path


def test_impression_rules() -> None:
    assert records.impression_is_prose(IMPRESSION) == IMPRESSION
    assert records.impression_is_prose(IMPRESSION_JA) == IMPRESSION_JA
    with pytest.raises(ValueError, match="characters"):
        records.impression_is_prose("Looks fine. No issues. Done.")
    with pytest.raises(ValueError, match="sentences"):
        records.impression_is_prose("x" * 500 + ". y")
    with pytest.raises(ValueError, match="repeats"):
        records.impression_is_prose("The drawing is fine and readable overall. " * 12)
    assert records.sentence_count("Supply is 3.3 V and 5.0 V") == 0
    assert HOOK_RECORDS.impression_errors(IMPRESSION) == []
    assert HOOK_RECORDS.impression_errors(IMPRESSION_JA) == []
    assert HOOK_RECORDS.impression_errors("Looks fine. No issues. Done.")


def test_record_impression_binds_artifacts(workspace: Path) -> None:
    result = records.record_impression(
        {"stage": "export", "artifacts": ["out"], "impression": IMPRESSION}
    )
    record = result["record"]
    assert record["artifacts"] == [
        {"path": "out", "sha256": records.tree_sha256(workspace / "out")}
    ]
    assert record["sequence"] == 1
    assert HOOK_RECORDS.record_errors("stage_impression", record) == []
    assert HOOK_RECORDS.tree_sha256(workspace / "out") == records.tree_sha256(workspace / "out")
    with pytest.raises(ValueError, match="outside the workspace"):
        records.record_impression(
            {"stage": "export", "artifacts": ["/etc/passwd"], "impression": IMPRESSION}
        )
    with pytest.raises(ValueError, match="does not exist"):
        records.record_impression(
            {"stage": "export", "artifacts": ["out/missing.csv"], "impression": IMPRESSION}
        )


def test_record_decision_requires_principled_choice(workspace: Path) -> None:
    result = records.record_decision(_decision("out/control-plan.csv"))
    record = result["record"]
    digest = hashlib.sha256((workspace / "out" / "control-plan.csv").read_bytes()).hexdigest()
    assert record["evidence"][0] == {"path": "out/control-plan.csv", "sha256": digest}
    assert record["evidence"][1]["reference"].startswith("approved")
    assert HOOK_RECORDS.record_errors("decision", record) == []
    for key, value in (
        ("options", _decision("out/control-plan.csv")["options"][:1]),
        ("chosen", "teleport"),
        ("rationale", "because"),
        ("principles", []),
        ("principles", ["vibes"]),
        ("risks", []),
        ("evidence", []),
    ):
        bad = _decision("out/control-plan.csv") | {key: value}
        with pytest.raises(ValidationError):
            records.record_decision(bad)
    with pytest.raises(ValidationError):
        records.record_decision(_decision("out/control-plan.csv") | {"surprise": 1})


def test_record_vision_review(workspace: Path) -> None:
    result = records.record_vision_review(
        {
            "image_path": "out/renders/control-plan.png",
            "model": "openhands/kimi-k3",
            "checklist": "control-plan",
            "findings": [{"category": "ambiguous-step", "severity": "warning", "note": "OP-1"}],
            "impression": IMPRESSION,
        }
    )
    record = result["record"]
    assert record["image_sha256"] == hashlib.sha256(b"\x89PNG fake").hexdigest()
    assert HOOK_RECORDS.record_errors("vision_review", record) == []
    with pytest.raises(ValidationError, match="image_path or source_event_id"):
        records.record_vision_review({"model": "m", "checklist": "x", "impression": IMPRESSION})
    event = records.record_vision_review(
        {"source_event_id": "a" * 64, "model": "m", "checklist": "x", "impression": IMPRESSION}
    )
    assert event["record"].get("image_sha256") is None


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("decision", "principles"),
        ("decision", "options"),
        ("decision", "rationale"),
        ("decision", "evidence"),
        ("decision", "risks"),
        ("decision", "revisit_when"),
        ("decision", "unknowns"),
        ("stage_impression", "impression"),
        ("stage_impression", "artifacts"),
        ("vision_review", "impression"),
        ("vision_review", "model"),
        ("vision_review", "recorded_at"),
        ("vision_review", "event_id"),
    ],
)
def test_hook_mirror_rejects_mutations(workspace: Path, kind: str, field: str) -> None:
    writers = {
        "decision": lambda: records.record_decision(_decision("out/control-plan.csv")),
        "stage_impression": lambda: records.record_impression(
            {"stage": "export", "artifacts": ["out"], "impression": IMPRESSION}
        ),
        "vision_review": lambda: records.record_vision_review(
            {
                "image_path": "out/renders/control-plan.png",
                "model": "m",
                "checklist": "control-plan",
                "impression": IMPRESSION,
            }
        ),
    }
    record = dict(writers[kind]()["record"])
    assert HOOK_RECORDS.record_errors(kind, record) == []
    del record[field]
    assert HOOK_RECORDS.record_errors(kind, record)
    record[field] = ""
    assert HOOK_RECORDS.record_errors(kind, record)


def _hook(mode: str, root: Path, session: str = "s1") -> subprocess.CompletedProcess[str]:
    env = dict(os.environ) | {"OPENHANDS_PROJECT_DIR": str(root)}
    return subprocess.run(
        [sys.executable, str(HOOK), mode],
        input=json.dumps({"session_id": session, "working_dir": str(root)}),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _status(root: Path) -> dict[str, Any]:
    path = root / records.RECORDS_DIR / "records-status.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stop_without_marker_allows(tmp_path: Path) -> None:
    assert _hook("stop", tmp_path).returncode == 0


def test_stop_clean_session_passes(tmp_path: Path) -> None:
    assert _hook("session-start", tmp_path).returncode == 0
    result = _hook("stop", tmp_path)
    assert result.returncode == 0, result.stdout
    assert _status(tmp_path)["verdict"] == "pass"


def test_stop_enforces_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    assert _hook("session-start", tmp_path).returncode == 0
    out = tmp_path / "out"
    out.mkdir()
    (out / "control-plan.csv").write_text("operation\n", encoding="utf-8")
    renders = out / "renders"
    renders.mkdir()
    (renders / "control-plan.png").write_bytes(b"png")
    log = tmp_path / records.RECORDS_DIR
    event = {"event_id": "b" * 64, "question": "is it legible?", "session_id": "s1"}
    (log / "vision-tool-events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    denied = _hook("stop", tmp_path)
    assert denied.returncode == 2
    payload = json.loads(denied.stdout)
    assert payload["decision"] == "deny"
    assert "out/control-plan.csv" in payload["additionalContext"]
    assert "vision tool event" in payload["additionalContext"]
    assert "no decision record" in payload["additionalContext"]
    assert _status(tmp_path)["verdict"] == "fail"

    records.record_decision(_decision("out/control-plan.csv"))
    records.record_impression(
        {"stage": "projections", "artifacts": ["out"], "impression": IMPRESSION}
    )
    records.record_vision_review(
        {"source_event_id": "b" * 64, "model": "m", "checklist": "q", "impression": IMPRESSION}
    )
    passed = _hook("stop", tmp_path)
    assert passed.returncode == 0, passed.stdout
    assert _status(tmp_path)["verdict"] == "pass"

    (out / "control-plan.csv").write_text("operation,inspection\n", encoding="utf-8")
    stale = _hook("stop", tmp_path)
    assert stale.returncode == 2
    assert "no fresh stage_impression" in json.loads(stale.stdout)["reason"]

    released = _hook("stop", tmp_path)
    assert released.returncode == 0
    assert json.loads(released.stdout)["decision"] == "allow"
    assert "still unmet" in json.loads(released.stdout)["additionalContext"]


def test_stop_flags_tampered_and_malformed_lines(tmp_path: Path) -> None:
    assert _hook("session-start", tmp_path).returncode == 0
    log = tmp_path / records.RECORDS_DIR
    forged = {
        "schema_version": 1,
        "kind": "stage_impression",
        "plugin": "prodeng",
        "sequence": 1,
        "event_id": "c" * 64,
        "recorded_at": "2999-01-01T00:00:00+00:00",
        "stage": "export",
        "artifacts": [{"path": "out", "sha256": "d" * 64}],
        "impression": "ok.",
    }
    (log / "impressions.jsonl").write_text(json.dumps(forged) + "\n{not json\n", encoding="utf-8")
    result = _hook("stop", tmp_path)
    assert result.returncode == 2
    reason = json.loads(result.stdout)["reason"]
    assert "malformed" in reason
    assert "invalid stage_impression" in reason


def test_viewed_image_needs_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    assert _hook("session-start", tmp_path).returncode == 0
    log = tmp_path / records.RECORDS_DIR
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"jpg")
    digest = hashlib.sha256(b"jpg").hexdigest()
    observation = {
        "event_id": "e" * 64,
        "image_path": str(image),
        "image_sha256": digest,
        "session_id": "s1",
    }
    (log / "image-observations.jsonl").write_text(json.dumps(observation) + "\n", encoding="utf-8")
    assert _hook("stop", tmp_path).returncode == 2
    records.record_vision_review(
        {
            "image_path": "photo.jpg",
            "model": "m",
            "checklist": "intake-image",
            "impression": IMPRESSION,
        }
    )
    assert _hook("stop", tmp_path).returncode == 0


def test_records_policy_matches_core() -> None:
    policy = HOOK_RECORDS.load_policy(SCRIPTS.parents[1])
    assert policy["plugin"] == records.PLUGIN
    assert policy["records_dir"] == records.RECORDS_DIR.as_posix()
    assert HOOK_RECORDS.IMPRESSION_MIN_CHARS == records.IMPRESSION_MIN_CHARS
    assert HOOK_RECORDS.IMPRESSION_MIN_SENTENCES == records.IMPRESSION_MIN_SENTENCES
    assert HOOK_RECORDS.RATIONALE_MIN_CHARS == records.RATIONALE_MIN_CHARS
    assert HOOK_RECORDS.LOG_FILES == records.LOG_FILES
    assert set(records.Severity.__args__) == HOOK_RECORDS.SEVERITIES
    hooks = json.loads((SCRIPTS.parent / "hooks.json").read_text(encoding="utf-8"))
    session_hooks = [h["name"] for group in hooks["session_start"] for h in group["hooks"]]
    stop_hooks = [h["name"] for group in hooks["stop"] for h in group["hooks"]]
    assert session_hooks[-1] == "require-records"
    assert stop_hooks[0] == "require-records"
