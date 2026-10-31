"""Contratos de negócio, equivalência e falhas reais da carga, usando unittest."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from backend.app.pipeline.engine import process_upload
from etl import PipelineConfig, run_pipeline
from etl.extract import COLUMNS, SchemaError, extract
from etl.load import ReconciliationError, reconcile
from etl.pipeline import export_results
from etl.validate import RULES, prepare, validate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dados/atendimentos_ficticios.csv"


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.database = self.directory / "suporte.sqlite"
        self.sample = pd.read_csv(SOURCE, sep=";", dtype="string", keep_default_na=False)

    def write(self, frame: pd.DataFrame, name: str = "entrada.csv") -> Path:
        source = self.directory / name
        frame.to_csv(source, sep=";", index=False, encoding="utf-8-sig")
        return source

    def rows(self, *changes: dict[str, str]) -> Path:
        records = [{**self.sample.iloc[0].to_dict(), "Protocolo": f"T{index}", **row}
                   for index, row in enumerate(changes, start=1)]
        return self.write(pd.DataFrame(records, columns=list(COLUMNS)))

    def query(self, query: str, params: tuple = ()) -> list[tuple]:
        with closing(sqlite3.connect(self.database)) as connection:
            return connection.execute(query, params).fetchall()

    def test_sample_reconciles_in_database_and_preserves_reasons(self) -> None:
        result = run_pipeline(SOURCE, self.database)
        report = result.manifest["reconciliacao_sql"]
        self.assertEqual((report["total_extraido"], report["validos"], report["excluidos"]), (18, 10, 8))
        self.assertEqual(result.excluded["motivo_codigo"].value_counts().tolist(), [1] * 8)
        self.assertEqual(result.manifest["cobertura_avaliacao"], 90.0)
        self.assertEqual(report["avaliacoes"], 9)
        self.assertEqual(report["linhas_distintas"], 18)
        self.assertEqual(report["reconciliado"], 1)
        self.assertEqual(self.query("SELECT etapa, entrada, saida FROM etapas ORDER BY ordem"),
                         [("extract", 18, 18), ("validate", 18, 10), ("transform", 10, 3), ("load", 21, 21)])

    def test_all_ranking_metrics_match_original_engine(self) -> None:
        reference = process_upload(SOURCE.read_bytes(), SOURCE.name, "08/2026", "Diego Demo")
        result = run_pipeline(SOURCE, self.database)
        mapping = {
            "atendente": "atendente", "atendimentos": "atendimentos", "horasTotal": "horas_total",
            "tmaMedioMin": "tma_medio_min", "tmaMedianoMin": "tma_mediano_min", "tmaP90Min": "tma_p90_min",
            "avaliacaoMedia": "avaliacao_media", "avaliacoes": "avaliacoes", "coberturaAvaliacao": "cobertura_avaliacao",
            "automaticos": "automaticos", "pontosQuantidade": "pontos_quantidade", "pontosTempo": "pontos_tempo",
            "pontosTma": "pontos_tma", "pontosAvaliacao": "pontos_avaliacao", "notaFinal": "nota_final",
            "rank": "posicao", "elegivel": "elegivel", "premiado": "premiado",
        }
        expected = pd.DataFrame(reference["ranking"])[list(mapping)].rename(columns=mapping)
        assert_frame_equal(result.ranking, expected, check_dtype=False, atol=1e-10, rtol=1e-10)

    def test_every_duplicate_is_quarantined_after_trimming_and_casefold(self) -> None:
        source = self.rows({"Protocolo": " AbC "}, {"Protocolo": "abc"}, {"Protocolo": "XYZ"})
        result = run_pipeline(source, self.database)
        self.assertEqual(result.valid["protocolo"].tolist(), ["XYZ"])
        self.assertEqual(result.excluded["motivo_codigo"].tolist(), ["PROTOCOLO_DUPLICADO"] * 2)
        self.assertEqual(result.manifest["reconciliacao_sql"]["total_extraido"], 3)
        self.assertEqual(self.query("SELECT COUNT(*) FROM validos"), [(1,)])

    def test_same_protocol_in_different_months_is_not_a_duplicate(self) -> None:
        source = self.rows({"Protocolo": "001"}, {"Protocolo": "001", "Iniciado": "10/07/2026 09:00", "Fim": "10/07/2026 10:00"})
        result = run_pipeline(source, self.database)
        self.assertEqual(result.valid["protocolo"].tolist(), ["001"])
        self.assertEqual(result.excluded["motivo_codigo"].tolist(), ["FORA_COMPETENCIA"])
        self.assertFalse(result.excluded["protocolo_duplicado"].any())

    def test_missing_protocol_is_audited_without_inventing_an_identifier(self) -> None:
        result = run_pipeline(self.rows({"Protocolo": "  "}, {}), self.database)
        self.assertEqual(result.excluded["motivo_codigo"].tolist(), ["SEM_PROTOCOLO"])
        self.assertEqual(result.excluded["protocolo_raw"].tolist(), ["  "])

    def test_invalid_grade_does_not_remove_valid_attendance(self) -> None:
        source = self.rows(*[{"Rating": grade} for grade in ("8", "texto", "inf", "", "0", "4,5")])
        result = run_pipeline(source, self.database)
        self.assertEqual(len(result.valid), 6)
        self.assertEqual(result.valid["avaliacao"].count(), 2)
        self.assertEqual(result.ranking.iloc[0]["avaliacao_media"], 2.25)
        self.assertAlmostEqual(result.manifest["cobertura_avaliacao"], 100 / 3)

    def test_month_uses_start_and_support_transfer_is_accepted(self) -> None:
        source = self.rows({"Iniciado": "31/08/2026 19:30", "Fim": "01/09/2026 00:00", "Setores": "Comercial", "Setores Transfers": "Suporte"})
        result = run_pipeline(source, self.database)
        self.assertEqual(len(result.valid), 1)
        self.assertEqual(result.valid.iloc[0]["competencia_registro"], "2026-08")
        self.assertEqual(result.valid.iloc[0]["duracao_horas"], 4.5)

    def test_expedient_boundaries_saturday_and_sunday(self) -> None:
        source = self.rows(
            {"Iniciado": "10/08/2026 08:00", "Fim": "10/08/2026 09:00"},
            {"Iniciado": "10/08/2026 19:59", "Fim": "10/08/2026 20:00"},
            {"Iniciado": "10/08/2026 20:00", "Fim": "10/08/2026 20:01"},
            {"Iniciado": "08/08/2026 09:00", "Fim": "08/08/2026 10:00"},
            {"Iniciado": "09/08/2026 09:00", "Fim": "09/08/2026 10:00"},
        )
        result = run_pipeline(source, self.database)
        self.assertEqual(result.valid["protocolo"].tolist(), ["T1", "T2", "T4"])
        self.assertEqual(result.excluded["motivo_codigo"].tolist(), ["PERIODO", "PERIODO"])

    def test_rules_are_independent_and_keep_first_reason(self) -> None:
        raw = extract(SOURCE).frame
        prepared = prepare(raw, PipelineConfig())
        original = prepared.copy(deep=True)
        for _, rule in RULES:
            mask = rule(prepared, PipelineConfig())
            self.assertTrue(mask.index.equals(prepared.index))
        assert_frame_equal(prepared, original)
        checked = validate(raw, PipelineConfig())
        self.assertEqual(checked.excluded.set_index("protocolo").loc["E001", "motivo_codigo"], "FORA_SUPORTE")
        self.assertEqual(checked.rule_counts["SEM_ATENDENTE"], {"detectados": 2, "motivo_principal": 1})

    def test_historical_weights_scale_and_duration_limit(self) -> None:
        source = self.rows(
            {"Iniciado": "11/05/2026 09:00", "Fim": "11/05/2026 10:00", "Rating": "10"},
            {"Iniciado": "11/05/2026 09:00", "Fim": "11/05/2026 17:01", "Rating": "10"},
        )
        result = run_pipeline(source, self.database, PipelineConfig(competencia="2026-05"))
        self.assertEqual(result.ranking.iloc[0]["nota_final"], 100.0)
        self.assertEqual(result.ranking.iloc[0]["pontos_tma"], 25.0)
        self.assertEqual(result.valid.iloc[0]["avaliacao"], 10)
        self.assertEqual(result.excluded["motivo_codigo"].tolist(), ["ACIMA_H"])

    def test_top_three_and_deterministic_tie_break(self) -> None:
        result = run_pipeline(self.rows(*[{"User ID": name} for name in ("Diana", "Carla", "Bruna", "Ana")]), self.database)
        self.assertEqual(result.ranking["atendente"].tolist(), ["Ana", "Bruna", "Carla", "Diana"])
        self.assertTrue(result.ranking["elegivel"].all())
        self.assertEqual(result.ranking["premiado"].tolist(), [True, True, True, False])

    def test_zero_duration_and_missing_ratings_do_not_generate_infinity(self) -> None:
        source = self.rows({"Fim": "10/08/2026 09:00", "Rating": "", "User ID": "Ana"},
                           {"Fim": "10/08/2026 09:00", "Rating": "", "User ID": "Bruna"})
        result = run_pipeline(source, self.database)
        self.assertTrue(result.ranking["nota_final"].eq(20).all())
        self.assertTrue(result.ranking["avaliacao_media"].isna().all())
        self.assertEqual(result.manifest["cobertura_avaliacao"], 0)
        export_results(result, self.directory / "exports")
        json.loads((self.directory / "exports/manifesto.json").read_text(encoding="utf-8"))

    def test_all_excluded_still_persists_an_auditable_empty_ranking(self) -> None:
        result = run_pipeline(self.rows({"Setores": "Financeiro"}), self.database)
        self.assertTrue(result.ranking.empty)
        self.assertEqual(result.manifest["reconciliacao_sql"]["reconciliado"], 1)
        self.assertEqual(self.query("SELECT COUNT(*) FROM ranking"), [(0,)])

    def test_schema_rejects_missing_extra_and_duplicate_headers(self) -> None:
        for frame in (self.sample.drop(columns="Fim"), self.sample.assign(Extra="x"),
                      self.sample.rename(columns={"Fim": "Iniciado"})):
            with self.subTest(columns=list(frame.columns)), self.assertRaises(SchemaError):
                run_pipeline(self.write(frame), self.database)
        self.assertFalse(self.database.exists())

    def test_empty_header_only_and_malformed_rows_fail_before_load(self) -> None:
        source = self.directory / "malformado.csv"
        for text in ("", ";".join(COLUMNS) + "\n", ";".join(COLUMNS) + "\ncurta;linha\n",
                     ";".join(COLUMNS) + '\n"aspas sem fechamento'):
            with self.subTest(text=text):
                source.write_text(text, encoding="utf-8")
                with self.assertRaises(SchemaError):
                    run_pipeline(source, self.database)
        self.assertFalse(self.database.exists())

    def test_protocol_zeroes_raw_values_and_sql_parameters_are_preserved(self) -> None:
        name = "Ana'; DROP TABLE validos; --"
        result = run_pipeline(self.rows({"Protocolo": "0007", "User ID": name}), self.database)
        self.assertEqual(result.valid["protocolo"].tolist(), ["0007"])
        self.assertEqual(self.query("SELECT protocolo, atendente FROM validos"), [("0007", name)])

    def test_reprocessing_is_idempotent_and_preserves_other_months(self) -> None:
        first = run_pipeline(SOURCE, self.database)
        second = run_pipeline(SOURCE, self.database)
        self.assertEqual(first.manifest, second.manifest)
        other_month = self.rows({"Iniciado": "16/09/2026 09:00", "Fim": "16/09/2026 10:00"})
        run_pipeline(other_month, self.database, PipelineConfig(competencia="2026-09"))
        run_pipeline(SOURCE, self.database)
        self.assertEqual(self.query("SELECT competencia, COUNT(*) FROM validos GROUP BY competencia ORDER BY competencia"),
                         [("2026-08", 10), ("2026-09", 1)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM execucoes"), [(2,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM etapas"), [(8,)])

    def test_replacement_removes_old_rows_instead_of_appending(self) -> None:
        run_pipeline(SOURCE, self.database)
        result = run_pipeline(self.rows({}), self.database)
        self.assertEqual(self.query("SELECT COUNT(*) FROM validos"), [(1,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM excluidos"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM ranking"), [(1,)])
        self.assertEqual(result.manifest["reconciliacao_sql"]["reconciliado"], 1)

    def test_failed_reconciliation_rolls_back_data_and_metadata(self) -> None:
        previous = run_pipeline(SOURCE, self.database)
        with patch("etl.load.reconcile_connection", return_value={"reconciliado": 0}):
            with self.assertRaises(ReconciliationError):
                run_pipeline(self.rows({}), self.database)
        self.assertEqual(reconcile(self.database, "2026-08"), previous.manifest["reconciliacao_sql"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM execucoes"), [(1,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM etapas"), [(4,)])

    def test_invalid_file_does_not_replace_previously_loaded_data(self) -> None:
        previous = run_pipeline(SOURCE, self.database)
        with self.assertRaises(SchemaError):
            run_pipeline(self.write(self.sample.drop(columns="Fim")), self.database)
        self.assertEqual(reconcile(self.database, "2026-08"), previous.manifest["reconciliacao_sql"])

    def test_real_sqlite_constraint_failure_rolls_back_the_replacement(self) -> None:
        previous = run_pipeline(SOURCE, self.database)
        invalid_ranking = previous.ranking.copy()
        invalid_ranking.loc[1, "atendente"] = invalid_ranking.loc[0, "atendente"]
        with patch("etl.pipeline.transform", return_value=invalid_ranking):
            with self.assertRaises(sqlite3.IntegrityError):
                run_pipeline(self.rows({}), self.database)
        self.assertEqual(reconcile(self.database, "2026-08"), previous.manifest["reconciliacao_sql"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM execucoes"), [(1,)])

    def test_sql_reconciliation_detects_a_tampered_attendant_count(self) -> None:
        run_pipeline(SOURCE, self.database)
        with closing(sqlite3.connect(self.database, isolation_level=None)) as connection:
            connection.execute("UPDATE ranking SET atendimentos=99 WHERE atendente='Ana Demo'")
        report = reconcile(self.database, "2026-08")
        self.assertEqual(report["reconciliado"], 0)
        self.assertGreater(report["divergencias_ranking"], 0)

    def test_read_only_reconciliation_does_not_create_missing_database(self) -> None:
        with self.assertRaises(sqlite3.OperationalError):
            reconcile(self.database, "2026-08")
        self.assertFalse(self.database.exists())

    def test_sql_reconciliation_detects_a_changed_source_record_number(self) -> None:
        run_pipeline(SOURCE, self.database)
        with closing(sqlite3.connect(self.database, isolation_level=None)) as connection:
            connection.execute("UPDATE validos SET linha_origem=999 WHERE protocolo='V001'")
        report = reconcile(self.database, "2026-08")
        self.assertEqual(report["reconciliado"], 0)
        self.assertEqual(report["ultima_linha"], 999)

    def test_export_is_reproducible_across_repeated_runs(self) -> None:
        output = self.directory / "exports"
        export_results(run_pipeline(SOURCE, self.database), output)
        original = {path.name: path.read_bytes() for path in output.iterdir()}
        export_results(run_pipeline(SOURCE, self.database), output)
        self.assertEqual(original, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_cli_load_and_read_only_reconciliation(self) -> None:
        command = [sys.executable, "-m", "etl", "--database", str(self.database),
                   "--output-dir", str(self.directory / "exports")]
        loaded = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertEqual(json.loads(loaded.stdout)["reconciliado"], 1)
        checked = subprocess.run(command + ["--reconcile-only"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(loaded.stdout), json.loads(checked.stdout))

    def test_quality_fixture_exercises_new_rules_without_changing_reference(self) -> None:
        result = run_pipeline(ROOT / "dados/cenarios_qualidade.csv", self.database)
        report = result.manifest["reconciliacao_sql"]
        self.assertEqual((report["total_extraido"], report["validos"], report["excluidos"]), (22, 10, 12))
        self.assertEqual(result.manifest["avaliacoes_validas"], 8)
        self.assertEqual(result.manifest["cobertura_avaliacao"], 80)
        self.assertEqual(result.excluded["motivo_codigo"].value_counts()["PROTOCOLO_DUPLICADO"], 2)


if __name__ == "__main__":
    unittest.main()
