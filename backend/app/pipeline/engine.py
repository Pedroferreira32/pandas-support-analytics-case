from __future__ import annotations

import csv
from datetime import datetime
from io import BytesIO, StringIO
import math
import re
import unicodedata
from typing import Any

import pandas as pd

from .rules import RuleConfig, official_config


INVALIDOS = {
    "",
    "-",
    "NAN",
    "NAT",
    "NONE",
    "NULL",
    "PENDENTE",
    "SEM ATENDENTE",
    "NAO INFORMADO",
}

MOTIVOS = {
    "FORA_SUPORTE": "Departamento diferente de Suporte",
    "SEM_ATENDENTE": "Atendente não informado",
    "ATENDENTE_EXCLUIDO": "Atendente fora da campanha",
    "DATA_INVALIDA": "Data de início inválida ou pendente",
    "SEM_FINALIZACAO": "Data final não informada",
    "DURACAO_NEGATIVA": "Data final anterior ao início",
    "ACIMA_H": "Duração acima do limite configurado",
    "PERIODO": "Fora do expediente ou em domingo",
}

ALIASES = {
    "protocolo": ["PROTOCOLO", "ID DO TICKET", "IDTICKET", "TICKET", "TICKET ID"],
    "cliente": ["CONTACT ID", "CONTACTID", "CLIENTE", "NOME DO CLIENTE", "RAZAO SOCIAL"],
    "contato": ["CONTACT NUMBER", "CONTACTNUMBER", "TELEFONE", "CELULAR", "WHATSAPP"],
    "revenda": ["REVENDA", "PARCEIRO", "CANAL", "NOME DA REVENDA", "RESELLER"],
    "atendente": ["ATENDENTE", "USER ID", "USERID", "OPERADOR", "USUARIO", "AGENTE"],
    "filas": ["FILAS", "FILA", "DEPARTAMENTO", "SETOR", "SETORES"],
    "filasTransfers": [
        "FILAS TRANSFERS",
        "FILASTRANSFERS",
        "FILAS TRANSFER",
        "FILA TRANSFERIDA",
        "SETORES TRANSFERS",
        "SETORESTRANSFERS",
    ],
    "inicio": ["INICIADO", "INICIO", "DATA INICIO", "CRIADO", "DATA", "CRIADO EM"],
    "fim": ["FIM", "DATA ULTIMA MENSAGEM", "ULTIMA MENSAGEM", "FINALIZADO", "DATA FINALIZACAO"],
    "rating": ["RATING", "AVALIACAO", "NOTA", "SATISFACAO", "CSAT"],
    "status": ["STATUS", "SITUACAO", "MOTIVO DE ENCERRAMENTO"],
}


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)


def clean_text(value: Any) -> str:
    return "" if _is_missing(value) else str(value).strip()


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFD", clean_text(value))
    return "".join(char for char in text if unicodedata.category(char) != "Mn").lstrip("\ufeff").strip().upper()


def normalize_header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize(value))


def parse_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    match = re.search(r"-?\d+(?:[.,]\d+)?", clean_text(value).replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_date(value: Any) -> pd.Timestamp | None:
    if _is_missing(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        parsed = pd.Timestamp(value)
        return None if pd.isna(parsed) else parsed.tz_localize(None) if parsed.tzinfo else parsed
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if 0 < number <= 100000:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(number, unit="D")
        return None

    text = clean_text(value)
    if normalize(text) in INVALIDOS:
        return None

    patterns = (
        (r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?", "br"),
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?", "iso"),
    )
    for pattern, order in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        first, second, third, hour, minute, second_value = match.groups()
        try:
            if order == "br":
                day, month, year = int(first), int(second), int(third)
            else:
                year, month, day = int(first), int(second), int(third)
            return pd.Timestamp(datetime(year, month, day, int(hour or 0), int(minute or 0), int(second_value or 0)))
        except ValueError:
            return None
    return None


def competence_to_iso(value: str) -> str:
    text = value.strip()
    match = re.fullmatch(r"(\d{2})/(\d{4})", text)
    if match and 1 <= int(match.group(1)) <= 12:
        return f"{match.group(2)}-{match.group(1)}"
    match = re.fullmatch(r"(\d{4})-(\d{2})", text)
    if match and 1 <= int(match.group(2)) <= 12:
        return text
    raise ValueError("Informe a competência no formato MM/AAAA, por exemplo 08/2026.")


def competence_to_br(value: str) -> str:
    return f"{value[5:7]}/{value[:4]}" if re.fullmatch(r"\d{4}-\d{2}", value) else value


def _detect_delimiter(text: str) -> str:
    first = next((line for line in text.splitlines() if line.strip()), "")
    return max([",", ";", "\t"], key=lambda delimiter: len(first.split(delimiter)))


def _read_delimited(content: bytes) -> pd.DataFrame:
    text = content.decode("utf-8-sig", errors="replace")
    if "\ufffd" in text:
        text = content.decode("windows-1252", errors="replace")
    delimiter = _detect_delimiter(text)
    rows = list(csv.reader(StringIO(text), delimiter=delimiter))
    if not rows:
        return pd.DataFrame()
    expected = max((len(row) for row in rows[:10]), default=1)
    repaired: list[list[str]] = []
    for row in rows:
        if len(row) == 1 and expected > 1 and delimiter in row[0]:
            candidate = next(csv.reader([row[0]], delimiter=delimiter))
            repaired.append(candidate if len(candidate) > 1 else row)
        else:
            repaired.append(row)
    width = max((len(row) for row in repaired), default=0)
    return pd.DataFrame([row + [""] * (width - len(row)) for row in repaired], dtype=object)


def read_table(content: bytes, filename: str) -> pd.DataFrame:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in {"csv", "txt", "tsv"}:
        frame = _read_delimited(content)
    elif extension in {"xlsx", "xls", "xlsm"}:
        frame = pd.read_excel(BytesIO(content), sheet_name=0, header=None, dtype=object)
    else:
        raise ValueError("Formato não suportado. Envie CSV, TXT, XLSX, XLS ou XLSM.")
    if frame.empty:
        raise ValueError("O arquivo está vazio ou não possui linhas legíveis.")
    return frame.fillna("")


def _map_headers(headers: list[Any]) -> dict[str, int]:
    normalized = [normalize_header(value) for value in headers]
    mapping: dict[str, int] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            try:
                mapping[field] = normalized.index(normalize_header(alias))
                break
            except ValueError:
                continue
    return mapping


def _locate_header(frame: pd.DataFrame) -> tuple[int, dict[str, int]]:
    best_index, best_mapping, best_score = -1, {}, -1
    for index, row in frame.head(50).iterrows():
        mapping = _map_headers(row.tolist())
        if len(mapping) > best_score:
            best_index, best_mapping, best_score = int(index), mapping, len(mapping)
    missing: list[str] = []
    if "atendente" not in best_mapping:
        missing.append("Atendente/User ID")
    if "inicio" not in best_mapping:
        missing.append("Iniciado/Criado")
    if "fim" not in best_mapping:
        missing.append("Fim")
    if "filas" not in best_mapping and "filasTransfers" not in best_mapping:
        missing.append("Filas/Setores ou Transfers")
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing)}")
    return best_index, best_mapping


def _source_frame(frame: pd.DataFrame, header_index: int) -> pd.DataFrame:
    source = frame.iloc[header_index + 1 :].copy()
    populated = source.apply(lambda row: any(clean_text(value) for value in row), axis=1)
    return source.loc[populated].reset_index(drop=True)


def _prepare(frame: pd.DataFrame, header_index: int, mapping: dict[str, int], config: RuleConfig) -> pd.DataFrame:
    source = _source_frame(frame, header_index)

    def column(field: str) -> pd.Series:
        if field not in mapping:
            return pd.Series([""] * len(source), index=source.index, dtype=object)
        return source.iloc[:, mapping[field]]

    prepared = pd.DataFrame(index=source.index)
    prepared["linhaOrigem"] = source.index + header_index + 2
    prepared["protocolo"] = column("protocolo").map(clean_text)
    missing_protocol = prepared["protocolo"].eq("")
    prepared.loc[missing_protocol, "protocolo"] = prepared.loc[missing_protocol, "linhaOrigem"].map(lambda value: f"LINHA-{value}")
    prepared["cliente"] = column("cliente").map(clean_text)
    prepared["contato"] = column("contato").map(clean_text)
    prepared["revenda"] = column("revenda").map(clean_text)
    prepared["atendente"] = column("atendente").map(clean_text)
    prepared["fila"] = column("filas").map(clean_text)
    prepared["transfer"] = column("filasTransfers").map(clean_text)
    prepared["departamento"] = prepared.apply(
        lambda row: " | ".join(dict.fromkeys(value for value in [row["fila"], row["transfer"]] if value)), axis=1
    )
    prepared["status"] = column("status").map(clean_text)
    prepared["inicioDt"] = column("inicio").map(parse_date)
    prepared["fimDt"] = column("fim").map(parse_date)
    raw_rating = column("rating").map(parse_number)
    prepared["avaliacao"] = raw_rating.where(raw_rating.between(0, config.escala_avaliacao_max), None)
    prepared["duracaoHoras"] = (
        pd.to_datetime(prepared["fimDt"]) - pd.to_datetime(prepared["inicioDt"])
    ).dt.total_seconds() / 3600
    return prepared


def _iso_local(value: Any) -> str:
    return "" if value is None or pd.isna(value) else pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%S")


def detect_competence(content: bytes, filename: str) -> str | None:
    frame = read_table(content, filename)
    header_index, mapping = _locate_header(frame)
    source = _source_frame(frame, header_index)
    dates = source.iloc[:, mapping["inicio"]].map(parse_date)
    keys = dates.dropna().map(lambda value: pd.Timestamp(value).strftime("%Y-%m"))
    if keys.empty:
        return None
    return str(keys.value_counts().index[0])


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    return float(pd.Series(values).quantile(ratio, interpolation="linear"))


def _slug(value: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", normalize(value).lower()))


def _feedback(row: dict[str, Any], config: RuleConfig) -> str:
    criteria = [
        ("Quantidade", row["pontosQuantidade"], config.peso_quantidade),
        ("Avaliação", row["pontosAvaliacao"], config.peso_avaliacao),
    ]
    if not config.pontuacao_tempo_tma_fixa:
        criteria.extend(
            [
                ("Tempo Total", row["pontosTempo"], config.peso_tempo),
                ("TMA", row["pontosTma"], config.peso_tma),
            ]
        )
    criteria.sort(key=lambda item: item[1] / item[2] if item[2] else 0, reverse=True)
    return (
        f"Ponto forte: {criteria[0][0]}. Foco de acompanhamento: {criteria[-1][0]}. "
        f"Resultado calculado com {row['atendimentos']} atendimento(s) válido(s) e {row['avaliacoes']} avaliação(ões)."
    )


def _calculate_ranking(valid: pd.DataFrame, config: RuleConfig) -> list[dict[str, Any]]:
    base: list[dict[str, Any]] = []
    for attendant, group in valid.groupby("atendente", sort=False):
        timed = group.loc[group["duracaoConsiderada"]]
        ratings = group["avaliacao"].dropna().astype(float).tolist()
        tmas = timed["tmaMinutos"].astype(float).tolist()
        base.append(
            {
                "id": _slug(str(attendant)),
                "atendente": str(attendant),
                "atendimentos": int(len(group)),
                "tmaMedioMin": float(pd.Series(tmas).mean()) if tmas else None,
                "tmaMedianoMin": _percentile(tmas, 0.5),
                "tmaP90Min": _percentile(tmas, 0.9),
                "horasTotal": float(timed["duracaoHoras"].sum()) if not timed.empty else 0.0,
                "avaliacaoMedia": float(pd.Series(ratings).mean()) if ratings else None,
                "avaliacoes": len(ratings),
                "coberturaAvaliacao": len(ratings) / len(group) * 100 if len(group) else 0.0,
                "automaticos": int(group["suspeitoAutomatico"].sum()),
            }
        )

    max_quantity = max((row["atendimentos"] for row in base), default=0)
    max_hours = max((row["horasTotal"] for row in base), default=0.0)
    positive_tmas = [row["tmaMedioMin"] for row in base if row["tmaMedioMin"] and row["tmaMedioMin"] > 0]
    min_tma = min(positive_tmas, default=0.0)
    ratings = [row["avaliacaoMedia"] for row in base if row["avaliacaoMedia"] is not None]
    max_rating = max(ratings, default=0.0)

    for row in base:
        row["pontosQuantidade"] = row["atendimentos"] / max_quantity * config.peso_quantidade if max_quantity else 0.0
        row["pontosTempo"] = row["horasTotal"] / max_hours * config.peso_tempo if max_hours else 0.0
        row["pontosTma"] = (
            min_tma / row["tmaMedioMin"] * config.peso_tma
            if min_tma and row["tmaMedioMin"]
            else 0.0
        )
        row["pontosAvaliacao"] = (
            row["avaliacaoMedia"] / max_rating * config.peso_avaliacao
            if row["avaliacaoMedia"] is not None and max_rating
            else 0.0
        )
        row["notaFinal"] = sum(
            row[key] for key in ["pontosQuantidade", "pontosTempo", "pontosTma", "pontosAvaliacao"]
        )

    base.sort(
        key=lambda row: (
            -row["notaFinal"],
            -row["atendimentos"],
            -(row["avaliacaoMedia"] if row["avaliacaoMedia"] is not None else -1),
            normalize(row["atendente"]),
        )
    )
    awarded = 0
    for index, row in enumerate(base, start=1):
        eligible = row["notaFinal"] >= config.nota_minima
        is_awarded = eligible and awarded < 3
        if is_awarded:
            awarded += 1
        row["rank"] = index
        row["elegivel"] = eligible
        row["premiado"] = is_awarded
        suffix = (
            "Meta atingida e posição premiada no Top 3."
            if is_awarded
            else "Meta atingida, mas fora das três posições premiadas."
            if eligible
            else f"Faltaram {config.nota_minima - row['notaFinal']:.2f} pontos para a meta.".replace(".", ",")
        )
        row["feedback"] = f"{_feedback(row, config)} {suffix}"
    return base


def _calculate_resellers(valid: pd.DataFrame) -> list[dict[str, Any]]:
    if valid.empty or "revenda" not in valid.columns:
        return []
    base = valid.copy()
    base["revenda"] = base["revenda"].map(clean_text).replace("", "Sem revenda identificada")
    result: list[dict[str, Any]] = []
    for reseller, group in base.groupby("revenda", sort=False):
        ratings = group["avaliacao"].dropna().astype(float).tolist()
        timed = group.loc[group["duracaoConsiderada"]]
        result.append(
            {
                "revenda": str(reseller),
                "atendimentos": int(len(group)),
                "clientes": int(group["cliente"].map(clean_text).replace("", pd.NA).nunique()),
                "atendentes": int(group["atendente"].map(clean_text).replace("", pd.NA).nunique()),
                "diasAtivos": int(group["inicio"].map(lambda value: str(value)[:10]).replace("", pd.NA).nunique()),
                "avaliacaoMedia": float(pd.Series(ratings).mean()) if ratings else None,
                "avaliacoes": len(ratings),
                "coberturaAvaliacao": len(ratings) / len(group) * 100 if len(group) else 0.0,
                "tmaMedioMin": float(timed["tmaMinutos"].mean()) if not timed.empty else None,
            }
        )
    result.sort(key=lambda item: (-item["atendimentos"], normalize(item["revenda"])))
    return result


def _calculate_operation(valid: pd.DataFrame) -> dict[str, Any]:
    timed = valid.loc[valid["duracaoConsiderada"], "tmaMinutos"].astype(float).tolist()
    ratings = valid["avaliacao"].dropna().astype(float).tolist()
    return {
        "atendimentos": int(len(valid)),
        "tmaMedianoMin": _percentile(timed, 0.5),
        "tmaP90Min": _percentile(timed, 0.9),
        "avaliacaoMedia": float(pd.Series(ratings).mean()) if ratings else None,
        "avaliacoes": len(ratings),
        "coberturaAvaliacao": len(ratings) / len(valid) * 100 if len(valid) else 0.0,
    }


def _record(row: pd.Series, automatic: bool, duration_considered: bool | None = None) -> dict[str, Any]:
    duration = float(row["duracaoHoras"]) if not pd.isna(row["duracaoHoras"]) else 0.0
    result: dict[str, Any] = {
        "linhaOrigem": int(row["linhaOrigem"]),
        "protocolo": str(row["protocolo"]),
        "cliente": str(row["cliente"]),
        "contato": str(row["contato"]),
        "revenda": str(row["revenda"]),
        "atendente": str(row["atendente"]),
        "departamento": str(row["departamento"]),
        "status": str(row["status"]),
        "inicio": _iso_local(row["inicioDt"]),
        "fim": _iso_local(row["fimDt"]),
        "avaliacao": None if pd.isna(row["avaliacao"]) else float(row["avaliacao"]),
        "duracaoHoras": duration,
        "tmaMinutos": duration * 60,
        "suspeitoAutomatico": bool(automatic),
    }
    if duration_considered is not None:
        result["duracaoConsiderada"] = bool(duration_considered)
    return result


def process_upload(content: bytes, filename: str, competence_input: str, excluded_names: str = "") -> dict[str, Any]:
    frame = read_table(content, filename)
    header_index, mapping = _locate_header(frame)
    headers = frame.iloc[header_index].tolist()
    competencia = competence_to_iso(competence_input)
    config = official_config(competencia)
    prepared = _prepare(frame, header_index, mapping, config)

    competence_keys = prepared["inicioDt"].dropna().map(lambda value: pd.Timestamp(value).strftime("%Y-%m"))
    if not competence_keys.empty:
        majority = str(competence_keys.value_counts().index[0])
        majority_count = int(competence_keys.value_counts().iloc[0])
        if majority != competencia and majority_count > len(prepared) / 2:
            raise ValueError(
                f"A competência informada não corresponde ao arquivo. A maioria dos atendimentos iniciados pertence a "
                f"{competence_to_br(majority)}, mas foi informado {competence_to_br(competencia)}. "
                "A competência considera a data de início, não a data de finalização."
            )

    end_minutes = prepared["fimDt"].map(lambda value: _iso_local(value)[:16] if value is not None and not pd.isna(value) else "")
    end_counts = end_minutes[end_minutes.ne("")].value_counts()
    hour_six = prepared["fimDt"].map(
        lambda value: bool(value is not None and not pd.isna(value) and pd.Timestamp(value).hour == 6 and pd.Timestamp(value).minute == 0)
    )
    prepared["suspeitoAutomatico"] = hour_six | end_minutes.map(lambda value: bool(value and end_counts.get(value, 0) >= 20))

    support = prepared["fila"].map(normalize).str.contains("SUPORTE", regex=False) | prepared["transfer"].map(normalize).str.contains("SUPORTE", regex=False)
    attendant_normalized = prepared["atendente"].map(normalize)
    excluded = [normalize(name) for name in excluded_names.split(";") if normalize(name)]
    excluded_mask = attendant_normalized.map(lambda value: any(name in value for name in excluded))
    reason = pd.Series("", index=prepared.index, dtype=object)

    def assign(code: str, condition: pd.Series) -> None:
        reason.loc[reason.eq("") & condition.fillna(False)] = code

    assign("FORA_SUPORTE", ~support)
    assign("SEM_ATENDENTE", attendant_normalized.isin(INVALIDOS))
    assign("ATENDENTE_EXCLUIDO", excluded_mask)
    assign("DATA_INVALIDA", prepared["inicioDt"].isna())
    assign("SEM_FINALIZACAO", prepared["fimDt"].isna())
    assign("DURACAO_NEGATIVA", prepared["duracaoHoras"].lt(0))
    if config.modo == "padrao":
        allowed_automatic = prepared["suspeitoAutomatico"] & config.incluir_finalizados_automaticamente
        assign("ACIMA_H", prepared["duracaoHoras"].gt(config.max_horas) & ~allowed_automatic)
        if not config.incluir_fora_expediente:
            start = pd.to_datetime(prepared["inicioDt"])
            minutes = start.dt.hour * 60 + start.dt.minute
            assign("PERIODO", start.dt.dayofweek.eq(6) | minutes.lt(480) | minutes.gt(1199))
    prepared["motivoCodigo"] = reason

    stats: dict[str, int] = {
        "TOTAL": int(len(prepared)),
        "AUTOMATICOS_IDENTIFICADOS": int(prepared["suspeitoAutomatico"].sum()),
        "AUTOMATICOS_VALIDOS": 0,
        "AUTOMATICOS_RECUPERADOS": 0,
    }
    for code, count in reason[reason.ne("")].value_counts().items():
        stats[str(code)] = int(count)

    valid_frame = prepared.loc[reason.eq("")].copy()
    excluded_frame = prepared.loc[reason.ne("")].copy()
    valid_frame["duracaoConsiderada"] = ~(
        valid_frame["suspeitoAutomatico"] & config.neutralizar_tempo_automaticos
    )
    stats["AUTOMATICOS_VALIDOS"] = int(valid_frame["suspeitoAutomatico"].sum())
    stats["AUTOMATICOS_RECUPERADOS"] = int(
        (valid_frame["suspeitoAutomatico"] & valid_frame["duracaoHoras"].gt(config.max_horas)).sum()
    )
    stats["VALIDOS"] = int(len(valid_frame))
    stats["EXCLUIDOS"] = int(len(excluded_frame))
    stats["REGULARES_VALIDOS"] = stats["VALIDOS"] - stats["AUTOMATICOS_VALIDOS"]
    stats["AUTOMATICOS_EXCLUIDOS"] = int(excluded_frame["suspeitoAutomatico"].sum())
    stats["AUTOMATICOS_NEUTRALIZADOS_TEMPO"] = (
        stats["AUTOMATICOS_VALIDOS"] if config.neutralizar_tempo_automaticos else 0
    )
    stats["AVALIACOES_VALIDAS"] = int(valid_frame["avaliacao"].notna().sum())

    if valid_frame.empty:
        raise ValueError("Nenhum atendimento válido restou após a aplicação das regras.")

    valid_records = [
        _record(row, bool(row["suspeitoAutomatico"]), bool(row["duracaoConsiderada"]))
        for _, row in valid_frame.iterrows()
    ]
    excluded_records = []
    for _, row in excluded_frame.iterrows():
        item = _record(row, bool(row["suspeitoAutomatico"]))
        code = str(row["motivoCodigo"])
        item.update({"motivoCodigo": code, "motivo": MOTIVOS[code]})
        excluded_records.append(item)

    mapping_names = {field: clean_text(headers[index]) for field, index in mapping.items()}
    warnings: list[str] = []
    if "protocolo" not in mapping:
        warnings.append("Protocolo ausente: foi usado o número da linha para auditoria.")
    if "cliente" not in mapping:
        warnings.append("Cliente ausente: o painel de clientes críticos exige Contact ID ou coluna equivalente.")
    warnings.append(
        f"Teto de {config.teto_pontuacao:.0f} pontos: Tempo Total e TMA são componentes separados e comparativos."
    )

    ranking_frame = pd.DataFrame(valid_records)
    return {
        "schemaVersion": 1,
        "competencia": competencia,
        "competenciaBr": competence_to_br(competencia),
        "origem": filename,
        "processadoEm": datetime.now().astimezone().isoformat(),
        "config": config.to_api(),
        "totalLinhas": int(len(prepared)),
        "validos": valid_records,
        "excluidos": excluded_records,
        "ranking": _calculate_ranking(ranking_frame, config),
        "revendas": _calculate_resellers(ranking_frame),
        "operacao": _calculate_operation(ranking_frame),
        "mapeamento": mapping_names,
        "estatisticas": stats,
        "avisos": warnings,
    }
