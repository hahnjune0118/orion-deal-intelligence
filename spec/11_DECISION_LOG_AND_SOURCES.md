# Decision Log and Sources

Contract 1.0.0 · 기준일 2026-11-03 · 제공 자료를 프로젝트 의도의 1차 근거로 사용한다. 외부 조사는 패키지 기능·라이선스·호스팅·공개 UX·API 데이터 조건으로 제한했다.

## 제공 자료 확인

| Source | 제공 파일 | 확인 내용·위치 |
|---|---|---|
| U01 최우선 | `01_FINAL_DECISIONS.md` | 전문. Dash/AG Grid, 3개 합성 사례, human review, 두 모드, DCF 제외, 목표 미검증 |
| U02 둘째 | `(연한준)프로젝트_기획안.docx` | 전문. 2026-10-27. XML 문단 p6–13 목적·문제, p49 workflow, p52 grounding, p54–65 Bayesian/EIG, p68–69 기술, p71–82 평가 |
| U03 셋째 | `3. (연한준) 금융인공지능실무 과제 기획안 피드백 보완 (2차).docx` | 전문과 embedded image 2개. p9–36 법적 쟁점, p60 기존 범위, p70 이후 storyboard/UI |
| U04 넷째 | `2. (연한준)금융인공지능실무 과제 기획안 피드백 보완.docx` | 전문. p8·11·14 benchmark, p18–22 traceability/HITL/과거 단일상장사·DCF |
| U05 제작 지시 | `02_FIRST_PROMPT.md` | 전문. 파일 목록·산출물·검증·최종 응답 형식 |

문단 번호는 `word/document.xml`의 모든 `w:p`를 문서순서로 센 0-based inspection index다. Word 페이지 번호가 아니다. U03의 2개 그림도 직접 확인했다. 그림의 실제 기업명·수치·가치평가·브랜드는 새 합성 dataset에 사용하지 않았다. 원문 bytes의 해시는 [QA/source_inventory.json](QA/source_inventory.json)에 있다. 원본 4개와 제작 지시 파일 모두 존재했으며 빠진 자료는 없다. 비공개 2026-10-23 blueprint가 첨부된 것으로 가정하지 않았다.

## 충돌과 설계 결정

| ID | 충돌/모호성 | 채택 결정 | 근거/영향 |
|---|---|---|---|
| D01 | U02 p68 Streamlit vs U01 Dash | Plotly Dash + Dash AG Grid | U01 우선; Streamlit 의존성 제외 |
| D02 | U04 p21·U03 p60 단일 상장사/DCF | 가상 Northstar + Cedar + Lumen | U01; 내부·상장사 데이터 수집 불필요 |
| D03 | U02 p62 optional DCF | DCF adapter/자동수정 전부 MVP 제외 | U01 명시적 제외가 optional보다 우선 |
| D04 | U02 B3 Bayesian/EIG vs deterministic priority | B3는 evidence-adaptive deterministic re-ranking | U01; Bayesian는 독립 optional panel |
| D05 | 문서 존재 vs Verified 표기 | provenance/support/reliability/truth/review 분리 | U01/U02 p52; false verification 방지 |
| D06 | DOCX page 개념 | native structural locator | U01; 그림 속 page reference를 DOCX에 전용하지 않음 |
| D07 | “유료 계약”과 “수금”의 혼동 | commercial contract existence만 충족 | U01 시연 B/C; collection/acceptance 별도 요청 |
| D08 | SQLite를 public cloud에 그대로 배치할지 | local SQLite, public strictly stateless replay | U01의 persistence 해결 요구; 새로운 설계 선택 |
| D09 | 공개 read-only vs interactive | 합성 branch에서 reviewer 승인 시뮬레이션 | U01 중요 상호작용 요구와 isolation 동시 만족 |
| D10 | DMC 도입 여부 | MVP 제외, Dash html/dcc와 CSS 사용 | 유지보수 범위 축소; 기능상 필수 아님 |
| D11 | XLSX export가 Enterprise를 요구하는지 | 서버 openpyxl export | AG Grid Enterprise Excel 기능을 사용하지 않음 |
| D12 | 시간·비용과 Obtainability 중복 반영 | O에만 통합, 별도 penalty 없음 | 설명가능성·중복계산 방지; 설계 선택 |
| D13 | M/O 미확보 | 3/2 기본값과 provisional 배지 | 누락을0으로 숨기지 않음; 설계 가정 |
| D14 | 3개 자료가 독립 검증 gold인지 | author-proposed gold, 독립 review 미완료 | 성능 주장 금지; 평가 절차에 분리 |
| D15 | source JSON 예시가 실제 native 파일인지 | fixture_text_only·hash=null 명시 | 이번은 명세 단계; Chunk3에서 native파일 생성·검증 |
| D16 | 무료 hosting | Render 조건부 Demo 후보, Railway 유료대안 | 무료·SLA 보장 금지, 실제 deploy 미실행 |
| D17 | 법률 문서의 현행성 | 학술 source의 주장으로만 보존 | 공식 현행법 검증 없이 조항·적용 결론을 재확정하지 않음 |
| D18 | 반복사례/새 정보 효과 confound | B1-R rerun 대조군 추가 | 설계 선택; B3 우위 과장 방지 |
| D19 | live model/가격 미확정 | null config와 fail-closed gate | 지원 모델·가격을 지어내지 않음 |
| D20 | 대체 문서의 일부 범위 | atomic evidence로 분해 후 scoped supersession | 새 문서가 모든 과거 증거를 자동 덮어쓰지 않음 |

D08–D20 중 U01에 상세 수치가 없던 사항은 이 Handoff의 구현 설계 선택이며 사용자가 과거에 지시한 사실로 표현하지 않는다. 변경하려면 영향과 acceptance test를 함께 갱신한다.

## 외부 공식 확인 기록

각 항목의 설명은 필요한 기능만 요약한다. 외부 사이트의 예시 기업정보·이미지를 재배포하지 않는다. 2026-11-03 조회 당시 정보이며 배포 전에 가격·호환성·약관을 다시 확인한다.

| ID | 공식 출처 | 확인한 사실 | 미확인 범위 |
|---|---|---|---|
| S01 | [Dash AG Grid docs](https://dash.plotly.com/dash-ag-grid) | wrapper와 version별 upstream AG Grid 문서 대응을 안내 | 프로젝트 pin 조합의 runtime 성공은 별도 |
| S02 | [Dash 3 migration](https://dash.plotly.com/dash-3-0-migration) | app.run, React18.3.1 기본, AG Grid/DMC 최소 호환 목록 | DMC 도입 필요성을 뜻하지 않음 |
| S03 | [AG Grid pricing/license](https://www.ag-grid.com/license-pricing/) | Community는 MIT/free, Enterprise는 별도 license | Enterprise 구매·계약 미검토 |
| S04 | [Plotly Enterprise Grid guide](https://dash.plotly.com/dash-ag-grid/enterprise-ag-grid) | grouping/sidebar/master detail 등 Enterprise 기능 분리 | 본 제품은 해당 기능 미사용 |
| S05 | [Hebbia Matrix](https://www.hebbia.com/matrix) | 문서와 여러 분석 열을 다루는 공개 Matrix 표 구조 | 내부 구조·품질·성능 검증 아님 |
| S06 | [Hebbia Dec 2025 update](https://www.hebbia.com/blog/the-disclosure-december-2025) | underlying source를 보는 citation preview 공개 설명 | Orion의 3-pane 배치는 독립 설계 |
| S07a | [Render Free](https://render.com/docs/free) | idle spin-down·ephemeral disk·free hour·과금 제한 | 계정 승인·실제 app 배포 미실행 |
| S07b | [Render disks](https://render.com/docs/disks) | paid disk와 mount 내부 지속성 | SQLite 운영 적합성·복구 보장 아님 |
| S07c | [Render pricing](https://render.com/pricing) | 공식 가격 확인 경로 | 동적 페이지에서 정확한 paid SKU 수치를 확보하지 못함 |
| S08 | [Railway billing](https://docs.railway.com/pricing/understanding-your-bill) | Hobby $5 minimum·포함 사용량·초과 청구 방식 | 특정 app의 월 청구액 추정 아님 |
| S09 | [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) | endpoint·조직설정·저장 조건 구분 | 사용자의 실제 계정 retention 설정 미조회 |
| S10 | [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) | scan/OCR 필요와 읽기순서·좌표·메모리 한계 | 모든 PDF 표 추출 보장 아님 |
| S11 | [Dash 3.2.0 release](https://pypi.org/project/dash/3.2.0/) | 지정 release 존재·배포 메타데이터 | 전체 앱 호환·취약점 부재 아님 |
| S12 | [Dash AG Grid 32.3.2 release](https://pypi.org/project/dash-ag-grid/32.3.2/) | 지정 release 존재·배포 메타데이터 | 최신 major 사용을 요구하는 것은 아님 |

나머지 직접 의존성도 공식 PyPI JSON endpoint를 조회했으며 URL·버전·배포파일 SHA·license metadata를 `QA/dependency_metadata.json`에 보존했다. Publisher metadata 확인과 license 법률 자문은 다르다. 배포할 wheel의 LICENSE/NOTICE 보존을 Chunk1/5 Gate에 둔다.

## 확인·가정·미검증의 구별

- **확인**: 제공 5개 파일 실재/내용과 두 embedded 그림, 외부 공식 문서의 위 공개 기능, 직접 dependency release 존재. 계약 산술·Schema·예시는 QA 보고서의 실제 실행 결과에 한정한다.
- **설계 선택**: 점수 가중치와 bin, UI 토큰, 48+10시간 배분, 입력/비용 상한, stateless replay, snapshot hash 포맷.
- **미검증**: Windows 앱 실행, full dependency install/security scan, native parser coverage, browser accessibility, public hosting deploy, Live API integration, 모델 성능·gold 독립성·시간 절감.

후속 구현에서 공식 정보를 다시 조회하면 확인일과 영향 결정을 추가한다. 현재 source를 과거 주장에 맞춰 수정하지 않는다. 전체 제품 완료나 학술 목표 달성은 본 패키지의 결론이 아니다.
