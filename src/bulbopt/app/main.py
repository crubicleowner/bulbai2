from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def build_cli_banner() -> str:
    return "BulbOpt Desktop | STL-first vertical slice"


def default_project_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "BulbOpt" / "projects"
    return Path.home() / ".bulbopt" / "projects"


def run_desktop() -> int:
    from PySide6.QtWidgets import QApplication

    from bulbopt.ui.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(project_root=default_project_root())
    window.show()
    return app.exec()


def run_cli(argv: list[str]) -> int:
    """Headless entrypoint for overnight/SSH/CI runs (spec §1).

    Subcommands:
      * ``run``    -- execute a new vertical slice case
      * ``list``   -- list persisted cases
      * ``resume`` -- continue a recoverable case from its checkpoints
    """

    parser = argparse.ArgumentParser(
        prog="bulbopt",
        description="BulbOpt Desktop headless CLI for STL-first bulbous bow generation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a new vertical slice case")
    run_parser.add_argument("--source", required=True, help="Source STL path")
    run_parser.add_argument("--project", required=True, help="Project root directory")
    run_parser.add_argument("--case-name", default="cli-case", help="Case name")
    run_parser.add_argument("--candidate-count", type=int, default=3)
    run_parser.add_argument("--runtime-budget-hours", type=int, default=8)
    run_parser.add_argument(
        "--optimization-mode",
        choices=["generate_new_bulb", "local_optimize"],
        default="generate_new_bulb",
    )

    list_parser = subparsers.add_parser("list", help="List persisted cases")
    list_parser.add_argument("--project", required=True)

    resume_parser = subparsers.add_parser(
        "resume", help="Resume a recoverable case from its checkpoints"
    )
    resume_parser.add_argument("--project", required=True)
    resume_parser.add_argument("--case", required=True)

    if not argv:
        parser.print_help(sys.stderr)
        return 2

    namespace = parser.parse_args(argv)

    if namespace.command == "run":
        from bulbopt.application.contracts.models import CreateCaseCommand
        from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice

        project_root = Path(namespace.project)
        command = CreateCaseCommand(
            case_name=namespace.case_name,
            source_path=str(Path(namespace.source).resolve()),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            candidate_count=int(namespace.candidate_count),
            runtime_budget_hours=int(namespace.runtime_budget_hours),
            optimization_mode=str(namespace.optimization_mode),
        )
        try:
            summary = run_vertical_slice(project_root=project_root, command=command)
        except Exception as error:
            print(f"Run failed: {error}", file=sys.stderr)
            return 1
        print(
            f"{summary.status}: case_id={summary.case_id} "
            f"case_name={summary.case_name} best={summary.best_candidate_id or 'n/a'}"
        )
        return 0

    if namespace.command == "list":
        from bulbopt.storage.project_repository.filesystem_repository import (
            FilesystemProjectRepository,
        )

        repository = FilesystemProjectRepository(root_dir=Path(namespace.project))
        summaries = repository.list_cases()
        if not summaries:
            print("No cases found")
            return 0
        for summary in summaries:
            recoverable = " [recoverable]" if summary.get("is_recoverable") else ""
            print(
                f"{summary.get('case_id', 'n/a')} | {summary.get('case_name', 'n/a')} "
                f"status={summary.get('status', 'n/a')}{recoverable} "
                f"updated={summary.get('updated_at', 'n/a')}"
            )
        return 0

    if namespace.command == "resume":
        from bulbopt.application.use_cases.run_vertical_slice import resume_vertical_slice

        try:
            summary = resume_vertical_slice(
                project_root=Path(namespace.project),
                case_id=namespace.case,
            )
        except Exception as error:
            print(f"Resume failed: {error}", file=sys.stderr)
            return 1
        print(
            f"{summary.status}: case_id={summary.case_id} "
            f"best={summary.best_candidate_id or 'n/a'}"
        )
        return 0

    parser.print_help(sys.stderr)
    return 2


def dispatch_main(
    run_shell=run_desktop,
    print_banner=print,
    launched_as_module: bool | None = None,
    argv: list[str] | None = None,
) -> int:
    if launched_as_module is None:
        launched_as_module = __spec__ is not None

    # Only route to the CLI when caller explicitly passed argv (i.e. main
    # entry). This preserves the old test contract where ``launched_as_module``
    # alone still means "launch desktop shell".
    if argv:
        return run_cli(argv)

    if launched_as_module:
        return run_shell()

    print_banner(build_cli_banner())
    return 0


if __name__ == "__main__":
    raise SystemExit(dispatch_main(argv=sys.argv[1:] or None))
