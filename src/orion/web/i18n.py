"""Korean presentation labels. Never translate or write authoritative records."""
from __future__ import annotations

LABELS = {
    "synthetic": "합성 자료", "read_only": "읽기 전용", "unknown": "알 수 없음",
    "pending": "대기", "parsed": "추출 완료", "needs_ocr": "문자 인식 필요",
    "needs_manual_review": "수동 검토 필요", "failed": "실패", "available": "검토 가능", "locked": "잠김",
    "company": "회사", "counterparty": "거래 상대방", "independent": "독립 출처", "analyst": "분석가",
    "validated": "검증 완료", "unverified": "미검증", "invalid": "유효하지 않음",
    "ocr_reviewed": "문자 인식 후 검토", "manual_checked": "수동 확인", "fixture": "예시 자료",
    "fixture_text_only": "텍스트 예시 전용", "file_verified": "파일 검증 완료",
    "draft": "초안", "approved": "승인", "rejected": "반려", "unapproved": "미승인",
    "preview_approval_required": "미리보기 · 승인 필요",
    "company_reported": "회사 보고", "counterparty_reported": "거래 상대방 보고",
    "analyst_assumption": "분석가 가정", "binary_hypothesis": "이진 가설",
    "independent_source": "독립 출처", "analyst_note": "분석가 의견",
    "missing": "증빙 없음", "partial": "부분 충족", "supported": "뒷받침됨", "contradicted": "상충",
    "not_checked": "미확인", "document_only": "문서 확인만 완료",
    "independently_verified": "독립 검증 완료", "disputed": "이견 있음", "independent_check": "독립 확인",
    "supports": "뒷받침", "refutes": "반박", "context": "참고 맥락", "active": "활성", "superseded": "대체됨",
    "duplicates": "중복", "contradicts": "상충", "supersedes": "대체",
    "objective_ratio": "객관적 비율", "analyst_rubric": "분석가 평가 기준",
    "derived_cost_time": "비용·시간 기반 산출", "analyst_estimate": "분석가 추정",
    "revenue_quality": "매출의 질", "ebitda": "EBITDA", "nwc": "순운전자본", "net_debt": "순차입금",
    "capex": "자본적 지출", "customer_concentration": "고객 집중도", "unit_economics": "단위 경제성",
    "open": "미해결", "awaiting_review": "검토 대기", "resolved": "해결", "duplicate": "중복",
    "approve": "승인", "reject": "반려", "edit": "수정", "reopen": "재개", "reviewer": "검토자", "system": "시스템",
    "seed_created": "초기 상태 생성", "update_staged": "업데이트 검토 대기", "update_approved": "업데이트 승인",
    "update_rejected": "업데이트 반려", "ranking_changed": "순위 변경", "ranking_unchanged": "순위 유지",
    "export_approved": "내보내기 승인", "exported": "내보내기 완료", "edit_applied": "수정 반영",
    "UNCHANGED": "변경 없음", "RESOLVED": "해결", "REOPENED": "재개", "RANK_CHANGED": "순위 변경",
    "SCORE_CHANGED": "점수 변경", "STATUS_CHANGED": "상태 변경",
    "UNRESOLVED_CONFLICT": "미해결 상충", "EVIDENCE_GAP": "증빙 공백",
    "MATERIALITY_DEFAULT": "중요도 기본값 사용", "OBTAINABILITY_DEFAULT": "확보 가능성 기본값 사용",
    "CRITERIA_SATISFIED": "요건 충족", "CONFLICT_REOPENED": "상충으로 재개",
    "EVIDENCE_GAP_REOPENED": "증빙 공백으로 재개", "RESIDUAL_PROMOTED": "잔여 질문 순위 상승",
    "RELATIVE_DEMOTED": "상대적 순위 하락", "RANKING_ELIGIBILITY_CHANGED": "순위 산정 대상 변경",
    "absent": "없음",
    "document": "문서", "claim": "주장", "question": "질문", "thesis": "투자 가설", "evidence": "증빙", "source": "원문",
    "support_status": "증빙 뒷받침", "truth_status": "사실 검증 상태", "review_status": "검토 상태",
    "verification_level": "검증 수준", "provenance": "출처 구분", "source_origin": "원문 출처",
    "kind": "유형", "page": "페이지", "block_index": "블록 번호", "slide": "슬라이드", "shape_id": "도형 ID",
    "paragraph_index": "문단 번호", "table_index": "표 번호", "table_cell": "표 셀", "row": "행", "column": "열",
    "part_uri": "문서 내부 경로", "heading_path": "제목 경로", "id": "ID", "deal_id": "투자 건 ID", "entity_version": "개체 버전",
    "document_id": "문서 ID", "document_version": "문서 버전", "filename": "파일명", "format": "형식",
    "asset_status": "자료 상태", "parse_status": "추출 상태", "created_at": "생성 시각", "updated_at": "수정 시각",
    "file_sha256": "파일 SHA-256", "text_sha256": "텍스트 SHA-256", "source_span_ids": "원문 구간 ID",
    "statement": "진술 원문", "claim_kind": "주장 유형", "thesis_id": "투자 가설 ID", "claim_id": "주장 ID",
    "stance": "증빙 입장", "lifecycle": "활성 상태", "criterion_keys": "요건 키", "independence_key": "독립성 키",
    "issue": "실사 질문", "request_text": "요청 자료", "requirements": "요건", "key": "키", "label": "이름",
    "materiality": "중요도", "obtainability": "확보 가능성", "score": "점수", "basis": "근거 유형",
    "rationale": "판단 근거", "financial_driver": "재무 영향 요인", "workflow_status": "처리 상태",
    "title": "제목", "counter_thesis": "반대 가설", "claim_ids": "주장 ID", "tags": "태그",
    "cost_usd": "비용 (USD)", "time_days": "소요 일수", "value": "값", "numerator": "분자", "denominator": "분모",
    "locator": "원문 위치", "locator_status": "원문 위치 검증", "extraction_method": "추출 방식",
    "quote": "인용 원문", "normalized_text": "정규화 원문", "start": "시작 위치", "end": "끝 위치",
    "normalization_version": "정규화 버전", "pdf": "PDF", "pptx": "PowerPoint", "docx": "Word",
    "canonical_key": "정규 키", "days": "일수", "denominator_minor": "분모 금액 (최소 통화 단위)",
    "duplicate_of": "중복 대상 ID", "exposure_minor": "노출 금액 (최소 통화 단위)",
    "external_cost_minor": "외부 비용 (최소 통화 단위)", "independent_check_reference": "독립 확인 참조",
    "min_reliability": "최소 신뢰도", "origin_key": "출처 키", "owner_label": "담당자",
    "parser_version": "파서 버전", "period_end": "기간 종료일", "period_start": "기간 시작일",
    "reliability_rationale": "신뢰도 판단 근거", "require_independent": "독립 출처 필요 여부",
    "required_criterion_keys": "필수 요건 키", "source_reliability": "출처 신뢰도", "subject_key": "대상 키",
    "docx_paragraph": "Word 문단", "docx_table_cell": "Word 표 셀",
    "positive": "긍정", "negative": "부정", "yes": "예", "no": "아니요",
    "Rejected branch — reset to continue": "반려된 분기 · 계속하려면 초기화하세요",
    "Synthetic analyst-reviewed state": "합성 자료 분석가 검토 상태",
    "Deterministic synthetic fixture-relative replay times; not real-world reviewer sign-off times.": "합성 예시 자료 기준의 결정론적 재현 시각이며, 실제 검토자의 승인 시각이 아닙니다.",
    "Synthetic preliminary screening; not a completed FDD report or investment recommendation.": "합성 자료 기반 예비 심사이며, 완료된 재무 실사 보고서나 투자 권고가 아닙니다.",
    "Source matching proves that a document reports a statement, not that the statement is independently true.": "원문 대조는 문서에 해당 진술이 있음을 확인하며, 진술 자체의 독립적 사실 검증을 뜻하지 않습니다.",
    "Deterministic authored demo. No live LLM calls or real B0–B3 benchmark results.": "작성된 자료를 결정론적으로 재현하는 데모입니다. 실시간 LLM 호출이나 실제 B0–B3 성능 비교 결과는 없습니다.",
    "Public Orion source ingestion remains pending; it is not offered as an ingested deal.": "공개 Orion 자료 수집은 대기 중이며, 수집이 완료된 투자 건으로 제공하지 않습니다.",
    "Session-bound demo branches are temporary. Reload/reset starts a new branch; no production VDR persistence is claimed.": "세션에 연결된 데모 분기는 임시 상태입니다. 새로고침·초기화하면 새 분기가 시작되며, 운영용 가상 데이터룸의 영속 저장을 제공하지 않습니다.",
    "This request was already applied; no change.": "이미 반영된 요청이므로 변경하지 않았습니다.",
    "This evidence event was already decided; no change.": "이미 결정된 증빙 이벤트이므로 변경하지 않았습니다.",
    "Demo restored to the initial state.": "데모를 초기 상태로 복원했습니다.",
    "Evidence approved. Ranking updated.": "증빙을 승인하여 순위를 갱신했습니다.",
    "Evidence approved. Top-3 unchanged; lower-priority questions changed.": "증빙을 승인했습니다. 상위 3개는 유지되며 하위 질문의 우선순위가 변경되었습니다.",
    "Evidence approved. Ranking unchanged; see the evidence and change explanation.": "증빙을 승인했습니다. 순위는 유지됩니다. 증빙과 변경 사유를 확인하세요.",
    "Evidence rejected. Authoritative ranking unchanged. Reset to review a new branch.": "증빙을 반려했습니다. 공식 순위는 유지됩니다. 새 분기를 검토하려면 초기화하세요.",
    "Allowlisted native source staged; current ranking unchanged.": "허용된 원문이 검토 대기 상태입니다. 현재 순위는 유지됩니다.",
    "Initial contract verification scenario": "초기 계약 검증 시나리오",
}

EVENT_LABELS = {
    "Contract evidence": "계약 증빙", "Commercial execution": "영업 실행",
    "Unit economics": "단위 경제성", "Ownership and reconciliation": "담당자 지정 및 대사",
    "Inventory count reconciliation": "재고 실사 대사", "Contract side letter and conflict": "계약 부속 합의 및 상충",
    "Source-backed evidence": "원문 기반 증빙",
}


def text(value):
    """Exact display lookup; unknown prose, identifiers and quotations survive."""
    value = str(value)
    if value in LABELS:
        return LABELS[value]
    # Stage labels are UI-generated, never evidence text.
    prefix, separator, label = value.partition(" · ")
    if separator and prefix.startswith("T") and prefix[1:].isdigit():
        return prefix + separator + EVENT_LABELS.get(label, label)
    return value


GRID_LOCALE = {
    "empty": "조건 선택", "ariaFilterMenuOpen": "필터 메뉴 열기", "ariaColumnMenuOpen": "열 메뉴 열기",
    "noRowsToShow": "표시할 행이 없습니다", "loadingOoo": "불러오는 중…", "searchOoo": "검색…",
    "filterOoo": "필터…", "equals": "같음", "notEqual": "같지 않음", "contains": "포함",
    "notContains": "포함하지 않음", "startsWith": "시작 문자", "endsWith": "끝 문자",
    "blank": "빈 값", "notBlank": "빈 값 아님", "lessThan": "미만", "greaterThan": "초과",
    "lessThanOrEqual": "이하", "greaterThanOrEqual": "이상", "inRange": "범위", "inRangeStart": "시작", "inRangeEnd": "끝",
    "andCondition": "그리고", "orCondition": "또는", "applyFilter": "적용", "resetFilter": "초기화",
    "clearFilter": "필터 지우기", "cancelFilter": "취소", "selectAll": "모두 선택", "selectAllSearchResults": "검색 결과 모두 선택",
    "sortAscending": "오름차순 정렬", "sortDescending": "내림차순 정렬", "sortUnSort": "정렬 해제",
    "ariaRowSelect": "행을 선택하려면 스페이스 키를 누르세요", "ariaRowDeselect": "행 선택을 해제하려면 스페이스 키를 누르세요",
    "ariaColumn": "열", "ariaColumnFilter": "열 필터", "ariaColumnFiltered": "필터 적용됨",
    "ariaFilterInput": "필터 입력", "ariaFilterColumnsInput": "열 필터 입력", "ariaLabelInput": "입력",
    "ariaLabelSelectField": "선택 필드", "ariaLabelColumnMenu": "열 메뉴", "ariaLabelFilterMenu": "필터 메뉴",
}

LABELS.update({'Aster executed paid contract': 'Aster의 서명된 유료 계약 확인', 'Birch executed paid contract': 'Birch의 서명된 유료 계약 확인', 'Aster acceptance and first cash': 'Aster의 검수 완료 및 최초 수금 확인', 'Aster full customer contribution': 'Aster 고객별 전체 공헌이익 확인', 'Independence of the two new customer groups': '신규 고객 두 집단의 독립성 확인', 'Birch acceptance and first cash': 'Birch의 검수 완료 및 최초 수금 확인', 'Corrected initial customer classification': '초기 고객 분류의 수정 근거 확인', 'Committed ARR reconciliation': '확정 계약 기준 ARR 대사', 'Deployable growth forecast': '실행 가능한 성장 전망 검증', 'Measured Birch contribution': 'Birch의 실제 공헌이익 검증', 'Recognized revenue to ledger': '인식 매출과 회계 원장 대사', 'Complete cost category coverage': '전체 원가 항목의 누락 여부 확인', 'Aster outstanding collection': 'Aster 미수금 회수 확인', 'Inventory physical existence and quantity reconciliation': '재고 실재성 및 수량 대사', 'Aged inventory recoverability': '장기 체화 재고의 회수 가능성 검토', 'Normalized recurring EBITDA': '정상화된 반복 EBITDA 검증', 'Working-capital and collection requirements': '운전자본 및 수금 요건 확인', 'Maintenance versus expansion CAPEX': '유지보수·성장 CAPEX 구분', 'Profitability to free-cash conversion': '이익의 잉여현금흐름 전환 검증', 'Customer concentration and minimum orders': '고객 집중도 및 최소 주문 확인', 'Funded practical manufacturing capacity': '자금이 확보된 실제 생산능력 검증', 'Product and channel revenue reconciliation': '제품·채널별 매출 대사', 'Roster and delivered hours support capacity': '인력 명부와 실제 투입 시간 검증', 'Labor cost and contract margin reconciliation': '인건비와 계약별 이익률 대사', 'Subsequent collection of key-client invoices': '주요 고객 청구액의 후속 수금 확인', 'Replacement equipment requirements': '장비 교체 필요성 확인', 'Key-client renewal and termination rights': '주요 고객 계약 갱신·해지 권리 검토'})
