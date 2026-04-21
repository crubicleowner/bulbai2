from __future__ import annotations

import zipfile
from pathlib import Path


class CasePackageExporter:
    """Bundle a completed case folder into a portable ``.zip`` archive.

    Implements spec §6.5 "archived case package": after the pipeline finishes,
    the engineer needs a single file they can send to a colleague, attach to a
    PR, or store in a shared drive. By default ``working/checkpoints/`` is
    excluded so the archive stays engineering-focused; pass
    ``include_checkpoints=True`` when the recipient needs to resume or audit
    stage-by-stage execution.
    """

    # Artifact roots that are considered "engineering payload" — everything
    # else in the case folder is runtime state.
    ARCHIVE_ROOTS: tuple[str, ...] = (
        "input",
        "working/repaired",
        "working/masks",
        "working/candidates",
        "working/evaluation",
        "working/openfoam_case",
        "outputs/reports",
        "outputs/geometry",
        "outputs/plots",
        "outputs/tables",
        "logs",
    )
    ROOT_FILES: tuple[str, ...] = (
        "case.json",
        "metadata.json",
        "artifacts_index.json",
        "candidate_index.json",
        "evaluation_index.json",
    )

    def export(
        self,
        case_dir: Path,
        output_dir: Path,
        *,
        include_checkpoints: bool = False,
    ) -> Path:
        case_dir = Path(case_dir)
        if not case_dir.exists() or not case_dir.is_dir():
            raise FileNotFoundError(f"Case directory does not exist: {case_dir.name}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / f"{case_dir.name}.zip"

        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            self._write_root_files(archive, case_dir)
            for root_name in self.ARCHIVE_ROOTS:
                self._write_subtree(
                    archive,
                    case_dir=case_dir,
                    root_name=root_name,
                )
            if include_checkpoints:
                self._write_subtree(
                    archive,
                    case_dir=case_dir,
                    root_name="working/checkpoints",
                )

        return archive_path

    def _write_root_files(self, archive: zipfile.ZipFile, case_dir: Path) -> None:
        for name in self.ROOT_FILES:
            source = case_dir / name
            if source.exists() and source.is_file():
                archive.write(source, arcname=f"{case_dir.name}/{name}")

    def _write_subtree(
        self,
        archive: zipfile.ZipFile,
        *,
        case_dir: Path,
        root_name: str,
    ) -> None:
        root_path = case_dir / root_name
        if not root_path.exists() or not root_path.is_dir():
            return
        for child in sorted(root_path.rglob("*")):
            if not child.is_file():
                continue
            arcname = f"{case_dir.name}/{child.relative_to(case_dir).as_posix()}"
            archive.write(child, arcname=arcname)
