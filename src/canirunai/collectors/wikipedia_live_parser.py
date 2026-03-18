from __future__ import annotations

import re

from ..parsers.normalization import clean_name, lookup_key
from ..schemas.base import RawReference
from ..schemas.cpu import CpuSpec
from ..schemas.gpu import GpuSpec
from .html_tables import ParsedTable, parse_html_tables
from .wikipedia_client import WikipediaPageSnapshot


def parse_cpu_specs_from_snapshot(
    snapshot: WikipediaPageSnapshot,
    *,
    vendor: str,
    cache_key: str,
) -> list[CpuSpec]:
    specs: dict[str, CpuSpec] = {}
    for table in parse_html_tables(snapshot.html):
        if not _is_cpu_table(table):
            continue
        for row in table.rows:
            spec = _cpu_spec_from_row(
                row,
                vendor=vendor,
                source_url=snapshot.page_url,
                source_revision_id=snapshot.revision_id,
                cache_key=cache_key,
            )
            if spec is not None:
                specs[lookup_key(spec.canonical_name)] = spec
    return sorted(specs.values(), key=lambda item: item.canonical_name.casefold())


def parse_gpu_specs_from_snapshot(
    snapshot: WikipediaPageSnapshot,
    *,
    vendor: str,
    cache_key: str,
) -> list[GpuSpec]:
    specs: dict[str, GpuSpec] = {}
    for table in parse_html_tables(snapshot.html):
        if not _is_gpu_table(table):
            continue
        for row in table.rows:
            spec = _gpu_spec_from_row(
                row,
                vendor=vendor,
                source_url=snapshot.page_url,
                source_revision_id=snapshot.revision_id,
                cache_key=cache_key,
            )
            if spec is not None:
                specs[lookup_key(spec.canonical_name)] = spec
    return sorted(specs.values(), key=lambda item: item.canonical_name.casefold())


def _is_cpu_table(table: ParsedTable) -> bool:
    if "wikitable" not in table.class_name.casefold() and "mw-datatable" not in table.class_name.casefold():
        return False
    joined = " ".join(_normalize_header(header) for header in table.headers)
    return (
        ("model" in joined or "sku" in joined or "branding" in joined)
        and "core" in joined
        and ("clock" in joined or "tdp" in joined or "power" in joined or "cache" in joined)
    )


def _is_gpu_table(table: ParsedTable) -> bool:
    if "wikitable" not in table.class_name.casefold() and "mw-datatable" not in table.class_name.casefold():
        return False
    joined = " ".join(_normalize_header(header) for header in table.headers)
    return (
        "model" in joined
        and "memory" in joined
        and ("size" in joined or "bus width" in joined or "configuration" in joined)
        and ("launch" in joined or "tdp" in joined or "bus interface" in joined or "bandwidth" in joined)
    )


def _cpu_spec_from_row(
    row: dict[str, str],
    *,
    vendor: str,
    source_url: str,
    source_revision_id: int | None,
    cache_key: str,
) -> CpuSpec | None:
    if _is_repeated_header_row(row):
        return None

    combined_name = _find_value(
        row,
        ["branding", "model"],
        ["branding and model"],
        ["processor branding"],
        ["processor family"],
        ["branding"],
    )
    model = _find_value(row, ["sku"], ["model"])
    name = _build_cpu_name(vendor=vendor, combined_name=combined_name, model=model)
    if not name:
        return None

    cores_text = _find_value(row, ["cores", "threads"], ["cores"])
    cores, threads = _parse_cores_threads(cores_text)
    if threads is None:
        threads = _parse_int(_find_value(row, ["threads"]))

    base_clock = _parse_float(
        _find_value(
            row,
            ["base", "clock"],
            ["clock", "base"],
        )
    )
    boost_clock = _parse_float(
        _find_value(
            row,
            ["turbo"],
            ["boost"],
            ["pb2"],
            ["pbo"],
            ["xfr"],
        )
    )
    cache_mb = _parse_float(_find_value(row, ["l3", "cache"], ["smart", "cache"], ["cache"]))
    tdp_w = _parse_float(_find_value(row, ["tdp"], ["power"]))
    socket = _find_value(row, ["socket"])
    release = _find_value(row, ["release", "date"], ["launch", "date"], ["launch"], ["released"])

    if not any(
        value is not None and value != ""
        for value in (cores, threads, base_clock, boost_clock, cache_mb, tdp_w, socket, release)
    ):
        return None

    unprefixed_name = _normalize_product_name(_remove_vendor_prefix(name, vendor))
    alias_candidates = [unprefixed_name]
    if model:
        alias_candidates.append(_normalize_product_name(model))

    return CpuSpec(
        canonical_name=name,
        aliases=_unique_aliases(alias_candidates, canonical_name=name),
        vendor=vendor,
        family=_infer_cpu_family(unprefixed_name),
        model=_normalize_product_name(model) if model else _infer_cpu_model(unprefixed_name),
        cores=cores,
        threads=threads,
        base_clock_ghz=base_clock,
        boost_clock_ghz=boost_clock,
        l3_cache_mb=cache_mb,
        tdp_w=tdp_w,
        socket=socket,
        release=release,
        source_url=source_url,
        source_revision_id=source_revision_id,
        raw_ref=RawReference(cache_key=cache_key),
    )


def _gpu_spec_from_row(
    row: dict[str, str],
    *,
    vendor: str,
    source_url: str,
    source_revision_id: int | None,
    cache_key: str,
) -> GpuSpec | None:
    if _is_repeated_header_row(row):
        return None

    name = _find_value(row, ["model name"], ["model"])
    if not name:
        return None
    canonical_name = _prepend_vendor(_normalize_product_name(name), vendor)

    memory_cell = _find_cell(
        row,
        ["memory", "size"],
        ["memory configuration"],
    )
    memory_size = _parse_memory_size_gib(
        memory_cell[1] if memory_cell else None,
        unit_hint=memory_cell[0] if memory_cell else None,
    )
    bus_width = _parse_int(
        _find_value(
            row,
            ["bus width"],
            ["memory", "bus width"],
        )
    )
    if bus_width is None and memory_cell:
        bus_width = _parse_bus_width(memory_cell[1])

    bandwidth_cell = _find_cell(row, ["bandwidth"], ["memory", "bandwidth"])
    bandwidth = _parse_bandwidth_gbs(
        bandwidth_cell[1] if bandwidth_cell else None,
        unit_hint=bandwidth_cell[0] if bandwidth_cell else None,
    )
    fp32_cell = _find_gpu_compute_cell(row, kind="fp32")
    fp16_cell = _find_gpu_compute_cell(row, kind="fp16")
    bf16_cell = _find_gpu_compute_cell(row, kind="bf16")
    fp8_cell = _find_gpu_compute_cell(row, kind="fp8")
    int8_cell = _find_gpu_compute_cell(row, kind="int8")

    spec = GpuSpec(
        canonical_name=canonical_name,
        aliases=_unique_aliases(
            [_normalize_product_name(_remove_vendor_prefix(canonical_name, vendor)), _normalize_product_name(name)],
            canonical_name=canonical_name,
        ),
        vendor=vendor,
        product_line=_infer_gpu_product_line(canonical_name),
        codename=_find_value(row, ["code name"]),
        process_nm=_parse_float(_find_process_value(row)),
        bus_interface=_find_value(row, ["bus interface"]),
        memory_size_gib=memory_size,
        memory_bus_width_bit=bus_width,
        memory_bandwidth_gbs=bandwidth,
        tdp_w=_parse_float(_find_value(row, ["tdp"])),
        cuda_compute_capability=_find_value(row, ["compute capability"]),
        processing_power_fp32_gflops=_parse_flops_gflops(
            fp32_cell[1] if fp32_cell else None,
            unit_hint=fp32_cell[0] if fp32_cell else None,
        ),
        processing_power_fp16_gflops=_parse_flops_gflops(
            fp16_cell[1] if fp16_cell else None,
            unit_hint=fp16_cell[0] if fp16_cell else None,
        ),
        processing_power_bf16_gflops=_parse_flops_gflops(
            bf16_cell[1] if bf16_cell else None,
            unit_hint=bf16_cell[0] if bf16_cell else None,
        )
        or _parse_flops_gflops(
            fp16_cell[1] if fp16_cell else None,
            unit_hint=fp16_cell[0] if fp16_cell else None,
        ),
        processing_power_fp8_gflops=_parse_flops_gflops(
            fp8_cell[1] if fp8_cell else None,
            unit_hint=fp8_cell[0] if fp8_cell else None,
        ),
        processing_power_int8_gops=_parse_ops_gops(
            int8_cell[1] if int8_cell else None,
            unit_hint=int8_cell[0] if int8_cell else None,
        ),
        source_url=source_url,
        source_revision_id=source_revision_id,
        raw_ref=RawReference(cache_key=cache_key),
    )
    if not any(
        value is not None and value != ""
        for value in (
            spec.memory_size_gib,
            spec.memory_bandwidth_gbs,
            spec.tdp_w,
            spec.processing_power_fp32_gflops,
            spec.bus_interface,
        )
    ):
        return None
    return spec


def _find_cell(row: dict[str, str], *patterns: list[str]) -> tuple[str, str] | None:
    for pattern in patterns:
        for header, value in row.items():
            normalized = _normalize_header(header)
            if all(token in normalized for token in pattern):
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
    return None


def _find_value(row: dict[str, str], *patterns: list[str]) -> str | None:
    cell = _find_cell(row, *patterns)
    if cell is None:
        return None
    return cell[1]


def _find_process_value(row: dict[str, str]) -> str | None:
    for header, value in row.items():
        normalized = _normalize_header(header)
        if normalized in {"fab", "fab nm", "process", "process nm", "node", "node nm"}:
            cleaned = _clean_cell_value(value)
            if cleaned:
                return cleaned
    return None


def _find_gpu_compute_cell(row: dict[str, str], *, kind: str) -> tuple[str, str] | None:
    for header, value in row.items():
        normalized = _normalize_header(header)
        if not normalized or "processing power" not in normalized and "precision" not in normalized and "tops" not in normalized:
            continue
        if kind == "fp32":
            if "single precision" in normalized and "accumulate" not in normalized:
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
            if "processing power" in normalized and not any(
                token in normalized
                for token in ("half precision", "fp16", "bf16", "bfloat16", "fp8", "int8", "double precision", "accumulate")
            ):
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
            continue
        if kind == "fp16":
            if "half precision" in normalized or "fp16" in normalized:
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
            continue
        if kind == "bf16":
            if "bf16" in normalized or "bfloat16" in normalized:
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
            continue
        if kind == "fp8":
            if "fp8" in normalized:
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
            continue
        if kind == "int8":
            if "int8" in normalized:
                cleaned = _clean_cell_value(value)
                if cleaned:
                    return header, cleaned
    return None


def _normalize_header(value: str) -> str:
    cleaned = _strip_notes(value).replace("/", " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned.casefold())
    return " ".join(cleaned.split())


def _strip_notes(value: str) -> str:
    cleaned = value.replace("\xa0", " ")
    cleaned = re.sub(r"\[\s*[^\]]+\s*\]", "", cleaned)
    cleaned = cleaned.replace("−", "-")
    return " ".join(cleaned.split()).strip(" /")


def _clean_cell_value(value: str) -> str | None:
    cleaned = _normalize_product_name(value)
    if not cleaned:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "", cleaned.casefold())
    if normalized in {"na", "notspecified", "unknown"}:
        return None
    if cleaned in {"?", "-", "--", "—", "— N/a"}:
        return None
    return cleaned


def _build_cpu_name(vendor: str, combined_name: str | None, model: str | None) -> str | None:
    combined = _normalize_product_name(combined_name or "")
    model_text = _normalize_product_name(model or "")
    if combined and model_text and lookup_key(model_text) not in lookup_key(combined):
        base = f"{combined} {model_text}"
    else:
        base = combined or model_text
    if not base:
        return None
    return _prepend_vendor(base, vendor)


def _prepend_vendor(name: str, vendor: str) -> str:
    prefix = {"intel": "Intel", "amd": "AMD", "nvidia": "NVIDIA"}[vendor]
    if lookup_key(name).startswith(lookup_key(prefix)):
        return _normalize_product_name(name)
    return _normalize_product_name(f"{prefix} {name}")


def _remove_vendor_prefix(name: str, vendor: str) -> str:
    prefix = {"intel": "Intel", "amd": "AMD", "nvidia": "NVIDIA"}[vendor]
    if lookup_key(name).startswith(lookup_key(prefix)):
        return _normalize_product_name(name[len(prefix) :])
    return _normalize_product_name(name)


def _parse_cores_threads(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    numbers = [int(match.group()) for match in re.finditer(r"\d+", value)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], None
    return numbers[0], numbers[1]


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(?<![A-Za-z0-9])-?\d[\d,]*", value)
    if match is None:
        return None
    return int(match.group().replace(",", ""))


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(?<![A-Za-z0-9])-?\d[\d,]*(?:\.\d+)?", value)
    if match is None:
        return None
    return float(match.group().replace(",", ""))


def _parse_memory_size_gib(value: str | None, *, unit_hint: str | None = None) -> float | None:
    if not value:
        return None
    numbers = _parse_numeric_values(value)
    if not numbers:
        return None
    number = numbers[0]
    lower = f"{unit_hint or ''} {value}".casefold().replace(",", "")
    if "tb" in lower or "tib" in lower:
        return number * 1024
    if "gb" in lower or "gib" in lower:
        return number
    if "mb" in lower or "mib" in lower:
        return number / 1024
    if "kb" in lower or "kib" in lower:
        return number / (1024 * 1024)
    return number


def _parse_bandwidth_gbs(value: str | None, *, unit_hint: str | None = None) -> float | None:
    if not value:
        return None
    number = _parse_float(value)
    if number is None:
        return None
    lower = re.sub(r"\s+", "", f"{unit_hint or ''} {value}".casefold())
    if "tb/s" in lower or "tbs" in lower:
        return number * 1000
    if "gb/s" in lower or "gbs" in lower:
        return number
    if "mb/s" in lower or "mbs" in lower:
        return number / 1000
    return number


def _parse_bus_width(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)\s*-?\s*bit", value.casefold())
    if match is None:
        return None
    return int(match.group(1))


def _parse_flops_gflops(value: str | None, *, unit_hint: str | None = None) -> float | None:
    if not value:
        return None
    number = _parse_float(value)
    if number is None:
        return None
    lower = _normalize_measurement_text(f"{unit_hint or ''} {value}")
    if "tflops" in lower:
        return number * 1000
    if "pflops" in lower:
        return number * 1_000_000
    return number


def _parse_ops_gops(value: str | None, *, unit_hint: str | None = None) -> float | None:
    if not value:
        return None
    number = _parse_float(value)
    if number is None:
        return None
    lower = _normalize_measurement_text(f"{unit_hint or ''} {value}")
    if "tops" in lower:
        return number * 1000
    if "pops" in lower:
        return number * 1_000_000
    if "gops" in lower:
        return number
    return number


def _parse_numeric_values(value: str | None) -> list[float]:
    if not value:
        return []
    return [
        float(match.group().replace(",", ""))
        for match in re.finditer(r"(?<![A-Za-z0-9])-?\d[\d,]*(?:\.\d+)?", value)
    ]


def _normalize_measurement_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _infer_cpu_family(name: str) -> str | None:
    parts = name.split()
    if len(parts) >= 2 and parts[0] in {"Core", "Ryzen"}:
        return " ".join(parts[:2])
    if parts and parts[0] in {"Xeon", "Athlon", "Threadripper", "Pentium", "Celeron", "EPYC"}:
        return parts[0]
    return " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else None)


def _infer_cpu_model(name: str) -> str | None:
    parts = name.split()
    return parts[-1] if parts else None


def _infer_gpu_product_line(name: str) -> str | None:
    lowered = name.casefold()
    if "geforce" in lowered:
        return "GeForce"
    if "radeon pro" in lowered:
        return "Radeon Pro"
    if "radeon" in lowered:
        return "Radeon"
    if "tesla" in lowered:
        return "Tesla"
    if "quadro" in lowered:
        return "Quadro"
    if "titan" in lowered:
        return "TITAN"
    return None


def _unique_aliases(candidates: list[str], *, canonical_name: str) -> list[str]:
    aliases: list[str] = []
    seen = {lookup_key(canonical_name)}
    for candidate in candidates:
        if not candidate:
            continue
        cleaned = _normalize_product_name(candidate)
        key = lookup_key(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        aliases.append(cleaned)
    return aliases


def _is_repeated_header_row(row: dict[str, str]) -> bool:
    header_variants = _header_variants(row.keys())
    matched_values = 0
    for value in row.values():
        normalized = _normalize_header(value)
        if not normalized:
            continue
        if any(
            normalized == variant
            or normalized.startswith(f"{variant} ")
            or variant.startswith(f"{normalized} ")
            for variant in header_variants
            if variant
        ):
            matched_values += 1
    return matched_values >= 2


def _header_variants(headers: object) -> set[str]:
    variants: set[str] = set()
    for header in headers:
        if not isinstance(header, str):
            continue
        normalized = _normalize_header(header)
        if normalized:
            variants.add(normalized)
        for part in header.split("/"):
            normalized_part = _normalize_header(part)
            if normalized_part:
                variants.add(normalized_part)
    return variants


def _normalize_product_name(value: str) -> str:
    cleaned = clean_name(_strip_notes(value))
    cleaned = re.sub(r"^\(\s*([A-Z0-9+./-]+(?:\s+[A-Z0-9+./-]+)*)\s*\)\s+", r"\1 ", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    return clean_name(cleaned)
