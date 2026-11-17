"""Execute a frozen final-campaign manifest with resumable cell checkpoints."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def trial_directory(root, row):
    return (root / row["scenario"] / row["telemetry_condition"]
            / row["initial_bottleneck_path"] / row["policy"]
            / f"rep_{int(row['repetition']):03d}")


def execute(manifest_path, output_root, *, dry_run=False, resume=False, limit=None,
            venv=".venv", controller_ip="127.0.0.1", controller_port=6653):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("split") == "development":
        raise ValueError("development manifest cannot be used as a final test campaign")
    if not manifest.get("trials"):
        raise ValueError("manifest contains no trials")
    rows = manifest["trials"][:limit] if limit else manifest["trials"]
    root = Path(output_root).resolve()
    runner = Path(__file__).with_name("run_final_scenario_trial.py")
    completed = 0
    for index, row in enumerate(rows, 1):
        target = trial_directory(root, row)
        result_path = target / "trial_result.json"
        if result_path.exists():
            if not resume:
                raise FileExistsError(f"{result_path} exists; use --resume")
            existing = json.loads(result_path.read_text(encoding="utf-8"))
            expected = (
                row["policy"], row["scenario"], row["telemetry_condition"],
                row["initial_bottleneck_path"], int(row["repetition"]), int(row["workload_seed"]),
            )
            actual = (
                existing.get("policy"), existing.get("scenario"),
                "baseline" if existing.get("telemetry_delay_seconds") == 0
                    and existing.get("telemetry_noise_std") == 0 else
                "delayed" if existing.get("telemetry_delay_seconds") > 0
                    and existing.get("telemetry_noise_std") == 0 else
                "noisy" if existing.get("telemetry_delay_seconds") == 0 else "combined",
                existing.get("initial_bottleneck_path"), int(existing.get("repetition")),
                int(existing.get("seed")),
            )
            if actual != expected:
                raise ValueError(f"existing trial does not match manifest: {result_path}")
            completed += 1
            continue

        delay = float(row["delay_s"])
        warmup = max(6.0, delay + 4.0)
        command = [
            sys.executable, str(runner),
            "--policy", row["policy"],
            "--scenario", row["scenario"],
            "--condition", row["telemetry_condition"],
            "--initial-path", row["initial_bottleneck_path"],
            "--repetition", str(row["repetition"]),
            "--seed", str(row["workload_seed"]),
            "--output-dir", str(target),
            "--venv", venv,
            "--controller-ip", controller_ip,
            "--controller-port", str(controller_port),
            "--warmup-seconds", str(warmup),
        ]
        print(f"[{index}/{len(rows)}] {' '.join(command)}", flush=True)
        if dry_run:
            continue
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True, env={
            **os.environ, "PYTHONPATH": str(Path.cwd()),
            "EVENTLET_NO_GREENDNS": "yes",
        })
        if not result_path.is_file():
            raise RuntimeError(f"trial exited without result artifact: {result_path}")
        completed += 1
    return {"planned": len(rows), "completed_or_skipped": completed,
            "dry_run": dry_run, "output_root": str(root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path("results/final_campaign_manifest.json"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("results/final_campaign"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int,
                        help="execute only the first N manifest rows for rehearsal")
    parser.add_argument("--venv", default=".venv")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    summary = execute(
        args.manifest, args.output_root, dry_run=args.dry_run,
        resume=args.resume, limit=args.limit, venv=args.venv,
        controller_ip=args.controller_ip, controller_port=args.controller_port,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
