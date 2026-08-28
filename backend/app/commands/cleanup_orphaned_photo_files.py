"""Remove old photo files that are no longer referenced by PostgreSQL."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.commands.check_photo_integrity import IntegrityReport, check_photo_integrity
from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.photos.storage.facade import PhotoStorage

ORPHAN_ISSUE_CODES = frozenset({"orphan_original", "orphan_sidecar", "orphan_derivative", "orphan_part"})
DEFAULT_MIN_AGE = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class OrphanFileCandidate:
    path: Path
    issue_code: str


@dataclass(frozen=True, slots=True)
class OrphanCleanupReport:
    integrity_report: IntegrityReport
    candidates: tuple[OrphanFileCandidate, ...]
    eligible_candidates: tuple[OrphanFileCandidate, ...]
    removed: tuple[OrphanFileCandidate, ...]
    skipped_recent: tuple[OrphanFileCandidate, ...]
    errors: tuple[str, ...]
    blocked_reason: str | None = None


def _path_is_under_root(path: Path, root: Path) -> bool:
    try:
        path.parent.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, NotADirectoryError, OSError, ValueError):
        return False
    return True


def _candidate_root(candidate: OrphanFileCandidate, storage_root: Path, derivative_root: Path) -> Path:
    if candidate.issue_code == "orphan_derivative" or (
        candidate.issue_code == "orphan_part" and _path_is_under_root(candidate.path, derivative_root)
    ):
        return derivative_root
    return storage_root


def _is_safe_regular_file(path: Path, root: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    return _path_is_under_root(path, root)


def _collect_candidates(report: IntegrityReport) -> tuple[OrphanFileCandidate, ...]:
    candidates: list[OrphanFileCandidate] = []
    seen: set[tuple[str, str]] = set()
    for issue in report.issues:
        if issue.code not in ORPHAN_ISSUE_CODES:
            continue
        key = (issue.code, issue.path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(OrphanFileCandidate(Path(issue.path), issue.code))
    return tuple(candidates)


def cleanup_orphaned_photo_files(
    session: Session,
    storage: PhotoStorage,
    storage_root: Path,
    derivative_root: Path,
    *,
    apply: bool = False,
    allow_empty_database: bool = False,
    min_age: timedelta = DEFAULT_MIN_AGE,
    now: datetime | None = None,
) -> OrphanCleanupReport:
    if min_age < timedelta(0):
        raise ValueError("min_age must not be negative")

    integrity_report = check_photo_integrity(session, storage, storage_root, derivative_root)
    candidates = _collect_candidates(integrity_report)
    if not candidates:
        return OrphanCleanupReport(integrity_report, (), (), (), (), ())

    if apply and integrity_report.checked_photos == 0 and not allow_empty_database:
        return OrphanCleanupReport(
            integrity_report,
            candidates,
            (),
            (),
            (),
            (),
            blocked_reason=(
                "Refusing to remove orphaned files while the database contains no photos; "
                "verify the database target or pass --allow-empty-database for an intentional reset"
            ),
        )

    current_time = now or datetime.now(UTC)
    cutoff = current_time - min_age
    eligible: list[OrphanFileCandidate] = []
    skipped_recent: list[OrphanFileCandidate] = []
    errors: list[str] = []
    for candidate in candidates:
        root = _candidate_root(candidate, storage_root, derivative_root)
        if not _is_safe_regular_file(candidate.path, root):
            errors.append(f"unsafe_or_missing:{candidate.path}")
            continue
        try:
            modified_at = datetime.fromtimestamp(candidate.path.stat().st_mtime, tz=UTC)
        except OSError:
            errors.append(f"stat_failed:{candidate.path}")
            continue
        if modified_at > cutoff:
            skipped_recent.append(candidate)
        else:
            eligible.append(candidate)

    removed: list[OrphanFileCandidate] = []
    if apply:
        for candidate in eligible:
            try:
                candidate.path.unlink(missing_ok=True)
            except OSError as error:
                errors.append(f"delete_failed:{candidate.path}:{type(error).__name__}")
            else:
                removed.append(candidate)

    return OrphanCleanupReport(
        integrity_report,
        candidates,
        tuple(eligible),
        tuple(removed),
        tuple(skipped_recent),
        tuple(errors),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect and optionally remove old photo files not referenced by PostgreSQL"
    )
    parser.add_argument("--apply", action="store_true", help="Remove eligible files; otherwise only report them")
    parser.add_argument(
        "--allow-empty-database",
        action="store_true",
        help="Allow cleanup when PostgreSQL has no photos; use only for an intentional full reset",
    )
    parser.add_argument(
        "--min-age-hours",
        type=float,
        default=DEFAULT_MIN_AGE.total_seconds() / 3600,
        help="Only remove files at least this many hours old (default: 24)",
    )
    return parser.parse_args()


def _print_candidates(label: str, candidates: tuple[OrphanFileCandidate, ...]) -> None:
    for candidate in candidates:
        print(f"{label}:{candidate.issue_code} path={candidate.path}")


def main() -> None:
    args = _parse_args()
    if args.min_age_hours < 0:
        raise SystemExit("--min-age-hours must not be negative")
    if args.allow_empty_database and not args.apply:
        raise SystemExit("--allow-empty-database requires --apply")

    settings = get_management_settings()
    if settings.photo_storage_root is None:
        raise SystemExit("PHOTO_STORAGE_ROOT is not configured")
    storage = PhotoStorage(settings)
    storage_status = storage.get_read_status()
    if not storage_status.available:
        raise SystemExit(f"Photo storage is unavailable: {storage_status.status}")

    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            report = cleanup_orphaned_photo_files(
                session,
                storage,
                settings.photo_storage_root,
                settings.photo_derivative_root,
                apply=args.apply,
                allow_empty_database=args.allow_empty_database,
                min_age=timedelta(hours=args.min_age_hours),
            )
            final_integrity_report = report.integrity_report
            if args.apply and report.removed:
                final_integrity_report = check_photo_integrity(
                    session,
                    storage,
                    settings.photo_storage_root,
                    settings.photo_derivative_root,
                )
    finally:
        engine.dispose()

    print(
        f"Checked {report.integrity_report.checked_photos} photo(s) and "
        f"{report.integrity_report.checked_derivatives} derivative(s)"
    )
    _print_candidates("candidate", report.candidates)
    _print_candidates("removed", report.removed)
    _print_candidates("recent", report.skipped_recent)
    for error in report.errors:
        print(f"error:{error}")
    if report.blocked_reason:
        print(f"blocked:{report.blocked_reason}")
    if final_integrity_report.clean:
        print("No remaining integrity issues found")
        return
    for issue in final_integrity_report.issues:
        photo = f" photo={issue.photo_id}" if issue.photo_id is not None else ""
        print(f"remaining:{issue.code}:{photo} path={issue.path}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
