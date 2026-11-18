"""Session-bound FDD drafts, review gates and exports for the local workbench.

This is an additive financial-workpaper boundary, not a change to canonical
evidence, ranked questions, entity contracts, or the official scoring engine.
Names entered for preparation/review are self-declared, not authenticated roles.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import hmac
import io
import json
import re
from zipfile import ZipFile, ZIP_DEFLATED

from .fdd_finance import (DATASETS, LABELS, D, FinanceError, calculations, csv_text, decimal,
                          demo_pack, nwc, pack_for, parse_csv, resolve_ref, serial)

AREAS = ("과거 실적", "QoE", "NWC", "Net debt", "현금흐름", "전망")
REQUEST_STATES = ("미요청", "요청", "수령", "보완 요청")
ISSUE_STATES = ("추가 확인", "경영진 답변", "판단 작성", "해결", "범위 제한")
ADJUSTMENT_DECISIONS = ("검토 후보", "분석 반영", "제외")
SCOPE_FIELDS = ("entity", "side", "transaction_type", "business_scope", "start", "end", "as_of", "gaap", "currency", "unit", "exclusions")


def _text(value, label, limit=2000, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise FinanceError(f"{label}: {'1~' if required else ''}{limit}자 이내로 입력하세요.")
    return value.strip()


def _choice(value, choices, label):
    if value not in choices:
        raise FinanceError(f"{label} 선택값을 확인하세요.")
    return value


def _date(value, label, optional=False):
    value = _text(value, label, 10, not optional)
    if not value and optional:
        return ""
    try:
        date.fromisoformat(value)
    except ValueError:
        raise FinanceError(f"{label}: YYYY-MM-DD 형식으로 입력하세요.") from None
    return value


def _period(value):
    value = _text(value, "해당 월", 7, True)
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", value):
        raise FinanceError("해당 월은 YYYY-MM 형식입니다.")
    return value


def _source_row(value):
    amount = decimal(value, optional=False)
    if amount != amount.to_integral_value() or not 2 <= amount <= 1001:
        raise FinanceError('원천 행 번호는 2 이상의 정수입니다(머리글은 1행).')
    return int(amount)


def content_hash(state):
    body = {k: v for k, v in state.items() if k not in {"binding", "history", "revision", "review"}}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def initial_state(case_id, company, binding):
    demo = case_id == "nb"
    pack = demo_pack() if demo else None
    state = dict(schema=1, binding=binding, case_id=case_id, revision=1, demo_pack=demo,
                 pack_hash=hashlib.sha256(json.dumps(pack["manifest"], sort_keys=True).encode()).hexdigest() if demo else None,
                 scope=dict(entity="Northstar FDD Lab" if demo else company, side="매수자", transaction_type="지분 인수",
                            business_scope="기업용 소프트웨어 구독·구축 서비스 (합성 재무팩)" if demo else "입력 필요",
                            start="2024-01", end="2025-12", as_of="2025-12-31", gaap="합성 IFRS 형식" if demo else "K-IFRS",
                            currency="USD" if demo else "KRW", unit="천 달러" if demo else "백만원",
                            exclusions="세무·법률·IT 실사 및 외부확인 제외. 기존 Northstar 증빙팩과 별개의 합성 재무 검증 자료." if demo else "미제공 자료·제외 범위를 입력하세요."),
                 datasets={}, requests=[], adjustments=[], issues=[], reconciliations={},
                 mapping=[dict(account_code=code, metric=metric, multiplier=sign) for code, metric, sign in
                          [('4000', 'revenue', '-1'), ('5000', 'cogs', '1'), ('6000', 'opex', '1'), ('6500', 'da', '1')]] if demo else [],
                 transaction=dict(ev=None, peg_method="12", peg_manual=None, mechanism="Completion accounts", note=""),
                 review=dict(preparer="", reviewer="", prepared_hash=None, approved_hash=None, comments=[]), history=[])
    if not demo:
        return state
    requests = [
        ("IRL-001", "과거 실적", "월별 관리손익·재무상태·현금흐름", "monthly_financials", "수령", "DATA"),
        ("IRL-002", "과거 실적", "시산표·총계정원장 집계", "trial_balance", "수령", "RECON"),
        ("IRL-003", "과거 실적", "연간 재무제표와 주석", "statutory_financials", "수령", "RECON"),
        ("IRL-004", "QoE", "비경상 비용·미계상 비용 원장", "adjustment_ledger", "수령", "QOE"),
        ("IRL-005", "NWC", "채권·채무·재고 연령", "aging", "수령", "NWC"),
        ("IRL-006", "전망", "사업계획·생산능력·계약 가정", "budget", "수령", "FORECAST"),
        ("IRL-007", "Net debt", "차입·현금·리스 명세 및 은행 확인", "", "요청", "DEBT"),
        ("IRL-008", "과거 실적", "12월 매출 미전기 차이 12 설명·전표", "", "보완 요청", "RECON"),
    ]
    state["requests"] = [dict(id=i, area=a, title=t, source_id=s, version=1 if s else None,
                              owner="재무팀", due="2026-11-20", status=st, followup="미전기 차이 설명·전표 필요" if st == '보완 요청' else "", workpaper=w) for i, a, t, s, st, w in requests]
    for i, area, name, amount, month, row, key, judgment in [
        ("ADJ-001", "QoE", "일회성 소송 비용 가산", "35", "2025-07", 2, "litigation_expense", "비반복 비용으로 분석 반영. 합의서·지급 내역 추가 확인 필요."),
        ("ADJ-002", "QoE", "주주 개인 비용 가산", "18", "2025-09", 3, "shareholder_personal", "사업 운영과 무관한 비용으로 분석 반영."),
        ("ADJ-003", "QoE", "유지보수 미계상 비용 차감", "-12", "2025-12", 4, "maintenance_underaccrual", "반복 운영 비용이므로 EBITDA 차감. 미지급액은 별도 순차입금 검토."),
        ("ADJ-004", "NWC", "91일 초과 채권 추가 충당금", "-20", "2025-12", 5, "ar_reserve", "기말 회수가능성 조정 후보를 분석에 반영. peg에는 자동 소급하지 않음."),
        ("ADJ-005", "Net debt", "거래 전 미지급 성과급", "25", "2025-12", 6, "bonus_payable", "월별 NWC 기타부채에 미포함. 현금 유출 의무의 debt-like 후보."),
        ("ADJ-006", "Net debt", "미지급 유지보수 비용", "12", "2025-12", 4, "maintenance_underaccrual", "NWC에는 미포함. QoE와 순차입금의 이익·잔액 효과는 별도임."),
    ]:
        state["adjustments"].append(dict(id=i, area=area, name=name, amount=amount, period=month,
            economic_key=key, source={"document": "adjustment_ledger", "row": row, "column": "amount"},
            management="합성 원장에 기재된 경영진 제시 후보", judgment=judgment,
            recurring="반복" if key == "maintenance_underaccrual" else "비반복", cash="현금", decision="분석 반영", agreed="미합의"))
    state["issues"] = [
        dict(id="ISS-001", area="과거 실적", title="관리매출과 시산표의 12월 차이", impact="12", priority="높음", status="추가 확인",
             request_id="IRL-008", adjustment_id="", management="설명 미수령", conclusion="차이 12의 기간 귀속과 전표 확인 필요."),
        dict(id="ISS-002", area="QoE", title="조정 후보의 반복성·부채성 분류 확인", impact=None, priority="보통", status="판단 작성",
             request_id="IRL-004", adjustment_id="ADJ-003", management="원장 발췌 제공", conclusion="조정 EBITDA와 debt-like의 이익·잔액 효과를 각각 검토."),
        dict(id="ISS-003", area="Net debt", title="현금·차입잔액의 외부 확인 미수령", impact=None, priority="높음", status="추가 확인",
             request_id="IRL-007", adjustment_id="", management="잔액 자료만 제공", conclusion="은행 확인 미수령에 따른 범위 제한. 차입 약정·담보·현금 제한 조건 확인 필요."),
    ]
    return state


def review_blockers(state):
    result = []
    calc = calculations(state)
    if not calc["selected"]:
        result.append("재무자료 미제공")
    annual = [calculations(state, year) for year in sorted({r['period'][:4] for r in calc['pack']['data']['monthly']
              if state['scope']['start'] <= r['period'] <= state['scope']['end']})]
    all_reconciliations = [row for c in annual for row in c['reconciliations']]
    if any(r["status"] not in {"일치", "조정 대사"} for r in all_reconciliations) or not all_reconciliations:
        result.append("미대사·미제공 재무 계정")
    if calc["adjusted_nwc"] is None or calc["net_debt"] is None:
        result.append("NWC·순차입금 기준잔액 미제공")
    if not annual or any(c['cash_residual'] is None or c['cash_residual'] != 0 for c in annual):
        result.append("영업현금흐름 대사 미완료")
    if any(c['segments'] and c['segment_residual'] != 0 for c in annual):
        result.append('부문 매출 합계 대사 미완료')
    if calc['aging'] and any(r['residual'] != 0 for r in calc['aging_checks']):
        result.append('연령 분석 잔액 대사 미완료')
    if any(i["priority"] == "높음" and i["status"] not in {"해결", "범위 제한"} for i in state["issues"]):
        result.append("미해결 중요 쟁점")
    if any(c["status"] == "미해결" for c in state["review"]["comments"]):
        result.append("미해결 검토 의견")
    if any(a["decision"] == "분석 반영" and not resolve_ref(calc["pack"], a["source"]) for a in state["adjustments"]):
        result.append("조정 원천 버전 불일치")
    if not all(state["scope"].get(k) for k in SCOPE_FIELDS):
        result.append("실사 범위 필수 항목 미입력")
    return result


def review_status(state):
    fingerprint = content_hash(state)
    if state["review"]["approved_hash"] == fingerprint and not review_blockers(state):
        return "검토 기록 확정"
    if state["review"]["prepared_hash"] == fingerprint:
        return "작성 제출 · 검토 대기"
    return "작성 중"


class FDDWorkpapers:
    def __init__(self, secret):
        self.key = secret.encode() if isinstance(secret, str) else secret

    def _binding(self, case_id, session_id):
        return hmac.new(self.key, ("fdd-v1|" + case_id + "|" + session_id).encode(), hashlib.sha256).hexdigest()

    def read(self, token, case_id, session_id, company=""):
        binding = self._binding(case_id, session_id)
        if not token:
            return initial_state(case_id, company, binding)
        try:
            if not isinstance(token, str) or len(token) > 180_000:
                raise ValueError()
            body, signature = token.rsplit(".", 1)
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            state = json.loads(base64.urlsafe_b64decode(body))
            if state["binding"] != binding or state["case_id"] != case_id or state["schema"] != 1:
                raise ValueError()
            if state["demo_pack"]:
                current_hash = hashlib.sha256(json.dumps(demo_pack()["manifest"], sort_keys=True).encode()).hexdigest()
                if state["pack_hash"] != current_hash:
                    raise ValueError()
            return state
        except Exception:
            raise FinanceError("재무 조서 세션이 현재 프로젝트와 일치하지 않습니다. 산출물을 보관하고 재무 조서를 초기화하세요.") from None

    def sign(self, state):
        body = base64.urlsafe_b64encode(json.dumps(serial(state), ensure_ascii=False, separators=(",", ":")).encode()).decode()
        # Three project drafts, the active token and a typed CSV must fit under
        # the existing 1 MiB HTTP boundary without enlarging the demo endpoint.
        if len(body) > 179_900:
            raise FinanceError("조서 저장 한도입니다. 데이터북을 내려받고 입력 자료의 크기를 줄이세요.")
        return body + "." + hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()

    def update(self, state, action, values, original_documents=()):
        state = deepcopy(state)
        original_state = deepcopy(state)
        before = content_hash(state)
        pack = pack_for(state)
        source_ids = set(pack["documents"]) | set(original_documents)
        detail = ""
        if action == "scope":
            scope = {key: _text(values.get(key), key, 2000 if key in {"exclusions", "business_scope"} else 120, True) for key in SCOPE_FIELDS}
            _period(scope["start"]); _period(scope["end"]); _date(scope["as_of"], "기준일")
            if scope["start"] > scope["end"] or scope["as_of"][:7] < scope["end"]:
                raise FinanceError("검토 시작·종료 기간과 기준일의 순서를 확인하세요.")
            _choice(scope["side"], ("매수자", "매도자", "투자·금융기관"), "실사 관점")
            if not re.fullmatch(r"[A-Z]{3}", scope["currency"]):
                raise FinanceError("통화는 KRW/USD 등 대문자 3자리로 입력하세요.")
            if pack["data"]["monthly"] and (scope["currency"], scope["unit"]) != (state["scope"]["currency"], state["scope"]["unit"]):
                raise FinanceError("자료가 연결된 상태에서 통화·단위만 변경할 수 없습니다. 빈 재무 조서에서 새 자료를 입력하세요.")
            state["scope"] = scope
            detail = "범위·기간·기준일 저장"
        elif action == "request":
            identifier = values.get("id") or self._next(state["requests"], "IRL")
            row = dict(id=identifier, title=_text(values.get("title"), "요청 자료", 500, True),
                       area=_choice(values.get("area"), AREAS, "업무 영역"), owner=_text(values.get("owner"), "담당자", 80, True),
                       due=_date(values.get("due"), "요청 기한", True), status=_choice(values.get("status"), REQUEST_STATES, "수령 상태"),
                       source_id=_text(values.get("source_id"), "원천 자료", 120), version=None,
                       followup=_text(values.get("followup"), "보완 사유"), workpaper=_text(values.get("workpaper"), "연결 조서", 80))
            if row["source_id"] and row["source_id"] not in source_ids:
                raise FinanceError("현재 프로젝트의 자료를 연결하세요.")
            if row["status"] == "수령" and not row["source_id"]:
                raise FinanceError("수령 상태에는 원천 자료 연결이 필요합니다.")
            if row["status"] == "보완 요청" and not row["followup"]:
                raise FinanceError("보완 요청의 사유를 입력하세요.")
            if row["source_id"]:
                row["version"] = pack["documents"].get(row["source_id"], {}).get("version", 1)
            self._upsert(state["requests"], row, values.get("id"))
            detail = identifier
        elif action == "adjustment":
            identifier = values.get("id") or self._next(state["adjustments"], "ADJ")
            ref = dict(document=values.get("source_id"), row=_source_row(values.get("source_row")), column=values.get("source_column"))
            resolved = resolve_ref(pack, ref)
            if not resolved:
                raise FinanceError("유효한 원천 파일·행(머리글은 1행)·열 이름을 지정하세요.")
            decimal(resolved['value'], optional=False)
            row = dict(id=identifier, area=_choice(values.get("area"), ("QoE", "NWC", "Net debt"), "조정 영역"),
                       name=_text(values.get("name"), "조정 설명", 300, True), amount=serial(decimal(values.get("amount"), optional=False)),
                       period=_period(values.get("period")), economic_key=_text(values.get("economic_key"), "경제적 항목 키", 100, True),
                       source=ref, management=_text(values.get("management"), "경영진 설명"),
                       judgment=_text(values.get("judgment"), "실사팀 판단", 2000, True),
                       recurring=_choice(values.get("recurring"), ("반복", "비반복", "추가 확인"), "반복성"),
                       cash=_choice(values.get("cash"), ("현금", "비현금", "추가 확인"), "현금성"),
                       decision=_choice(values.get("decision"), ADJUSTMENT_DECISIONS, "분석 반영"),
                       agreed=_choice(values.get("agreed"), ("미합의", "경영진 동의", "경영진 이견"), "경영진 합의"))
            dates = {r["period"] for r in pack["data"]["monthly"]}
            if row["period"] not in dates:
                raise FinanceError("조정 월에 해당하는 관리재무 자료가 필요합니다.")
            for existing in state["adjustments"]:
                if existing["id"] == identifier or existing["decision"] != "분석 반영" or row["decision"] != "분석 반영":
                    continue
                if (existing["economic_key"] == row["economic_key"] or existing['source'] == row['source']) and existing["period"] == row["period"]:
                    if existing["area"] == row["area"]:
                        raise FinanceError("동일 경제적 항목을 같은 영역·월에 중복 반영할 수 없습니다.")
                    if {existing["area"], row["area"]} == {"NWC", "Net debt"}:
                        raise FinanceError("같은 경제적 항목을 NWC와 순차입금에 중복 반영할 수 없습니다.")
            if row["area"] == "Net debt" and row["decision"] == "분석 반영" and row["economic_key"] in {"ar", "inventory", "other_assets", "ap", "other_liabilities", "cash", "borrowings", "lease_liability"}:
                raise FinanceError("기준 NWC·순차입금에 포함된 계정 전체를 debt-like에 다시 반영할 수 없습니다. 별도 항목과 제외 근거를 확인하세요.")
            if (row['area'] == 'Net debt' and row['decision'] == '분석 반영'
                    and pack['documents'][ref['document']]['kind'] == 'monthly'
                    and ref['column'] in {'ar', 'inventory', 'other_assets', 'ap', 'other_liabilities', 'cash', 'borrowings', 'lease_liability'}):
                raise FinanceError('기준 NWC·순차입금에 반영된 잔액을 같은 원천 셀에서 다시 debt-like로 반영할 수 없습니다.')
            self._upsert(state["adjustments"], row, values.get("id"))
            detail = identifier
        elif action == "issue":
            identifier = values.get("id") or self._next(state["issues"], "ISS")
            row = dict(id=identifier, title=_text(values.get("title"), "발견사항", 500, True),
                       area=_choice(values.get("area"), AREAS, "업무 영역"), impact=serial(decimal(values.get("impact"))),
                       priority=_choice(values.get("priority"), ("높음", "보통", "낮음"), "중요도"),
                       status=_choice(values.get("status"), ISSUE_STATES, "쟁점 상태"),
                       request_id=values.get("request_id") or "", adjustment_id=values.get("adjustment_id") or "",
                       management=_text(values.get("management"), "경영진 답변"), conclusion=_text(values.get("conclusion"), "실사팀 결론"))
            for field, collection in (("request_id", "requests"), ("adjustment_id", "adjustments")):
                if row[field] and row[field] not in {r["id"] for r in state[collection]}:
                    raise FinanceError("현재 프로젝트의 요청·조정사항을 선택하세요.")
            if row["status"] in {"해결", "범위 제한", "판단 작성"} and not row["conclusion"]:
                raise FinanceError("해결·범위 제한·판단 작성에는 실사팀 결론이 필요합니다.")
            if row["status"] == "경영진 답변" and not row["management"]:
                raise FinanceError("수령한 경영진 답변을 기록하세요.")
            self._upsert(state["issues"], row, values.get("id"))
            detail = identifier
        elif action == "reconciliation":
            identifier = values.get("id")
            all_rows = []
            for year in sorted({r["period"][:4] for r in pack["data"]["monthly"]}):
                all_rows.extend(calculations(state, year)["reconciliations"])
            if identifier not in {r["id"] for r in all_rows}:
                raise FinanceError("대사할 계정·연도를 선택하세요.")
            ref = dict(document=values.get("source_id"), row=_source_row(values.get("source_row")) if values.get('source_row') not in (None, '') else 0, column=values.get("source_column"))
            adjustment_tb = decimal(values.get("adjustment_tb") or "0", optional=False)
            adjustment_fs = decimal(values.get("adjustment_fs") or "0", optional=False)
            explanation = _text(values.get("explanation"), "대사 차이 설명", 2000, True)
            if (adjustment_tb or adjustment_fs) and not resolve_ref(pack, ref):
                raise FinanceError("대사 조정에는 유효한 파일·행·열 근거가 필요합니다.")
            state["reconciliations"][identifier] = dict(adjustment_tb=serial(adjustment_tb), adjustment_fs=serial(adjustment_fs), explanation=explanation,
                                                        source=ref if resolve_ref(pack, ref) else None)
            detail = identifier
        elif action == 'mapping':
            code = _text(values.get('account_code'), '계정 코드', 80, True)
            if code not in {r['account_code'] for r in pack['data']['gl']}:
                raise FinanceError('총계정원장에 있는 계정 코드를 입력하세요.')
            row = dict(account_code=code, metric=_choice(values.get('metric'), ('revenue', 'cogs', 'opex', 'da'), '매핑 계정'),
                       multiplier=_choice(str(values.get('multiplier')), ('1', '-1'), '차대변 부호'))
            state['mapping'] = [r for r in state['mapping'] if r['account_code'] != code] + [row]
            state['reconciliations'] = {}
            detail = code + ' 계정 매핑 저장'
        elif action == "transaction":
            state["transaction"] = dict(ev=serial(decimal(values.get("ev"))),
                peg_method=_choice(values.get("peg_method"), ("3", "6", "12", "manual"), "Peg 방식"),
                peg_manual=serial(decimal(values.get("peg_manual"))),
                mechanism=_choice(values.get("mechanism"), ("Completion accounts", "Locked box"), "가격 조정 방식"),
                note=_text(values.get("note"), "가격·계약 시사점"))
            if state["transaction"]["peg_method"] == "manual" and state["transaction"]["peg_manual"] is None:
                raise FinanceError("수동 peg의 금액을 입력하세요.")
            detail = "가격 시나리오 저장"
        elif action == "dataset":
            kind = values.get("kind")
            rows = parse_csv(kind, values.get("text"))
            filename = _text(values.get("filename"), "자료 이름", 100, True)
            if any(char in filename for char in ("/", "\\", ":")):
                raise FinanceError("자료 이름에 경로를 사용할 수 없습니다.")
            old_doc = next((doc for doc in pack["documents"].values() if doc["kind"] == kind), None)
            version = (old_doc["version"] if old_doc else 0) + 1
            normalized = csv_text(rows, DATASETS[kind][1])
            state["datasets"][kind] = dict(rows=rows, filename=filename, version=version,
                                           sha256=hashlib.sha256(normalized.encode()).hexdigest())
            # Replaced sources must not inherit either adjustment adoption or
            # historical reconciliation conclusions from another source version.
            if old_doc:
                for a in state["adjustments"]:
                    if a["source"]["document"] == old_doc["id"]:
                        a["decision"] = "검토 후보"
                for r in state["requests"]:
                    if r["source_id"] == old_doc["id"]:
                        r.update(source_id=f"entered_{kind}_v{version}", version=version, status="보완 요청", followup="원천 버전 교체에 따른 재검토 필요")
            state["reconciliations"] = {}
            detail = f"{kind} 원천 v{version}, {len(rows)}행 입력"
        elif action == "prepare":
            state["review"]["preparer"] = _text(values.get("preparer"), "작성자", 80, True)
            state["review"]["prepared_hash"] = content_hash(state)
            state["review"]["approved_hash"] = None
            detail = "작성 제출"
        elif action == "approve":
            reviewer = _text(values.get("reviewer"), "검토자", 80, True)
            if state["review"]["prepared_hash"] != before:
                raise FinanceError("현재 버전을 작성 제출한 뒤 검토하세요.")
            if reviewer.casefold() == state["review"]["preparer"].casefold():
                raise FinanceError("작성자와 다른 검토자 이름을 입력하세요. 이름은 사용자가 직접 기재하는 기록입니다.")
            blockers = review_blockers(state)
            if blockers:
                raise FinanceError("검토 기록 확정 전 해결 필요: " + " · ".join(blockers))
            state["review"].update(reviewer=reviewer, approved_hash=before)
            detail = "검토 기록 확정 (인증되지 않은 자기기입 이름)"
        elif action == "comment":
            state["review"]["comments"].append(dict(id=self._next(state["review"]["comments"], "RC"),
                author=_text(values.get("author"), "의견 작성자", 80, True),
                workpaper=_text(values.get("workpaper"), "연결 조서", 100, True),
                note=_text(values.get("note"), "검토 의견", 2000, True), status="미해결", response=""))
            state["review"]["approved_hash"] = None
            detail = "검토 의견 추가"
        elif action == "resolve_comment":
            row = next((r for r in state["review"]["comments"] if r["id"] == values.get("id")), None)
            if not row:
                raise FinanceError("검토 의견을 선택하세요.")
            row.update(response=_text(values.get("response"), "해소 근거", 2000, True), status="해결")
            state['review']['approved_hash'] = None
            detail = row["id"]
        else:
            raise FinanceError("지원하지 않는 재무 조서 작업입니다.")
        after = content_hash(state)
        if after != before:
            state["review"]["approved_hash"] = None
            state["review"]["prepared_hash"] = None
        state["revision"] += 1
        def record(snapshot):
            if action in {'scope', 'transaction'}:
                return snapshot[action]
            collection = {'adjustment': 'adjustments', 'request': 'requests', 'issue': 'issues'}.get(action)
            if collection:
                return next((r for r in snapshot[collection] if r['id'] == detail), {})
            if action == 'reconciliation':
                return snapshot['reconciliations'].get(detail, {})
            if action == 'mapping':
                return next((r for r in snapshot['mapping'] if r['account_code'] == values.get('account_code')), {})
            return {}
        old_record, new_record = record(original_state), record(state)
        changes = {k: dict(before=old_record.get(k), after=new_record.get(k)) for k in set(old_record) | set(new_record)
                   if old_record.get(k) != new_record.get(k)}
        state["history"].append(dict(revision=state["revision"], action=action, detail=detail, before=before, after=after,
                                     changes=json.dumps(serial(changes), ensure_ascii=False, sort_keys=True) if changes else '',
                                     timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        if len(state["history"]) > 200:
            raise FinanceError("조서 변경 이력 200건 한도입니다. 데이터북을 저장한 뒤 새 조서를 시작하세요.")
        return state

    @staticmethod
    def _next(rows, prefix):
        return f"{prefix}-{max([int(r['id'].split('-')[-1]) for r in rows] or [0]) + 1:03}"

    @staticmethod
    def _upsert(rows, row, original_id):
        if original_id:
            existing = next((i for i, r in enumerate(rows) if r["id"] == original_id), None)
            if existing is None:
                raise FinanceError("현재 프로젝트의 기록을 선택하세요.")
            rows[existing] = row
        else:
            if len(rows) >= 100:
                raise FinanceError("등록부는 100건까지 저장할 수 있습니다.")
            rows.append(row)


def report_markdown(state, period=None):
    c = calculations(state, period)
    s = state["scope"]
    def fmt(value):
        return "미제공 / 미정량" if value is None else f"{value:,.2f}"
    lines = [f"# {s['entity']} · FDD 검토 초안", "", f"상태: {review_status(state)} | 조서 버전 {state['revision']}",
             f"기간: {', '.join(c['periods']) or '미제공'} | 기준일: {s['as_of']} | {s['currency']} {s['unit']}",
             f"실사 관점: {s['side']} | 거래: {s['transaction_type']} | 회계기준: {s['gaap']}",
             f"대상 범위: {s['business_scope']}", f"제외·제한: {s['exclusions']}", "",
             "## 재무 분석", "", "| 항목 | 금액 |", "|---|---:|"]
    for label, value in [("매출", c["revenue"]), ("보고 EBITDA", c["reported_ebitda"]), ("분석 반영 조정 EBITDA", c["adjusted_ebitda"]),
                         ("기말 조정 NWC", c["adjusted_nwc"]), ("순차입금", c["net_debt"]), ("보고 영업현금흐름", c["cash"]["operating_cash"]),
                         ("FCF (보고 OCF − 유지·성장 CAPEX)", c["fcf"]), ("EV 입력 시나리오", c["ev"]), ("Equity 입력 시나리오", c["equity"])]:
        lines.append(f"| {label} | {fmt(value)} |")
    lines += ["", "조정 EBITDA는 공식 검토 확정·경영진 합의와 별개의 분석 반영 금액입니다. EV는 입력 시나리오이며 EBITDA 조정을 자동 가격배수로 환산하지 않습니다.",
              f"NWC peg: {state['transaction']['peg_method']} | 가격 조정 방식: {state['transaction']['mechanism']}", "", "## 조정사항", ""]
    for a in state["adjustments"]:
        ref = resolve_ref(c["pack"], a["source"])
        lines += [f"### {a['id']} · {a['area']} · {a['name']}",
                  f"{a['period']} | {fmt(decimal(a['amount']))} | {a['decision']} | {a['agreed']}",
                  f"경영진: {a['management']}", f"실사팀: {a['judgment']}",
                  f"원천: {ref['filename']} v{ref['version']} · {ref['row']}행 / {ref['column']} · SHA256 {ref['sha256']}" if ref else "원천 버전 불일치 · 재검토 필요", ""]
    lines += ["## 발견사항·경영진 Q&A", ""]
    for issue in state["issues"]:
        lines += [f"- {issue['id']} [{issue['priority']} / {issue['status']}] {issue['title']} · 영향 {fmt(decimal(issue['impact']))}",
                  f"  - 경영진: {issue['management']}", f"  - 실사팀: {issue['conclusion']} | 자료 요청 {issue['request_id']} | 조정 {issue['adjustment_id']}"]
    lines += ["", "## 미해결 검토 조건", *[f"- {b}" for b in review_blockers(state)], "", "## 작성·검토 기록",
              f"작성자: {state['review']['preparer'] or '미입력'} | 검토자: {state['review']['reviewer'] or '미입력'}",
              "이름은 자기기입 기록으로 로그인·권한·독립성을 인증하지 않습니다. 회계법인 서명 또는 감사의견이 아닙니다.",
              "", "## 데이터 분류·계산 정의",
              "합성 재무팩 또는 사용자가 직접 입력한 자료입니다. 원문 질문·증빙 엔진에서 숫자를 추출하지 않습니다.",
              "EBITDA = 매출 − 원가 − 영업비용(D&A 제외). NWC = 채권 + 재고 + 기타 영업자산 − 채무 − 기타 영업부채.",
              "순차입금 = 차입금 + 리스부채 − 사용가능 현금 + 분석 반영 debt-like. 제한성 현금은 현금 차감에서 제외.",
              "가격 조정 계산과 정의는 개별 거래 계약·실사 범위에 맞춰 검토해야 합니다.",
              f"동일 내용 해시: {content_hash(state)}", ""]
    return "\n".join(lines)


def export_tables(state, period=None):
    c = calculations(state, period)
    tables = {"범위": [{"항목": k, "값": v} for k, v in state["scope"].items()],
              "월별재무": c["selected"], "대사": serial(c["reconciliations"]), "계정매핑": state['mapping'],
              "조정사항": [{**a, "source": json.dumps(a["source"], ensure_ascii=False)} for a in state["adjustments"]],
              "NWC": [{"period": r["period"], **{k: r.get(k) for k in ("ar", "inventory", "other_assets", "ap", "other_liabilities")},
                        "nwc": serial(nwc(r))} for r in c["selected"]],
              "거래영향": [dict(reported_ebitda=serial(c["reported_ebitda"]), adjusted_ebitda=serial(c["adjusted_ebitda"]),
                              reported_nwc=serial(c["reported_nwc"]), adjusted_nwc=serial(c["adjusted_nwc"]), peg=serial(c["peg"]),
                              net_debt=serial(c["net_debt"]), ev=serial(c["ev"]), equity=serial(c["equity"]),
                              mechanism=state["transaction"]["mechanism"], currency=state["scope"]["currency"], unit=state["scope"]["unit"])],
              "현금흐름": [{**serial(c["cash"]), "opening_nwc": serial(c["opening_nwc"]), "closing_nwc": serial(c["reported_nwc"]),
                            "delta_nwc": serial(c["delta_nwc"]), "expected_ocf": serial(c["cash_expected"]), "residual": serial(c["cash_residual"]), "fcf": serial(c["fcf"])}],
              "연령분석": c["aging"], "부문매출": c["segments"], "전망": c["budgets"], "자료요청": state["requests"], "쟁점QA": state["issues"],
              "검토의견": state["review"]["comments"], "변경이력": state["history"],
              "원천목록": [{k: v for k, v in d.items() if k not in {"text", "columns"}} for d in c["pack"]["documents"].values()],
              "산출물정보": [dict(revision=state["revision"], content_hash=content_hash(state), status=review_status(state),
                                preparer=state["review"]["preparer"], reviewer=state["review"]["reviewer"],
                                limitation=state["scope"]["exclusions"], source_classification="synthetic / user_entered", period=c["period"])]}
    return tables


def _safe(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and (value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        # Preserve numeric negative values; protect untrusted prose from formulas.
        try:
            decimal(value, optional=False)
        except FinanceError:
            return "'" + value
    return value


def databook_bytes(state, period=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in export_tables(state, period).items():
        sheet = workbook.create_sheet(name)
        fields = list(dict.fromkeys(k for row in rows for k in row))
        if not fields:
            sheet.append(["기록 없음 / 미제공"])
            continue
        sheet.append(fields)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24437A")
        for row in rows:
            amounts = {key for _, columns in DATASETS.values() for key in columns} - {'period','year','metric','segment','id','account','description','bucket','assumption','account_code','account_name'}
            amounts |= {'adjustment_tb','adjustment_fs','difference_tb','difference_fs','residual_tb','residual_fs','residual_gl','nwc','reported_ebitda','adjusted_ebitda','reported_nwc','adjusted_nwc','peg','net_debt','ev','equity','opening_nwc','closing_nwc','delta_nwc','expected_ocf','residual','fcf','impact'}
            if name == '대사':
                amounts |= {'management','trial','gl','statutory'}
            if name == '조정사항':
                amounts.discard('cash')  # Cash/non-cash classification, not a balance.
            sheet.append([(None if row.get(k) in (None, '') else D(str(row[k]))) if k in amounts else _safe(row.get(k)) for k in fields])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in range(1, len(fields) + 1):
            sheet.column_dimensions[get_column_letter(column)].width = min(48, max(18, len(str(fields[column - 1])) + 3))
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                # Force all string inputs to text, including those beginning '='.
                if isinstance(cell.value, str):
                    cell.data_type = "s"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def source_bundle_bytes(state):
    pack = pack_for(state)
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        # Names are generated by the service; user input cannot choose ZIP paths.
        for identifier, source in pack["documents"].items():
            archive.writestr(f"sources/{identifier}.csv", source["text"])
        archive.writestr("source_manifest.json", json.dumps([{k: v for k, v in d.items() if k != "text"} for d in pack["documents"].values()], ensure_ascii=False, indent=2))
        archive.writestr("README.txt", "합성 또는 사용자 입력 재무 자료. 기존 원문 증빙팩과 분리. CSV는 원천 재현용이며 Excel에서 외부 콘텐츠를 실행하지 마세요.")
    return stream.getvalue()
