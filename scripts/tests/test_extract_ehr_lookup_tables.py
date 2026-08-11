from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "extract_ehr_lookup_tables.py"
SPEC = importlib.util.spec_from_file_location("extract_ehr_lookup_tables", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def table_section(name: str, columns: str, inserts: list[str]) -> str:
    statements = "\n".join(inserts)
    return (
        f"CREATE TABLE `{name}` (\n{columns}\n) ENGINE=InnoDB;\n"
        f"{statements}\n"
    )


class LookupExtractionTests(unittest.TestCase):
    def test_only_approved_tables_are_retained_and_scan_stops_early(self) -> None:
        private_value = "PRIVATE_EMPLOYEE_SENTINEL_123456"
        dump = "".join(
            [
                table_section(
                    "ehr_employee_info",
                    "  `id` bigint NOT NULL,\n  `id_card` varchar(32)",
                    [f"INSERT INTO `ehr_employee_info` VALUES (1,'{private_value}');"],
                ),
                table_section(
                    "country",
                    "  `code` varchar(8) NOT NULL,\n  `name` varchar(64),\n  `leaf` int",
                    ["INSERT INTO `country` VALUES ('ABW','A;B',1);"],
                ),
                table_section(
                    "ehr_dict",
                    "  `id` bigint NOT NULL,\n  `name` varchar(64),\n  `code` varchar(64)",
                    [
                        "INSERT INTO `ehr_dict` VALUES (1,'Married','MARRIED');",
                        "INSERT INTO `ehr_dict` VALUES (2,'Escaped \\' value','ESCAPED');",
                    ],
                ),
                table_section(
                    "ehr_dict_element",
                    "  `id` bigint NOT NULL,\n  `dict_id` bigint,\n  `name` varchar(64)",
                    ["INSERT INTO `ehr_dict_element` VALUES (1,1,'married');"],
                ),
                table_section(
                    "later_private_table",
                    "  `secret` varchar(64)",
                    [f"INSERT INTO `later_private_table` VALUES ('{private_value}');"],
                ),
                "-- trailing bytes that should not be scanned\n" + ("x" * 8192),
            ]
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.sql"
            output = root / "output"
            source.write_bytes(dump)

            stats = MODULE.extract_lookup_tables(
                source,
                output,
                read_chunk_bytes=1024,
                max_insert_bytes=1024 * 1024,
            )

            extracted = (output / "ehr-lookups.sql").read_text(encoding="utf-8")
            self.assertNotIn(private_value, extracted)
            self.assertNotIn("ehr_employee_info", extracted)
            self.assertNotIn("later_private_table", extracted)
            for table in MODULE.TARGET_TABLES:
                self.assertIn(f"CREATE TABLE `{table}`", extracted)
                self.assertGreater(stats.tables[table].insert_statements, 0)
            self.assertEqual(stats.tables["ehr_dict"].insert_statements, 2)
            self.assertEqual(stats.stopped_after_table, "ehr_dict_element")
            self.assertLess(stats.physical_bytes_read, len(dump))
            self.assertFalse(stats.to_json_dict()["non_target_values_retained"])

    def test_incomplete_target_set_is_rejected_without_final_output(self) -> None:
        dump = table_section(
            "country",
            "  `code` varchar(8) NOT NULL",
            ["INSERT INTO `country` VALUES ('ABW');"],
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.sql"
            output = root / "output"
            source.write_bytes(dump)

            with self.assertRaises(MODULE.ExtractionError):
                MODULE.extract_lookup_tables(
                    source,
                    output,
                    read_chunk_bytes=1024,
                    max_insert_bytes=1024 * 1024,
                )

            self.assertFalse((output / "ehr-lookups.sql").exists())
            self.assertFalse((output / "manifest.json").exists())
            self.assertFalse((output / "ehr-lookups.sql.partial").exists())


if __name__ == "__main__":
    unittest.main()
