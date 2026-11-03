# Dash UI UX Design System

Contract 1.0.0 · 디자인 방향: 문서·주장·근거를 동시에 탐색하는 독립적인 분석 작업대.

## 벤치마크의 적용 범위

Hebbia 공식 Matrix 페이지의 문서와 분석 열을 함께 다루는 구조, 공식 제품 업데이트의 source preview를 참고한다. 이것은 공개 기능 확인이며 비공개 구현이나 성능을 검증한 것이 아니다. 차용하는 원칙은 문서 중심 탐색, 분석 결과에서 원문으로 바로 이동, 작업 맥락을 유지하는 검토다. Orion 고유의 score 설명·승인 상태·before/after가 화면의 중심이다. Hebbia 로고·브랜드·아이콘·카피·스크린샷·정확한 레이아웃을 복제하지 않는다. 출처: [S05–S06](11_DECISION_LOG_AND_SOURCES.md).

## 화면과 레이아웃

MVP는 하나의 workspace와 중심 탭 3개(Matrix / DD 질문 / 변경 비교)로 구현한다. Deal overview는 왼쪽 요약과 문서 목록으로 통합한다. Evaluation은 개발자용 CLI 보고서 링크로 제공하고 별도 페이지는 optional이다.

| 영역 | 1440×900 | 내용 |
|---|---|---|
| Global header | 높이 56, 좌우 padding 20 | 제품명, 모드 배지, Deal, run 상태, export |
| Left navigation | 너비 208, min 184 | Deal 선택, 문서, 파싱 상태, 이벤트 목록 |
| Central workspace | 나머지 약 840, min 600 | Top-3 요약, 탭·필터, evidence grid, 선택 row 상세 |
| Right inspector | 너비 360, min 320 | 출처 위치, 원문 강조, verification, review action |
| Gutters / footer | gap 12, 하단 28 | Snapshot/revision, pending update, 상태 안내 |

좌/중/우 각각 독립 vertical scroll을 가지되 중첩 scroll은 각 pane 하나로 제한한다. header/toolbar/review actions는 sticky다. 화면 전체에 대형 빈 hero를 두지 않는다. Top-3는 중앙 상단의 3행 목록으로 140px 이내에 표시하여 Matrix와 함께 보인다. Grid의 넓은 정보를 숨기기 위해 작은 글씨를 쓰지 않는다. 컬럼 chooser로 optional열을 숨기고 중앙에만 horizontal scroll을 허용한다.

| 너비 | 반응형 규칙 |
|---|---|
| ≥1360 | 세 pane 고정. 1440×900 reference |
| 1100–1359 | left 184, inspector 320, central min 560; 보조 열 기본 숨김 |
| 900–1099 | left는 버튼으로 여는 drawer; central + inspector 2-pane |
| <900 또는 200% 확대 | 한 번에 central 또는 source/review 탭; 기능 삭제 없이 돌아가기/선택 유지 |

데스크톱 1280×720도 핵심 목표다. 좁은 화면에서 source pane을 읽을 수 없는 폭으로 압축하지 않는다. 키보드와 스크린리더의 DOM 순서는 탐색→matrix→source→review다.

## 토큰

| 용도 | 값 |
|---|---|
| Canvas / panel | #F3F5F8 / #FFFFFF |
| Text / secondary | #172B3A / #475569 |
| Accent / selected | #145E63 / #E5F3F1 |
| Border / focus | #CBD5E1 / #1D4ED8 3px |
| Supported / Partial | #166534 on #DCFCE7 / #854D0E on #FEF3C7 |
| Missing / Contradicted | #475569 on #F1F5F9 / #991B1B on #FEE2E2 |
| Type | system UI, Segoe UI, Noto Sans KR fallback; 본문15px, 보조14px, 제목22px |
| Density | grid row44px, header42px, control36px 이상, touch target44px 권장 |
| Spacing | 4/8/12/16/24px; radius6px; 강한 shadow 대신 border |

기본 글자 대비 4.5:1, 큰 글자 3:1 이상을 실제 도구로 검증한다. 색상만으로 상태를 표시하지 않고 텍스트와 아이콘을 같이 쓴다. 이 문서의 색상 지정은 접근성 테스트 통과 보고가 아니다. 애니메이션은 선택 행의 짧은 강조만; reduced-motion을 존중한다.

## Evidence Matrix 컬럼 계약

행은 claim 단위다. evidence가 여러 개이면 `근거 3개` 버튼으로 inspector 안 목록을 펼친다. Enterprise row grouping/master-detail 없이 기본 grid와 외부 detail pane으로 구현한다.

| field | 제목 | width/min | 기본 | 선택 동작 |
|---|---|---:|---|---|
| statement | 주장 | 240/220 | 표시·좌 pin | Claim inspector |
| support_status | 증빙 충족 | 112/100 | 표시 | 조건 충족 목록 |
| source_refs | 원문 근거 | 150/130 | 표시 | SourceSpan 선택 |
| truth_status | 사실 확인 | 130/120 | 표시 | verification 설명 |
| review_status | 검토 | 112/100 | 표시 | 승인 영역 focus |
| thesis_title | 투자 가설 | 200/160 | 숨김 | Thesis 상세 |
| financial_driver | 재무 영향 | 140/120 | 숨김 | driver 설명 |
| linked_question_count | 후속 질문 | 100/90 | 숨김 | 관련 질문 필터 |

셀 텍스트는 최대 2줄·넘침 표시와 Enter로 전체 내용을 열 수 있게 한다. row ID는 claim.id, 선택 상태는 index가 아닌 ID로 유지한다. HTML injection 가능한 셀 renderer를 사용하지 않는다. sort/filter는 화면 조회용이며 엔진 priority 순서를 수정하지 않는다.

## DD Question Grid와 comparison

필수 열: 순위64px, 질문260px, 점수80px, 증빙부족88px, 중요도88px, 확보가능88px, 상태110px. 보조열: 요청문서240px, owner120px, 기간120px, financial_driver140px. 화면 정렬을 바꾸면 “화면 정렬 / 계산 순위”를 구별한다. 점수 클릭 시 `9×G + 8×M + 3×O`와 입력 근거를 보여준다. M/O 편집은 inspector의 폼에서 draft→reviewer approve 방식이며 grid 직접 inline 편집으로 즉시 반영하지 않는다.

변경 비교의 각 row는 `질문 / 전 순위 / 후 순위 / 전 점수 / 후 점수 / 상태 변화 / 이유 / 근거`다. null rank는 `— 해결됨` 또는 `— 이전 제외`로 표현한다. score delta와 rank delta를 구별하며 순위 승격만으로 초록색 score 증가를 그리지 않는다. changed-only 필터와 unchanged 이벤트 이유를 제공한다.

## Inspector와 review

상단에는 filename, 문서 버전, 출처 유형, 실제 locator를 배치한다. 다음으로 원문 prefix/강조 quote/suffix, `문서상 확인`과 `독립 사실 확인` 배지를 별도로 둔다. 아래에는 적용 criterion, 미충족 condition, 반증·중복·대체 관계, reliability rationale, analyst note가 온다. 하단 sticky controls는 `초안 수정`, `반려`, `검토 후 승인`이다.

승인 전에 무엇이 바뀔지 preview를 보여주되 이 preview는 현재 committed Snapshot이 아니다. “승인 시 적용” 라벨을 붙인다. 최종 export 승인은 별도 confirmation panel에서 포함 질문 수·Snapshot·미확인 사항을 보여준다. 사용자가 이미 승인한 개발 작업에 대한 대화형 재승인 절차가 아니라 **제품 사용자 workflow**의 일부다.

PDF는 기본적으로 정확한 추출 텍스트를 강조하고 원본 page 열기/download를 제공한다. native page highlight는 bbox가 검증된 경우만 표시한다. DOCX/PPTX는 구조 경로와 text/table cell을 제공한다. 실제 렌더링 없이 fake DOCX 페이지 미리보기를 만들지 않는다.

## Dash 컴포넌트와 callback 소유권

| ID | 컴포넌트 | 책임 |
|---|---|---|
| mode-banner / deal-selector | html.Div / dcc.Dropdown | mode와 고정 Deal 목록 |
| document-list / document-upload | html 목록 / dcc.Upload(Local만) | 서버 허용 정책과 함께 동작 |
| workspace-tabs | dcc.Tabs | matrix/questions/changes |
| evidence-grid / question-grid / change-grid | dag.AgGrid Community | stable getRowId, read-only data |
| top3-list / source-inspector | html.Div | score 이유·escaped source text |
| selection-store | dcc.Store(memory) | claim/span/question ID만 |
| demo-actions-store | dcc.Store(memory) | allowlisted action log만 |
| review-approve / review-reject | html.Button | 단일 action dispatcher로 연결 |
| export-download | dcc.Download | 서버에서 승인 확인 후 bytes 반환 |
| status-live-region | html.Div(role=status) | aria-live=polite, 오류는 적절한 alert |

action dispatcher 한 callback이 상태 변경을 소유한다. 선택·필터 callbacks는 저장 상태를 바꾸지 않는다. 동일 Output에 무분별한 allow_duplicate를 사용하지 않는다. Dash `ctx.triggered_id`로 명령을 구별하되 클라이언트 입력을 권한으로 쓰지 않는다. 긴 Local Live 작업은 단일 local worker queue와 run polling으로 처리하고 중복 click을 disabling만으로 막지 않고 idempotency를 적용한다. 실행 중 취소는 새 요청 중지이며 이미 청구된 API 사용료 환불을 뜻하지 않는다.

## 상태와 접근성

| 상태 | 화면 피드백 / 가능한 행동 |
|---|---|
| empty | 문서 없음, Local 등록 또는 Demo 예제 선택 |
| loading | 단계와 run ID, 기존 committed 결과 유지, stale 라벨 |
| needs_ocr / manual_review | 문제 문서와 이유, 데이터 없는 위치를 인용하지 않음 |
| invalid source | quote 불일치 위치 설명, 승인 버튼 비활성 및 서버 차단 |
| stale revision | 새 Snapshot 확인 후 다시 검토, 사용자 draft note 보존 |
| provider/budget error | 저장된 입력과 기존 결과 유지, 비용/재시도 가능 여부 표시 |
| no eligible questions | 모두 해결/미승인 여부 표시, 가짜 Top-3 생성 없음 |

Tab/Shift+Tab으로 주요 영역 이동, grid 내 arrow keys, Enter로 source, Escape로 drawer 닫기와 focus 복귀를 지원한다. focus가 없는 global 단축키는 MVP에서 도입하지 않는다. toolbar·icon button에 명시적 label, 상태의 aria-live, 모달 focus trap와 복귀를 검사한다.

참고 wireframe: [workspace](DESIGN/workspace-wireframe.svg), [update review](DESIGN/update-review-wireframe.svg). 그림은 정밀한 배치 가이드이며 동작하는 앱·사용성 검증 결과가 아니다.
