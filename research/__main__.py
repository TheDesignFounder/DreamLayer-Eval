from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__, analysis, bundles, comparison, experiments, fixtures, human, judges
from .contracts import record
from .store import Store


def main() -> None:
    "Execute the research CLI and emit JSON results or validation errors."
    parser = argparse.ArgumentParser(description="DreamLayer reproducible research workbench")
    parser.add_argument("--db", default=".research/research.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=5055)
    demo = sub.add_parser("demo")
    demo.add_argument("--directory", default=".research/fixtures")
    create = sub.add_parser("create")
    create.add_argument("config")
    preview = sub.add_parser("preview")
    preview.add_argument("config")
    preview.add_argument("--output")
    rankings = sub.add_parser("import-rankings")
    rankings.add_argument("file")
    for name in ("compare", "comparison-rows", "analysis-input"):
        cmd = sub.add_parser(name)
        cmd.add_argument("experiment_id")
        cmd.add_argument("--label-view", default="raw", choices=["raw", "adjudicated"])
        cmd.add_argument("--filters", default="{}")
        cmd.add_argument("--output")
        if name == "analysis-input":
            cmd.add_argument("operation", choices=["binary", "correlations", "paired", "selection"])
    retry_judge = sub.add_parser("retry-judge")
    retry_judge.add_argument("request_id")
    retry_judge.add_argument("--note", required=True)
    retry_judge.add_argument("--allow-unknown-delivery", action="store_true")
    retry_judge.add_argument("--additional-calls", type=int, default=1)
    retry_judge.add_argument("--additional-frames", type=int, default=40)
    retry_judge.add_argument("--additional-tokens", type=int, default=1000000)
    reconcile = sub.add_parser("reconcile-judge")
    reconcile.add_argument("request_id")
    reconcile.add_argument("resolution", choices=["not_delivered", "abandon", "completed"])
    reconcile.add_argument("--note", required=True)
    reconcile.add_argument("--response")
    for name in ("plan", "run", "cancel", "analyze"):
        cmd = sub.add_parser(name)
        cmd.add_argument("experiment_id")
        if name == "run":
            cmd.add_argument("--limit", type=int)
            cmd.add_argument("--rerun-failed", action="store_true")
            cmd.add_argument("--upgrade-evaluators", action="store_true")
        if name == "analyze":
            cmd.add_argument("--seed", type=int, default=0)
            cmd.add_argument("--label-view", choices=["raw", "adjudicated"], default="raw")
    export = sub.add_parser("export")
    export.add_argument("experiment_id")
    export.add_argument("output")
    export.add_argument("--references-only", action="store_true")
    load = sub.add_parser("import")
    load.add_argument("bundle")
    load.add_argument("--media-lookup")
    assign = sub.add_parser("assign")
    assign.add_argument("experiment_id")
    assign.add_argument("rater_id")
    assign.add_argument("rubric")
    assign.add_argument("--mode", default="pointwise")
    assign.add_argument("--seed", type=int, default=0)
    assign.add_argument(
        "--practice", help="JSON file listing practice prompt source IDs or asset IDs"
    )
    annotate = sub.add_parser("annotate")
    annotate.add_argument("assignment_id")
    annotate.add_argument("annotation")
    for name in ("labels-export", "labels-import"):
        cmd = sub.add_parser(name)
        cmd.add_argument("experiment_id")
        cmd.add_argument("file")
        cmd.add_argument("--format", default="jsonl", choices=["csv", "jsonl"])
        if name == "labels-export":
            cmd.add_argument("--blinded", action="store_true")
    stats = sub.add_parser("statistics")
    stats.add_argument(
        "operation",
        choices=[
            "binary",
            "correlations",
            "paired",
            "agreement",
            "selection",
            "bootstrap",
            "threshold",
        ],
    )
    stats.add_argument("input")
    stats.add_argument("--options", default="{}")
    stats.add_argument("--experiment-id")
    stats.add_argument("--output")
    history = sub.add_parser("recover")
    history.add_argument("downloads")
    history.add_argument("output")
    history.add_argument("--limit", type=int)
    ml = sub.add_parser("ml-smoke")
    ml.add_argument("--allow-download", action="store_true")
    retry = sub.add_parser("retry-generation")
    retry.add_argument("trial_id")
    args = parser.parse_args()
    store = Store(args.db)
    media_root = Path(args.db).resolve().parent / "media"
    output = None
    if args.command == "serve":
        from .api import create_app

        create_app(args.db, media_root).run(
            host="127.0.0.1", port=args.port, threaded=True, debug=False
        )
    elif args.command == "create":
        output = experiments.create(store, json.loads(Path(args.config).read_text()), media_root)
    elif args.command == "demo":
        config = fixtures.create(args.directory)
        exp = experiments.create(store, config, media_root)
        experiments.execute(store, exp["id"], media_root)
        output = {"experiment_id": exp["id"], "analysis": analysis.summarize(store, exp["id"])}
    elif args.command == "plan":
        output = experiments.plan(store, args.experiment_id)
    elif args.command == "run":
        import sys

        from .upgrades import UpgradeRefused, warnings

        for notice in warnings(
            store, args.experiment_id, args.upgrade_evaluators, args.rerun_failed
        ):
            print(notice["message"], file=sys.stderr)
        try:
            output = experiments.execute(
                store,
                args.experiment_id,
                media_root,
                limit=args.limit,
                rerun_failed=args.rerun_failed,
                upgrade_evaluators=args.upgrade_evaluators,
            )
        except UpgradeRefused as exc:
            parser.exit(1, f"error: {' '.join(str(exc).split())}\n")
    elif args.command == "preview":
        output = experiments.preview(json.loads(Path(args.config).read_text()))
        if args.output:
            Path(args.output).write_text(json.dumps(output["config"], indent=2))
    elif args.command in {"compare", "comparison-rows", "analysis-input"}:
        options = {"label_view": args.label_view, "filters": json.loads(args.filters)}
        output = (
            comparison.analysis_input(store, args.experiment_id, args.operation, **options)
            if args.command == "analysis-input"
            else (comparison.compare if args.command == "compare" else comparison.joined_rows)(
                store, args.experiment_id, **options
            )
        )
        if args.output:
            Path(args.output).write_text(json.dumps(output, indent=2, allow_nan=False))
    elif args.command == "retry-judge":
        output = judges.retry_request(
            store,
            args.request_id,
            args.note,
            args.allow_unknown_delivery,
            args.additional_calls,
            args.additional_frames,
            args.additional_tokens,
        )
    elif args.command == "reconcile-judge":
        output = judges.reconcile_request(
            store,
            args.request_id,
            args.resolution,
            args.note,
            json.loads(Path(args.response).read_text()) if args.response else None,
        )
    elif args.command == "import-rankings":
        from .historical_import import import_rankings

        output = import_rankings(store, args.file)
    elif args.command == "cancel":
        output = store.job(args.experiment_id, cancel=1)
    elif args.command == "analyze":
        output = analysis.summarize(
            store, args.experiment_id, seed=args.seed, label_view=args.label_view
        )
        store.put(
            record(
                "analysis",
                args.experiment_id,
                config={"seed": args.seed, "label_view": args.label_view},
                output=output,
                implementation=f"dreamlayer-research-{__version__}",
            )
        )
    elif args.command == "export":
        output = bundles.export_bundle(
            store, args.experiment_id, args.output, not args.references_only
        )
    elif args.command == "import":
        output = bundles.import_bundle(
            store,
            args.bundle,
            media_root,
            json.loads(Path(args.media_lookup).read_text()) if args.media_lookup else None,
        )
    elif args.command == "assign":
        output = human.assign(
            store,
            args.experiment_id,
            args.rater_id,
            json.loads(Path(args.rubric).read_text()),
            args.mode,
            args.seed,
            json.loads(Path(args.practice).read_text()) if args.practice else None,
        )
    elif args.command == "annotate":
        output = human.annotate(
            store, args.assignment_id, json.loads(Path(args.annotation).read_text())
        )
    elif args.command == "labels-export":
        Path(args.file).write_text(
            human.export_annotations(
                store, args.experiment_id, args.format, blinded_export=args.blinded
            )
        )
        output = args.file
    elif args.command == "labels-import":
        output = human.import_annotations(store, Path(args.file).read_text(), args.format)
    elif args.command == "statistics":
        functions = {
            "binary": analysis.binary_errors,
            "correlations": lambda data: analysis.correlations(data["x"], data["y"]),
            "paired": analysis.paired_difference,
            "agreement": analysis.agreement,
            "selection": analysis.selection,
            "bootstrap": analysis.cluster_interval,
            "threshold": analysis.choose_threshold,
        }
        output = functions[args.operation](
            json.loads(Path(args.input).read_text()), **json.loads(args.options)
        )
        from .contracts import file_hash

        saved = record(
            "analysis",
            args.experiment_id,
            config={
                "operation": args.operation,
                "options": json.loads(args.options),
                "input_sha256": file_hash(args.input),
                "input": json.loads(Path(args.input).read_text()),
            },
            output=output,
            implementation=f"dreamlayer-research-{__version__}",
        )
        if args.experiment_id:
            store.get(args.experiment_id)
            store.put(saved)
        if args.output:
            Path(args.output).write_text(json.dumps(saved, indent=2, allow_nan=False))
    elif args.command == "recover":
        from .history import recover

        recovered = recover(args.downloads, args.output, args.limit)
        output = {
            k: v
            for k, v in recovered.items()
            if k not in {"conflicts", "unresolved", "human", "workbook_sheets"}
        }
    elif args.command == "ml-smoke":
        from .ml_smoke import run

        output = run(media_root.parent / "ml-smoke", args.allow_download)
    elif args.command == "retry-generation":
        from .generation import generate

        trial = store.get(args.trial_id)
        output = generate(
            store,
            trial["experiment_id"],
            trial,
            store.get(trial["prompt_id"]),
            media_root,
            retry=True,
        )
    if output is not None:
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
