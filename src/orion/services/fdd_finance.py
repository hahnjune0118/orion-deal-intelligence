"""Decimal-based FDD workpaper calculations; independent of the DD scoring engine.

Amounts use the source pack's single currency/unit. Expenses and balance-sheet
amounts are positive inputs; adjustments and cash bridge movements are signed.
None propagates through calculations. No document text is treated as financial
data and no missing source is replaced with zero.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
from importlib.resources import files
import io
import json
import re

D = Decimal
MONTHLY_FIELDS = ("period", "revenue", "cogs", "opex", "da", "ar", "inventory", "other_assets", "ap",
                  "other_liabilities", "cash", "restricted_cash", "borrowings", "lease_liability",
                  "interest_paid", "tax_paid", "noncash", "other_operating", "operating_cash",
                  "maintenance_capex", "growth_capex")
DATASETS = {
    "monthly": ("monthly_financials", MONTHLY_FIELDS),
    "trial": ("trial_balance", ("period", "revenue", "cogs", "opex", "da")),
    "gl": ("gl_balances", ("period", "account_code", "account_name", "balance")),
    "statutory": ("statutory_financials", ("year", "metric", "amount")),
    "segments": ("revenue_segments", ("period", "segment", "revenue", "cogs")),
    "ledger": ("adjustment_ledger", ("id", "period", "account", "amount", "description")),
    "aging": ("aging", ("period", "account", "bucket", "amount")),
    "budget": ("budget", ("period", "revenue", "ebitda", "contracted_revenue", "capacity_revenue", "assumption")),
}
LABELS = {"revenue": "매출", "cogs": "매출원가", "opex": "영업비용 (D&A 제외)", "da": "감가상각비",
          "ar": "매출채권", "inventory": "재고", "other_assets": "기타 영업유동자산", "ap": "매입채무",
          "other_liabilities": "기타 영업유동부채", "cash": "사용가능 현금", "restricted_cash": "제한성 현금",
          "borrowings": "차입금", "lease_liability": "리스부채", "interest_paid": "현금 이자", "tax_paid": "현금 법인세",
          "noncash": "기타 비현금 가산", "other_operating": "기타 영업현금 영향", "operating_cash": "보고 영업현금흐름",
          "maintenance_capex": "유지 CAPEX", "growth_capex": "성장 CAPEX", "ebitda": "EBITDA"}
TEXT_FIELDS = {"period", "year", "metric", "segment", "id", "account", "description", "bucket", "assumption", "account_code", "account_name"}


class FinanceError(ValueError):
    pass


def decimal(value, *, optional=True):
    if value is None or value == "":
        if optional:
            return None
        raise FinanceError("금액을 입력하세요. 미제공 값은 빈칸으로 둡니다.")
    if isinstance(value, bool):
        raise FinanceError("금액에 참/거짓 값을 사용할 수 없습니다.")
    try:
        result = D(str(value).strip())
        if not result.is_finite() or abs(result) >= D("1e15") or result.as_tuple().exponent < -6:
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise FinanceError("금액은 유한한 숫자(소수 6자리 이하)로 입력하세요.") from None


def serial(value):
    if isinstance(value, D):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: serial(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def add(values):
    values = list(values)
    return None if not values or any(v is None for v in values) else sum(values, D(0))


def subtract(a, b):
    return None if a is None or b is None else a - b


def ratio(a, b):
    return None if a is None or b in (None, 0) else a / b


def number(row, key):
    return decimal(row.get(key)) if row else None


def ebitda(row):
    return subtract(subtract(number(row, "revenue"), number(row, "cogs")), number(row, "opex"))


def nwc(row):
    assets = add(number(row, k) for k in ("ar", "inventory", "other_assets"))
    liabilities = add(number(row, k) for k in ("ap", "other_liabilities"))
    return subtract(assets, liabilities)


def parse_csv(kind, text):
    """Strict typed entry, not native document ingestion or provider execution."""
    if kind not in DATASETS or not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 140_000:
        raise FinanceError("표 종류를 선택하고 140KB 이하의 CSV를 붙여넣으세요.")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""))
    expected = list(DATASETS[kind][1])
    if reader.fieldnames != expected:
        raise FinanceError("CSV 열·순서가 템플릿과 다릅니다: " + ",".join(expected))
    rows, identities = [], set()
    for index, raw in enumerate(reader, 2):
        if None in raw or any(value is None for value in raw.values()):
            raise FinanceError(f"{index}행의 열 개수를 확인하세요.")
        row = {}
        for key, value in raw.items():
            if len(value) > 1500:
                raise FinanceError(f"{index}행의 텍스트가 너무 깁니다.")
            if key in TEXT_FIELDS:
                row[key] = value.strip()
            else:
                amount = decimal(value)
                if key not in {"noncash", "other_operating", "operating_cash", "ebitda", "balance"} and amount is not None and amount < 0:
                    raise FinanceError(f"{index}행 {key}: 원천 비용·잔액은 양수로 입력하세요.")
                row[key] = serial(amount)
        if "period" in row and not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", row["period"]):
            raise FinanceError(f"{index}행: 기간은 YYYY-MM 형식입니다.")
        if kind == "statutory" and (not re.fullmatch(r"20\d{2}", row["year"]) or row["metric"] not in {"revenue", "cogs", "opex", "da"}):
            raise FinanceError("연간 재무제표는 연도와 revenue/cogs/opex/da 계정을 사용합니다.")
        if kind == "aging" and row["account"] not in {"ar", "inventory", "ap"}:
            raise FinanceError("연령분석 계정은 ar / inventory / ap입니다.")
        key = tuple(row.get(k) for k in {
            "monthly": ("period",), "trial": ("period",), "statutory": ("year", "metric"),
            "segments": ("period", "segment"), "ledger": ("id",), "aging": ("period", "account", "bucket"), "gl": ("period", "account_code"),
            "budget": ("period",),
        }[kind])
        if any(not k for k in key) or key in identities:
            raise FinanceError(f"{index}행: 기간·계정·항목 키가 비어 있거나 중복됩니다.")
        identities.add(key)
        rows.append(row)
        if len(rows) > (120 if kind in {"monthly", "trial", "budget"} else 1000):
            raise FinanceError("표의 행 한도를 초과했습니다(월별 120행, 상세 1,000행).")
    if not rows:
        raise FinanceError("CSV에 데이터 행이 없습니다.")
    # Financial tables must be monthly observations, not silently filled gaps.
    return rows


def csv_text(rows, columns=None):
    rows = list(rows)
    columns = list(columns or (rows[0] if rows else []))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(k) is None else row[k] for k in columns])
    return stream.getvalue()


@lru_cache(maxsize=1)
def demo_pack():
    root = files("orion").joinpath("resources/fdd_lab")
    manifest = json.loads(root.joinpath("manifest.json").read_text(encoding="utf-8"))
    documents, data = {}, {}
    for kind, (identifier, fields_) in DATASETS.items():
        description = next(d for d in manifest["documents"] if d["id"] == identifier)
        raw = root.joinpath(description["filename"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != description["sha256"]:
            raise FinanceError("합성 재무팩의 원천 해시가 일치하지 않습니다.")
        text = raw.decode("utf-8")
        data[kind] = parse_csv(kind, text)
        documents[identifier] = {**description, "kind": kind, "columns": list(fields_), "text": text}
    return {"manifest": manifest, "data": data, "documents": documents}


def pack_for(state):
    """Return a fresh, typed view; caller cannot mutate the cached fixture."""
    base = demo_pack() if state.get("demo_pack") else {"data": {}, "documents": {}, "manifest": {}}
    data = json.loads(json.dumps(base["data"]))
    documents = json.loads(json.dumps(base["documents"]))
    for kind, override in state.get("datasets", {}).items():
        identifier = f"entered_{kind}_v{override['version']}"
        data[kind] = override["rows"]
        # Old source versions remain available for history, but active adjustments
        # are invalidated by the service when an input table is replaced.
        documents = {k: v for k, v in documents.items() if v["kind"] != kind}
        documents[identifier] = dict(id=identifier, filename=override["filename"], version=override["version"],
                                    description="사용자 입력 재무표 · 외부 검증 전", classification="user_entered",
                                    sha256=override["sha256"], kind=kind, columns=list(DATASETS[kind][1]),
                                    text=csv_text(override["rows"], DATASETS[kind][1]))
    for kind in DATASETS:
        data.setdefault(kind, [])
    return {"manifest": base["manifest"], "data": data, "documents": documents}


def source_ref(pack, kind, row, column):
    document = next((d for d in pack["documents"].values() if d["kind"] == kind), None)
    if not document or row is None:
        return None
    return {"document": document["id"], "row": row + 2, "column": column}


def resolve_ref(pack, ref):
    if not isinstance(ref, dict):
        return None
    doc = pack["documents"].get(ref.get("document"))
    row, column = ref.get("row"), ref.get("column")
    if not doc or type(row) is not int or column not in doc["columns"]:
        return None
    rows = pack["data"][doc["kind"]]
    if not 2 <= row <= len(rows) + 1:
        return None
    return {**ref, "filename": doc["filename"], "version": doc["version"], "sha256": doc["sha256"],
            "value": rows[row - 2].get(column), "record": rows[row - 2], "classification": doc["classification"]}


def _selected(rows, period):
    rows = sorted(rows, key=lambda r: r["period"])
    if period == "LTM":
        return rows[-12:]
    return [r for r in rows if r["period"].startswith(str(period))]


def consecutive(rows):
    dates = [int(r["period"][:4]) * 12 + int(r["period"][5:]) for r in rows]
    return bool(dates) and all(b - a == 1 for a, b in zip(dates, dates[1:]))


def eligible_adjustments(state, area, selected=None):
    selected_periods = {r["period"] for r in selected or []}
    return [a for a in state["adjustments"] if a["area"] == area and a["decision"] == "분석 반영"
            and (area != "QoE" or a["period"] in selected_periods)]


def calculations(state, period=None):
    pack = pack_for(state)
    data = pack["data"]
    rows = sorted(data["monthly"], key=lambda r: r["period"])
    scope_rows = [r for r in rows if state['scope']['start'] <= r['period'] <= state['scope']['end']]
    period = period or (scope_rows[-1]["period"][:4] if scope_rows else "")
    selected = _selected(scope_rows, period)
    continuous = consecutive(selected) and (period != 'LTM' or len(selected) == 12)
    periods = [r["period"] for r in selected]
    current = selected[-1] if selected else None
    prior = []
    for value in periods:
        previous = str(int(value[:4]) - 1) + value[4:]
        match = next((r for r in scope_rows if r["period"] == previous), None)
        if match:
            prior.append(match)
    revenue = add(number(r, "revenue") for r in selected) if continuous else None
    reported = add(ebitda(r) for r in selected) if continuous else None
    previous_revenue = add(number(r, "revenue") for r in prior) if len(prior) == len(selected) else None
    previous_ebitda = add(ebitda(r) for r in prior) if len(prior) == len(selected) else None
    qoe = eligible_adjustments(state, "QoE", selected)
    qoe_sum = sum((decimal(a["amount"], optional=False) for a in qoe), D(0))
    adjusted = None if reported is None else reported + qoe_sum
    # A zero sum of known adopted adjustments is valid; absent underlying
    # financials remain None. No adjustment is adopted implicitly.
    latest_nwc = nwc(current)
    nwc_adjustments = [a for a in eligible_adjustments(state, "NWC") if current and a["period"] == current["period"]]
    nwc_sum = sum((decimal(a["amount"], optional=False) for a in nwc_adjustments), D(0))
    adjusted_nwc = None if latest_nwc is None else latest_nwc + nwc_sum
    window = [r for r in scope_rows if current and r["period"] <= current["period"]]
    pegs = {}
    for count in (3, 6, 12):
        tail = window[-count:]
        total = add(nwc(r) for r in tail) if len(tail) == count and consecutive(tail) else None
        pegs[str(count)] = None if total is None else total / count
    pegs["manual"] = decimal(state["transaction"].get("peg_manual"))
    peg = pegs.get(state["transaction"].get("peg_method", "12"))
    # cash is explicitly unrestricted and distinct from restricted_cash.
    gross_debt = add(number(current, k) for k in ("borrowings", "lease_liability"))
    base_net_debt = subtract(gross_debt, number(current, "cash"))
    debt_adjustments = [a for a in eligible_adjustments(state, "Net debt") if current and a["period"] == current["period"]]
    debt_sum = sum((decimal(a["amount"], optional=False) for a in debt_adjustments), D(0))
    net_debt = None if base_net_debt is None else base_net_debt + debt_sum
    # Opening balance is required for an EBITDA-to-cash bridge.
    before = next((r for r in reversed(rows) if periods and r['period'] < periods[0]), None)
    if before and (int(periods[0][:4]) * 12 + int(periods[0][5:]) -
                   int(before['period'][:4]) * 12 - int(before['period'][5:])) != 1:
        before = None
    opening_nwc = nwc(before)
    manifest = pack["manifest"]
    if before is None and selected and not state.get("datasets", {}).get("monthly") and manifest.get("opening_period"):
        start_index = int(periods[0][:4]) * 12 + int(periods[0][5:])
        opening_index = int(manifest["opening_period"][:4]) * 12 + int(manifest["opening_period"][5:])
        if start_index - opening_index == 1:
            opening_nwc = nwc(manifest["opening_nwc"])
    movements = {k: add(number(r, k) for r in selected) if continuous else None for k in
                 ("interest_paid", "tax_paid", "noncash", "other_operating", "operating_cash", "maintenance_capex", "growth_capex")}
    delta_nwc = subtract(latest_nwc, opening_nwc)
    cash_expected = add([reported, None if movements["interest_paid"] is None else -movements["interest_paid"],
                         None if movements["tax_paid"] is None else -movements["tax_paid"],
                         None if delta_nwc is None else -delta_nwc, movements["noncash"], movements["other_operating"]])
    cash_residual = subtract(movements["operating_cash"], cash_expected)
    capex = add([movements["maintenance_capex"], movements["growth_capex"]])
    fcf = subtract(movements["operating_cash"], capex)
    ev = decimal(state["transaction"].get("ev"))
    nwc_price_adjustment = subtract(adjusted_nwc, peg)
    if state['transaction']['mechanism'] == 'Locked box':
        # No automatic completion NWC true-up under this selected scenario.
        nwc_price_adjustment = D(0)
    equity = add([ev, None if net_debt is None else -net_debt, nwc_price_adjustment])
    # EV is a user-entered scenario, never automatically increased by EBITDA.
    reconciliations = []
    mapping = {row['account_code']: row for row in state.get('mapping', [])}
    unmapped = sorted({r['account_code'] for r in data['gl'] if r['account_code'] not in mapping})
    if selected:
        for year in sorted({p[:4] for p in periods}):
            year_rows = [r for r in selected if r["period"].startswith(year)]
            year_periods = {r["period"] for r in year_rows}
            tb = [r for r in data["trial"] if r["period"] in year_periods]
            full_year = len(year_rows) == 12 and consecutive(year_rows)
            for metric in ("revenue", "cogs", "opex", "da"):
                identifier = f"{year}-{metric}"
                management = add(number(r, metric) for r in year_rows) if consecutive(year_rows) else None
                trial = add(number(r, metric) for r in tb) if {r["period"] for r in tb} == year_periods else None
                gl_rows = [r for r in data['gl'] if r['period'] in year_periods and mapping.get(r['account_code'], {}).get('metric') == metric]
                gl = add(None if number(r, 'balance') is None else number(r, 'balance') * D(mapping[r['account_code']]['multiplier']) for r in gl_rows)
                if {r['period'] for r in gl_rows} != year_periods or unmapped:
                    gl = None
                residual_gl = subtract(trial, gl)
                statutory_row = next((r for r in data["statutory"] if r["year"] == year and r["metric"] == metric), None)
                statutory = number(statutory_row, "amount") if full_year else None
                note = state["reconciliations"].get(identifier, {})
                adjustment_tb = decimal(note.get("adjustment_tb", "0"), optional=False)
                adjustment_fs = decimal(note.get("adjustment_fs", "0"), optional=False)
                mt = subtract(management, trial)
                ts = subtract(trial, statutory)
                residual_tb = None if mt is None else mt - adjustment_tb
                residual_fs = None if ts is None else ts - adjustment_fs
                reconciliations.append(dict(id=identifier, year=year, metric=metric,
                    management=management, trial=trial, gl=gl, residual_gl=residual_gl, statutory=statutory, adjustment_tb=adjustment_tb,
                    adjustment_fs=adjustment_fs, difference_tb=mt, difference_fs=ts,
                    residual_tb=residual_tb, residual_fs=residual_fs,
                    status="미제공 / 기간 불일치" if residual_tb is None or residual_fs is None or residual_gl is None else
                    ("미대사" if residual_tb != 0 or residual_fs != 0 or residual_gl != 0 else ("조정 대사" if adjustment_tb or adjustment_fs else "일치")),
                    explanation=note.get("explanation", ""), source=note.get("source")))
    segments = [r for r in data["segments"] if r["period"] in periods]
    segment_sum = add(number(r, "revenue") for r in segments)
    segment_residual = subtract(segment_sum, revenue)
    latest_aging = [r for r in data["aging"] if current and r["period"] == current["period"]]
    aging_checks = []
    for metric in ("ar", "inventory", "ap"):
        total = add(number(r, "amount") for r in latest_aging if r["account"] == metric)
        aging_checks.append({"account": metric, "total": total, "balance": number(current, metric),
                             "residual": subtract(total, number(current, metric))})
    budgets = data["budget"]
    budget_revenue = add(number(r, "revenue") for r in budgets)
    budget_ebitda = add(number(r, "ebitda") for r in budgets)
    contracted = add(number(r, "contracted_revenue") for r in budgets)
    capacity = add(number(r, "capacity_revenue") for r in budgets)
    return dict(pack=pack, period=period, selected=selected, periods=periods, current=current, prior=prior,
                revenue=revenue, prior_revenue=previous_revenue, revenue_growth=ratio(subtract(revenue, previous_revenue), previous_revenue),
                reported_ebitda=reported, prior_ebitda=previous_ebitda, ebitda_margin=ratio(reported, revenue),
                qoe=qoe, qoe_sum=qoe_sum, adjusted_ebitda=adjusted, reported_nwc=latest_nwc,
                nwc_adjustments=nwc_adjustments, adjusted_nwc=adjusted_nwc, pegs=pegs, peg=peg,
                base_net_debt=base_net_debt, net_debt=net_debt, debt_adjustments=debt_adjustments,
                opening_nwc=opening_nwc, delta_nwc=delta_nwc, cash=movements, cash_expected=cash_expected,
                cash_residual=cash_residual, capex=capex, fcf=fcf, cash_conversion=ratio(movements["operating_cash"], reported),
                ev=ev, nwc_price_adjustment=nwc_price_adjustment, equity=equity,
                reconciliations=reconciliations, unmapped=unmapped, segments=segments, segment_residual=segment_residual,
                aging=latest_aging, aging_checks=aging_checks, budgets=budgets, budget_revenue=budget_revenue,
                budget_ebitda=budget_ebitda, contracted_coverage=ratio(contracted, budget_revenue),
                budget_growth=ratio(subtract(budget_revenue, revenue), revenue) if len(budgets) == len(selected) and consecutive(budgets) and continuous else None, capacity=capacity,
                capacity_gap=subtract(budget_revenue, capacity), continuous=continuous)
