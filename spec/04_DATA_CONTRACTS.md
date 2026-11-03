# Data Contracts

Contract 1.0.0 · 기계 판독 계약: [models.schema.json](SCHEMAS/models.schema.json), JSON Schema Draft 2020-12.

## 공통 규칙

Schema의 모든 `properties`는 해당 객체의 required 목록에 포함된다. 모르는 값은 nullable 필드에서만 JSON `null`로 표시한다. 빈 문자열·`NaN`·`Infinity`·타입 강제 변환을 허용하지 않는다. `additionalProperties=false`이며 Pydantic은 strict validation과 `extra='forbid'`를 사용한다. 상태 root의 계약 버전과 Snapshot의 scoring version은 각각 `1.0.0`이다.

ID는 소문자로 시작하는 3–64자 `[a-z][a-z0-9_-]{2,63}`다. 샘플 ID는 읽기 쉽도록 지었으며 실제 앱에서는 이 규칙의 opaque ID를 생성한다. 한 Deal 안의 모든 entity ID는 유형 간에도 유일하다. `entity_version`은 1부터 증가하며 과거 버전은 유지한다. `document_version`은 파일·추출 기준의 버전이며 entity metadata 수정만으로 바꾸지 않는다. 원문 bytes나 parser-normalization 결과가 바뀌면 새 document_version과 새 SourceSpan ID를 만든다.

날짜는 `YYYY-MM-DD`, 시각은 UTC ISO-8601 `Z`로 저장한다. UI에서는 브라우저의 시간대 표기를 함께 제공하되 정렬·hash에 영향을 주지 않는다. 금액은 USD 정수 cents, 비율은 0–1, 점수는 0–5 또는 0–100이다. 파일 locator의 page/slide는 1 기반, 모든 구조 index와 text offset은 0 기반이다.

## 객체 사전

| Entity | 핵심 필드와 의미 | 참조·버전 계약 |
|---|---|---|
| Deal | name, business_model, currency, synthetic, as_of, thesis_ids | MVP는 synthetic=true; 실제 비공개 Deal 지원 금지 |
| Document | format, document_version, asset_status, file_sha256, parse_status, parser_version, source_origin, origin_key | file_verified는 실제 bytes SHA-256 필수 |
| SourceSpan | document_id/version, locator, normalized_text, quote, start/end, text_sha256, locator_status, extraction_method | 단일 추출 단위; 원문·quote match의 최소 단위 |
| Thesis | title, counter_thesis, claim_ids, review_status | claim.thesis_id와 양방향 일치 |
| Claim | statement, subject_key, period_start/end, claim_kind, source_span_ids, required_criterion_keys, support_status, truth_status, review_status | 가설·회사 주장·분석가 가정을 구별 |
| Evidence | claim_id, source_span_ids, stance, criterion_keys, provenance, source_reliability, verification_level/reference, origin_key, review_status, lifecycle | 한 claim의 근거 atom. 복수 claim 적용은 별도 atom+같은 origin_key |
| EvidenceRelation | from/to_evidence_id, relation_type, scope_criterion_keys, review_status, rationale | directed duplicates/contradicts/supersedes. 자기 참조 금지 |
| DDQuestion | claim_id, canonical_key, issue, request_text, financial_driver, requirements, materiality, obtainability, review_status, workflow_status, duplicate_of, owner_label | 요구조건이 해결 기준, 질문 문장이 변해도 canonical_key로 중복 식별 |
| RankingSnapshot | state_revision, scoring_version, input_digest, trigger_event_id, rows, top3 | immutable; rows의 첫 3개와 top3 일치 |
| AnalystDecision | actor_id/role, target_type/id/version, selection_digest, action, reason, base_revision, decided_at | 대상 버전에 결합; 서버 ActorContext에서 생성 |
| AuditEvent | sequence, event_type, decision_id, revisions, idempotency_key, before/after_snapshot, reason, previous_hash/event_hash | append-only application interface; DB 소유자의 변조 방지 보장 아님 |
| AnalysisRun | cached/live, status, model_id, prompt_version, input/output_digest, tokens, reserved/actual_cost, pricing_version, timestamps, error_code | cached는 API 0, live 완료는 usage·model·pricing 기록 |

정확한 필드 목록·타입·enum은 [SCHEMAS/FIELD_REFERENCE.md](SCHEMAS/FIELD_REFERENCE.md)에 Schema에서 생성해 수록했다. 이 표를 코드보다 느슨하게 재해석하지 않는다.

## 독립 상태 축

| 축 | 저장 enum | 의미 |
|---|---|---|
| review_status | draft / approved / rejected | 사용 여부의 인간 판단 |
| support_status | missing / partial / supported / contradicted | 정의된 claim 조건의 증빙 충족 수준 |
| truth_status | not_checked / document_only / independently_verified / disputed | 현실 사실의 확인 수준 |
| workflow_status | open / awaiting_review / resolved / rejected / duplicate | 질문 업무 상태 |
| lifecycle | active / superseded | evidence의 현재 적용 가능성 |
| locator_status | validated / unverified / invalid | 추출 원문에서 quote·위치를 재현할 수 있는지 |

Claim support는 승인된 active evidence의 조건 충족으로 파생한다. 조건을 전혀 충족하지 못하면 missing, 일부면 partial, 모두면 supported, 조건 중 하나라도 해결되지 않은 승인 반증이 있으면 contradicted가 우선한다. 단순 context evidence는 존재하더라도 조건 충족 수 0이다. Document가 존재한다는 이유로 supported가 되지 않는다.

Truth는 위치 검증으로 승격하지 않는다. 출처 주장만 있으면 document_only; 충돌이면 disputed; 독립 확인은 모든 claim 조건에 대한 independent_check와 reviewer의 명시적 확인 결정이 있을 때만 independently_verified다. 분석가 가정은 not_checked이며 참고 사실로 승격하지 않는다. 자동 inference만으로 verified를 생성하지 않는다.

## 원문 locator와 snippet 검증

정규화 `text-v1`: UTF-8 decoding → Unicode NFC → CRLF/CR를 LF로 바꿈. 공백 병합·하이픈 제거·대소문자 변환을 하지 않는다. 인용 구간은 Python Unicode code point 기준 `[start,end)`이며 JavaScript UTF-16 offset으로 직접 해석하지 않는다. 브라우저는 서버가 나눈 prefix/quote/suffix를 escape하여 표시한다.

검사는 `(1) known document/version, (2) file hash/asset mode, (3) locator resolves exactly one unit, (4) hash(normalized_text), (5) 0≤start<end≤len(text), (6) text[start:end]==quote` 순서다. 같은 문구가 두 번 나오면 offset이 없거나 모호한 후보를 승인하지 않는다. 부분 일치/fuzzy match는 제안용일 뿐 validated 판정에 쓰지 않는다. quote가 실제 주장과 의미상 연결되는지는 analyst/평가자가 별도로 판단한다.

| 형식 | locator 계약 | fallback |
|---|---|---|
| PDF | page≥1, block_index≥0. parser가 페이지의 추출 단위를 고정 index로 제공 | scan은 needs_ocr, 추출 순서·표가 불명확하면 needs_manual_review. bbox 강조는 optional |
| PPTX | slide≥1, shape_id는 XML shape ID, paragraph_index, nullable table_cell(row,column) | notes·SmartArt·그룹 그림은 MVP 입력 제외. unsupported 정보를 표시 |
| DOCX 문단 | kind=docx_paragraph, part_uri=word/document.xml, block_index, paragraph_index, heading_path | body의 paragraph/table만 block count, sectPr 제외. 일반 문단의 paragraph_index=0 |
| DOCX 표 | kind=docx_table_cell, table_index, row,column,paragraph_index,heading_path | top-level 단순 표만. merged/nested table은 수동검토, fabricated page 없음 |

DOCX headers, footnotes, tracked changes, text boxes는 자동 extraction의 지원 범위를 넘어선다. 감지 시 누락을 기록하고 중요 정보이면 사용자가 단순 형식으로 제공해야 한다. 변환 PDF를 추가할 수 있으나 별도 Document이며 native DOCX locator를 가짜 page로 바꾸지 않는다.

현재 fixture의 `asset_status=fixture_text_only`, `extraction_method=fixture`는 raw extraction 텍스트의 계약 검사만 가능하다. 제품 source viewer에는 “계약 예시 텍스트, 원본 파일 미생성”을 표시해야 한다. Chunk 3에서 실제 합성 파일을 만들고 `file_verified`로 교체하기 전 인용 위치 정확도의 실측 표본으로 사용하지 않는다.

## Schema 밖의 필수 참조 검사

1. 모든 entity.deal_id는 root Deal과 같고, 모든 cross-reference는 같은 Deal의 유효 버전을 가리킨다. 존재하지 않는 claim/document/span/question 참조를 차단한다.
2. Thesis.claim_ids ↔ Claim.thesis_id 양방향 일치. Question과 Evidence의 criterion_keys는 해당 Claim.required_criterion_keys의 부분집합이다. Claim의 모든 required key는 최소 하나의 Question requirement에서 정의되어야 한다.
3. 같은 claim/key의 requirement 정책(min_reliability, require_independent)은 질문 간 동일해야 한다. 질문 하나에 duplicate key를 허용하지 않는다.
4. approved evidence의 모든 span은 validated이며 document는 parsed이다. fixture 예외는 Demo/계약 시험에서만 허용한다. 실제 Local Live에서 fixture provenance를 승인할 수 없다.
5. independent_check에는 독립 확인 reference가 있어야 한다. source_origin=independent만으로 충분하지 않다. rationale·기간·대상 범위를 사람이 검사한다.
6. supersedes 관계는 DAG, 범위 밖의 과거 evidence는 유지한다. MVP에서는 완전 대체만 lifecycle=superseded로 허용하고 부분 대체는 기존 evidence를 atom으로 분리한 뒤 적용한다. new superseder가 approved·validated여야 한다.
7. duplicates는 동일 claim·stance·scope에서만 승인 가능하다. canonical origin을 하나로 합쳐 중복 수를 세지 않는다. 서로 반대인 주장은 duplicates로 숨기지 않는다.
8. snapshot rows의 question은 유일하고 rank는 1..N, top3는 rows[:3], head_snapshot은 최신 committed revision이다. derived statuses와 stored status가 다르면 stale state로 차단한다.
9. Audit sequence는 연속, previous_hash는 앞 event_hash와 일치, revision은 역행하지 않는다. live run cost/token은 음수 불가, unknown actual cost는 null이다.
10. `objective_ratio`는 양수 denominator와 nonnegative exposure가 있어야 하고 M은 고정 bin 결과와 일치해야 한다. `derived_cost_time`은 days/cost 둘 다 필요하다. unknown 입력은 score=null로 통일한다.

## 전이와 승인

| 대상 | From → To | Guard / 부수효과 |
|---|---|---|
| 추출 초안 | draft → approved/rejected | reviewer가 정확한 version을 검토 |
| 초안 수정 | approved/rejected → 새 draft version | 기존 승인 보존, 새 승인 필요 |
| Update | validated staged → approved | reviewer, base_revision, integrity, idempotency 통과 |
| Update | staged → rejected | 이유와 audit만 추가, rank snapshot 불변 |
| Question | open → resolved | 모든 requirements 충족·반증 없음; commit에서 결정론 파생 |
| Question | resolved → open | 승인 반증, 충족 증빙의 적법한 대체/철회로 다시 gap 존재 |
| Question | open → duplicate/rejected | reviewer 결정·canonical reference·이유 |
| Export | draft → approved → exported | 현재 Snapshot+selection_digest에 결합 |

`awaiting_review`는 아직 질문 자체의 승인이 필요한 상태다. 기존 approved question에 evidence가 staging되었다고 awaiting_review로 바꾸지 않는다. 따라서 staging이 기존 Top-3를 제거하지 않는다. Reviewer가 질문/근거를 수정할 때에도 승인 commit 전까지 마지막 승인 상태를 유지한다.

StagedEvidenceUpdate는 생성 뒤 immutable이며 decision.target_version은 1이다. 수정은 새 event ID로 staging한다. snapshot_export decision의 `selection_digest`는 필수 SHA-256이며 `(snapshot_id, snapshot_input_digest, sorted included_question_ids, export_format, normalized_filters)`의 canonical JSON으로 계산한다. 다른 decision에서는 selection_digest=null이다. `format=all`은 csv/xlsx/markdown 세 형식을 뜻하는 고정 enum 값으로 service DTO에서 검사한다. export 경로는 사용자가 임의 지정하지 않는다.

## Hash와 serialization

`input_digest`는 `contract_version`, `scoring_version`, 그리고 Deal/Documents/SourceSpans/Theses/Claims/Evidence/Relations/Questions의 **현재 승인 평가에 사용한 record set**을 정렬한 canonical JSON의 SHA-256이다. entity collection은 `(id,entity_version)`로 정렬한다. 객체 키는 정렬, UTF-8, `ensure_ascii=False`, separators `(',',':')`, NaN 불허로 고정한다. entity 내부 list는 생성 시 canonical 순서를 유지하며 heading_path 같은 순서형 list를 임의 정렬하지 않는다. approval/clock/run/cost/snapshot/audit는 ranking input에서 제외한다. 저장된 Document/Evidence의 created_at은 immutable input metadata다.

`AuditEvent.event_hash`는 event_hash 필드를 제외한 event 전체의 같은 canonical JSON에서 계산한다. previous_hash가 hash chain을 연결한다. 암호학적 서명·공증은 아니다. 수치 비교는 Decimal의 raw 값으로 하고 표시 점수만 소수 둘째 자리 half-up한다.

## 호환성과 변경관리

필드 삭제·enum 의미 변경·새 required field는 major contract bump, optional nullable 필드 추가는 minor 후보이며 모든 example·validator·migration을 함께 수정한다. 점수 공식/기본값 변경은 scoring version을 올리고 기존 Snapshot을 재작성하지 않는다. 새로운 비교 Snapshot을 추가한다. Schema와 Markdown이 충돌하면 조용히 한쪽을 택하지 말고 결정 로그에 수정 내용을 남긴 뒤 둘 다 일치시킨다.
