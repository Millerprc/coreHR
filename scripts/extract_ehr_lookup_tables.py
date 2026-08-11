#!/usr/bin/env python3
"""Extract approved lookup tables from a large MySQL dump without loading PII.

Only ``country``, ``ehr_dict`` and ``ehr_dict_element`` DDL/INSERT statements
are copied. Other table sections are scanned for structural markers and are
never written to the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


CREATE_TOKEN = b"CREATE TABLE"
INSERT_TOKEN = b"INSERT INTO"
TARGET_TABLES = ("country", "ehr_dict", "ehr_dict_element")
LAST_TARGET_TABLE = TARGET_TABLES[-1]
TOKEN_OVERLAP_BYTES = 512
MAX_DDL_BYTES = 16 * 1024 * 1024
DEFAULT_READ_CHUNK_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_INSERT_BYTES = 256 * 1024 * 1024
PROGRESS_BYTES = 5 * 1024**3

CREATE_NAME_RE = re.compile(
    rb"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    rb"(?:(?:`[^`]+`|[^`\s.(]+)\.)?(?P<table>`[^`]+`|[^`\s(]+)",
    re.IGNORECASE,
)
INSERT_NAME_RE = re.compile(
    rb"INSERT\s+INTO\s+(?:(?:`[^`]+`|[^`\s.(]+)\.)?"
    rb"(?P<table>`[^`]+`|[^`\s(]+)",
    re.IGNORECASE,
)


class ExtractionError(RuntimeError):
    """Safe-to-display extraction failure without source row values."""


@dataclass
class TableStats:
    ddl_bytes: int = 0
    insert_statements: int = 0
    insert_bytes: int = 0


@dataclass
class ExtractionStats:
    source_size_bytes: int
    physical_bytes_read: int = 0
    logical_bytes_processed: int = 0
    stopped_after_table: str | None = None
    elapsed_seconds: float = 0.0
    output_size_bytes: int = 0
    output_sha256: str = ""
    tables: dict[str, TableStats] = field(
        default_factory=lambda: {name: TableStats() for name in TARGET_TABLES}
    )

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["approved_tables"] = list(TARGET_TABLES)
        data["non_target_values_retained"] = False
        return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("sql_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--read-chunk-mib", type=int, default=8)
    parser.add_argument("--max-insert-mib", type=int, default=256)
    return parser.parse_args()


def is_statement_start(data: bytes, pos: int) -> bool:
    if pos == 0:
        return True
    cursor = pos - 1
    while cursor >= 0 and data[cursor] in (0x20, 0x09, 0x0D):
        cursor -= 1
    return cursor < 0 or data[cursor] == 0x0A


def find_statement(data: bytes, token: bytes, start: int = 0) -> int:
    pos = start
    while pos < len(data):
        found = data.find(token, pos)
        if found < 0:
            return -1
        if is_statement_start(data, found):
            return found
        pos = found + len(token)
    return -1


def find_simple_statement_end(data: bytes, start: int, limit: int) -> int:
    end_limit = min(len(data), start + limit)
    lf = data.find(b";\n", start, end_limit)
    crlf = data.find(b";\r\n", start, end_limit)
    candidates = [position for position in (lf, crlf) if position >= 0]
    return min(candidates) + 1 if candidates else -1


def find_quoted_statement_end(data: bytes, start: int = 0) -> int:
    quote = 0
    escaped = False
    pos = start
    while pos < len(data):
        byte = data[pos]
        if quote:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == quote:
                if pos + 1 < len(data) and data[pos + 1] == quote:
                    pos += 1
                else:
                    quote = 0
        elif byte in (0x27, 0x22):
            quote = byte
        elif byte == 0x3B:
            return pos + 1
        pos += 1
    return -1


def extract_table_name(prefix: bytes, pattern: re.Pattern[bytes]) -> str | None:
    match = pattern.search(prefix)
    if match is None:
        return None
    raw = match.group("table").decode("utf-8", errors="strict").strip()
    if len(raw) >= 2 and raw[0] == "`" and raw[-1] == "`":
        return raw[1:-1].replace("``", "`")
    return raw


def _discard_to_overlap(buffer: bytes) -> tuple[bytes, int]:
    discarded = max(0, len(buffer) - TOKEN_OVERLAP_BYTES)
    return buffer[discarded:], discarded


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def extract_lookup_tables(
    sql_path: Path,
    output_dir: Path,
    *,
    read_chunk_bytes: int = DEFAULT_READ_CHUNK_BYTES,
    max_insert_bytes: int = DEFAULT_MAX_INSERT_BYTES,
) -> ExtractionStats:
    sql_path = sql_path.resolve()
    output_dir = output_dir.resolve()
    if not sql_path.is_file():
        raise ExtractionError("SQL source file does not exist")
    if read_chunk_bytes <= TOKEN_OVERLAP_BYTES:
        raise ExtractionError("read chunk is smaller than the parser overlap")
    if max_insert_bytes <= 0:
        raise ExtractionError("max INSERT size must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    sql_output = output_dir / "ehr-lookups.sql"
    manifest_output = output_dir / "manifest.json"
    partial_output = output_dir / "ehr-lookups.sql.partial"
    if sql_output.exists() or manifest_output.exists() or partial_output.exists():
        raise ExtractionError("output files already exist; choose an empty output directory")

    stats = ExtractionStats(source_size_bytes=sql_path.stat().st_size)
    started = time.monotonic()
    state = "seek_create"
    current_table: str | None = None
    buffer = b""
    absolute_offset = 0
    eof = False
    done = False
    next_progress_at = PROGRESS_BYTES

    try:
        with sql_path.open("rb", buffering=0) as source, partial_output.open("wb") as target:
            target.write(
                b"-- Locally extracted approved EHR lookup tables; contains no employee tables.\n"
                b"SET NAMES utf8mb4;\n"
                b"SET FOREIGN_KEY_CHECKS=0;\n\n"
            )

            while not done:
                if not eof:
                    chunk = source.read(read_chunk_bytes)
                    if chunk:
                        buffer += chunk
                    else:
                        eof = True

                made_progress = True
                while made_progress and not done:
                    made_progress = False

                    if state == "seek_create":
                        create_pos = find_statement(buffer, CREATE_TOKEN)
                        if create_pos < 0:
                            if eof:
                                done = True
                            else:
                                buffer, discarded = _discard_to_overlap(buffer)
                                absolute_offset += discarded
                            continue
                        absolute_offset += create_pos
                        buffer = buffer[create_pos:]
                        state = "capture_ddl"
                        made_progress = True

                    elif state == "capture_ddl":
                        ddl_end = find_simple_statement_end(buffer, 0, MAX_DDL_BYTES)
                        if ddl_end < 0:
                            if len(buffer) >= MAX_DDL_BYTES or eof:
                                raise ExtractionError("DDL terminator not found within safe limit")
                            continue
                        table = extract_table_name(buffer[: min(ddl_end, 4096)], CREATE_NAME_RE)
                        if table is None:
                            raise ExtractionError("CREATE TABLE name could not be parsed")
                        current_table = table
                        if table in TARGET_TABLES:
                            target.write(buffer[:ddl_end])
                            target.write(b"\n\n")
                            stats.tables[table].ddl_bytes += ddl_end
                        absolute_offset += ddl_end
                        buffer = buffer[ddl_end:]
                        state = "seek_target_statement" if table in TARGET_TABLES else "seek_next_create"
                        made_progress = True

                    elif state == "seek_next_create":
                        create_pos = find_statement(buffer, CREATE_TOKEN)
                        if create_pos < 0:
                            if eof:
                                done = True
                            else:
                                buffer, discarded = _discard_to_overlap(buffer)
                                absolute_offset += discarded
                            continue
                        absolute_offset += create_pos
                        buffer = buffer[create_pos:]
                        state = "capture_ddl"
                        made_progress = True

                    elif state == "seek_target_statement":
                        insert_pos = find_statement(buffer, INSERT_TOKEN)
                        create_pos = find_statement(buffer, CREATE_TOKEN)
                        if create_pos >= 0 and (insert_pos < 0 or create_pos < insert_pos):
                            if current_table == LAST_TARGET_TABLE:
                                absolute_offset += create_pos
                                stats.stopped_after_table = LAST_TARGET_TABLE
                                done = True
                            else:
                                absolute_offset += create_pos
                                buffer = buffer[create_pos:]
                                state = "capture_ddl"
                                made_progress = True
                            continue
                        if insert_pos >= 0:
                            absolute_offset += insert_pos
                            buffer = buffer[insert_pos:]
                            state = "capture_insert"
                            made_progress = True
                            continue
                        if eof:
                            if current_table == LAST_TARGET_TABLE:
                                stats.stopped_after_table = LAST_TARGET_TABLE
                            done = True
                        else:
                            buffer, discarded = _discard_to_overlap(buffer)
                            absolute_offset += discarded

                    elif state == "capture_insert":
                        insert_end = find_quoted_statement_end(buffer)
                        if insert_end < 0:
                            if len(buffer) > max_insert_bytes:
                                raise ExtractionError("target INSERT exceeded the configured safe limit")
                            if eof:
                                raise ExtractionError("target INSERT terminator was not found")
                            continue
                        if insert_end > max_insert_bytes:
                            raise ExtractionError("target INSERT exceeded the configured safe limit")
                        insert_table = extract_table_name(buffer[: min(insert_end, 4096)], INSERT_NAME_RE)
                        if insert_table != current_table or insert_table not in TARGET_TABLES:
                            raise ExtractionError("target INSERT table did not match its CREATE section")
                        target.write(buffer[:insert_end])
                        target.write(b"\n")
                        table_stats = stats.tables[insert_table]
                        table_stats.insert_statements += 1
                        table_stats.insert_bytes += insert_end
                        absolute_offset += insert_end
                        buffer = buffer[insert_end:]
                        state = "seek_target_statement"
                        made_progress = True

                    else:
                        raise ExtractionError("unknown parser state")

                if source.tell() >= next_progress_at and not done:
                    print(
                        json.dumps(
                            {
                                "read_gib": round(source.tell() / (1024**3), 2),
                                "processed_gib": round(absolute_offset / (1024**3), 2),
                                "elapsed_seconds": round(time.monotonic() - started, 1),
                            }
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
                    while next_progress_at <= source.tell():
                        next_progress_at += PROGRESS_BYTES

            target.write(b"\nSET FOREIGN_KEY_CHECKS=1;\n")
            target.flush()
            stats.physical_bytes_read = source.tell()

        missing_ddl = [name for name, value in stats.tables.items() if value.ddl_bytes == 0]
        missing_rows = [name for name, value in stats.tables.items() if value.insert_statements == 0]
        if missing_ddl or missing_rows:
            raise ExtractionError(
                "approved table extraction was incomplete: "
                f"missing DDL count={len(missing_ddl)}, missing INSERT count={len(missing_rows)}"
            )

        partial_output.replace(sql_output)
        stats.logical_bytes_processed = absolute_offset
        stats.elapsed_seconds = round(time.monotonic() - started, 3)
        stats.output_size_bytes = sql_output.stat().st_size
        stats.output_sha256 = _sha256(sql_output)
        with manifest_output.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(stats.to_json_dict(), target, ensure_ascii=False, indent=2)
            target.write("\n")
        return stats
    except Exception:
        if partial_output.exists():
            partial_output.unlink()
        raise


def main() -> int:
    args = parse_args()
    try:
        stats = extract_lookup_tables(
            args.sql_path,
            args.output_dir,
            read_chunk_bytes=args.read_chunk_mib * 1024 * 1024,
            max_insert_bytes=args.max_insert_mib * 1024 * 1024,
        )
    except (ExtractionError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats.to_json_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
