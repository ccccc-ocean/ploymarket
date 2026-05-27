from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
import tempfile
import time


@dataclass(frozen=True)
class HealthAssessment:
    healthy: bool
    reason: str
    status: str
    age_seconds: int | None


def load_state(state_dir: str | Path, pipeline: str) -> dict | None:
    path = _state_path(state_dir, pipeline)
    if not path.exists():
        return None
    with path.open() as handle:
        return json.load(handle)


def mark_started(
    state_dir: str | Path,
    pipeline: str,
    run_id: str,
    started_at: int,
    recovery_reason: str = "",
) -> dict:
    previous = load_state(state_dir, pipeline) or {}
    state = {
        "pipeline": pipeline,
        "status": "running",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": None,
        "exit_code": None,
        "last_step": "",
        "recovery_reason": recovery_reason,
        "last_success_at": previous.get("last_success_at"),
    }
    _write_state(state_dir, pipeline, state)
    return state


def mark_finished(
    state_dir: str | Path,
    pipeline: str,
    run_id: str,
    completed_at: int,
    exit_code: int,
    last_step: str = "",
) -> dict:
    previous = load_state(state_dir, pipeline) or {}
    started_at = previous.get("started_at") if previous.get("run_id") == run_id else None
    status = "success" if exit_code == 0 else "failed"
    state = {
        "pipeline": pipeline,
        "status": status,
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "exit_code": exit_code,
        "last_step": last_step,
        "recovery_reason": previous.get("recovery_reason", ""),
        "last_success_at": completed_at if exit_code == 0 else previous.get("last_success_at"),
    }
    _write_state(state_dir, pipeline, state)
    return state


def assess_health(
    state: dict | None,
    now: int,
    max_success_age_seconds: int,
    max_running_age_seconds: int,
) -> HealthAssessment:
    if state is None:
        return HealthAssessment(False, "missing_state", "missing", None)

    status = str(state.get("status", "unknown"))
    if status == "running":
        started_at = state.get("started_at")
        if not isinstance(started_at, int):
            return HealthAssessment(False, "running_without_start_time", status, None)
        age = max(0, now - started_at)
        if age <= max_running_age_seconds:
            return HealthAssessment(True, "running", status, age)
        return HealthAssessment(False, "running_stale", status, age)

    if status == "failed":
        completed_at = state.get("completed_at")
        age = max(0, now - completed_at) if isinstance(completed_at, int) else None
        step = str(state.get("last_step", "") or "unknown")
        return HealthAssessment(False, f"failed_at_{step}", status, age)

    if status == "success":
        last_success_at = state.get("last_success_at")
        if not isinstance(last_success_at, int):
            return HealthAssessment(False, "success_without_timestamp", status, None)
        age = max(0, now - last_success_at)
        if age <= max_success_age_seconds:
            return HealthAssessment(True, "recent_success", status, age)
        return HealthAssessment(False, "success_stale", status, age)

    return HealthAssessment(False, "unknown_status", status, None)


def append_event(
    state_dir: str | Path,
    timestamp: int,
    pipeline: str,
    reason: str,
    action: str,
    outcome: str,
) -> Path:
    directory = Path(state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "watchdog_events.csv"
    new_file = not path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["timestamp", "pipeline", "reason", "action", "outcome"])
        writer.writerow([timestamp, pipeline, reason, action, outcome])
    return path


def _state_path(state_dir: str | Path, pipeline: str) -> Path:
    return Path(state_dir) / f"{pipeline}.json"


def _write_state(state_dir: str | Path, pipeline: str, state: dict) -> None:
    directory = Path(state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _state_path(directory, pipeline)
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as handle:
        json.dump(state, handle, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Track and evaluate unattended pipeline health")
    parser.add_argument("--state-dir", default="runtime/data/health")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--pipeline", required=True)
    start_parser.add_argument("--run-id", required=True)
    start_parser.add_argument("--timestamp", type=int, required=True)
    start_parser.add_argument("--recovery-reason", default="")

    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("--pipeline", required=True)
    finish_parser.add_argument("--run-id", required=True)
    finish_parser.add_argument("--timestamp", type=int, required=True)
    finish_parser.add_argument("--exit-code", type=int, required=True)
    finish_parser.add_argument("--last-step", default="")

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--pipeline", required=True)
    check_parser.add_argument("--timestamp", type=int, default=None)
    check_parser.add_argument("--max-success-age-seconds", type=int, required=True)
    check_parser.add_argument("--max-running-age-seconds", type=int, required=True)

    event_parser = subparsers.add_parser("event")
    event_parser.add_argument("--pipeline", required=True)
    event_parser.add_argument("--timestamp", type=int, required=True)
    event_parser.add_argument("--reason", required=True)
    event_parser.add_argument("--action", required=True)
    event_parser.add_argument("--outcome", required=True)

    args = parser.parse_args()
    if args.command == "start":
        state = mark_started(args.state_dir, args.pipeline, args.run_id, args.timestamp, args.recovery_reason)
        print(f"pipeline_health | pipeline={args.pipeline} | status={state['status']} | run_id={args.run_id}")
        return
    if args.command == "finish":
        state = mark_finished(
            args.state_dir, args.pipeline, args.run_id, args.timestamp, args.exit_code, args.last_step
        )
        print(
            f"pipeline_health | pipeline={args.pipeline} | status={state['status']} | "
            f"run_id={args.run_id} | last_step={args.last_step} | exit_code={args.exit_code}"
        )
        return
    if args.command == "event":
        path = append_event(
            args.state_dir, args.timestamp, args.pipeline, args.reason, args.action, args.outcome
        )
        print(
            f"pipeline_watchdog_event | pipeline={args.pipeline} | reason={args.reason} | "
            f"action={args.action} | outcome={args.outcome} | {path}"
        )
        return

    assessment = assess_health(
        load_state(args.state_dir, args.pipeline),
        int(time.time()) if args.timestamp is None else args.timestamp,
        args.max_success_age_seconds,
        args.max_running_age_seconds,
    )
    age = "none" if assessment.age_seconds is None else assessment.age_seconds
    print(
        f"pipeline_health_check | pipeline={args.pipeline} | healthy={str(assessment.healthy).lower()} | "
        f"status={assessment.status} | reason={assessment.reason} | age_seconds={age}"
    )
    raise SystemExit(0 if assessment.healthy else 1)


if __name__ == "__main__":
    main()
