# Chunk 4 웹 애플리케이션 구조

Chunk 4는 기존 Python 도메인 모델·점수·전이·원문 검증·합성 자료 위에 Dash 화면, 웹용 작업 조정 서비스와 보고서 내보내기를 연결합니다. 기존 점수 공식과 저장 계약을 화면 코드에서 다시 구현하지 않습니다.

## 계층과 책임

| 경로 | 책임 |
|---|---|
| `src/orion/app.py` | `python -m orion.app` 진입점, Dash/Flask 앱 구성과 로컬 실행 |
| `src/orion/web/layout.py` | 세 영역 작업대, 7개 탐색 영역, Community AG Grid와 Plotly 화면 표현 |
| `src/orion/web/callbacks.py` | 선택·탐색·승인·반려·다운로드의 입력을 서비스로 전달하고 안전한 결과를 표시 |
| `src/orion/services/web_workspace.py` | 허용 합성 사례 로드, 서명된 행동 이력 검증, 요청별 상태 재생, 원문·질문·가설·비교 DTO 구성 |
| `src/orion/services/export.py` | 승인된 상태·선택·형식 검증, 세션에 결합된 내보내기 승인, CSV/XLSX/Markdown/DOCX 생성 |
| `src/orion/domain/grounding.py` | 실제 source resolver, 원본 해시, locator와 quote 검증 |
| `src/orion/domain/scoring.py` | 기존 `P = 9G + 8M + 3O`의 권위 있는 계산 |
| `src/orion/domain/transitions.py` | 기존 승인 전이, 현재 Snapshot 일치 검사와 질문 변화 계산 |
| `src/orion/services/review.py`, `workspace.py` | 기존 서버 ActorContext와 SQLite를 사용하는 로컬 검토 서비스 계약 |
| `src/orion/synthetic/`, `native_dataset.py` | 실제 합성 자료와 단계별 이벤트, 원문 파서/index 연결 |
| `src/orion/quant/` | 명시된 가상 확률 가정의 Bayesian/EIG 계산 |

화면의 표·요약·차트는 서비스가 반환한 상태를 보여줍니다. 숫자 표시 형식과 표 정렬은 프레젠테이션의 책임이며, 승인 상태나 우선순위를 변경할 권한이 없습니다. Grid 행의 식별은 화면 위치가 아닌 안정된 entity ID를 사용합니다.

## 승인 요청의 흐름

1. 브라우저가 선택한 이벤트 ID, 승인/반려, 검토 이유와 예상 revision을 보냅니다.
2. 서비스가 서버가 만든 브라우저 세션과 서명된 행동 이력을 확인합니다.
3. 허용된 합성 자료에서 독립적인 상태를 재생하고 현재 Snapshot과 원문을 검증합니다.
4. 이벤트 순서, revision, 중복 요청과 서버 reviewer 권한을 검사합니다.
5. 승인 시 기존 `apply_approved_update()`를 호출합니다. 반려 시 결정·감사 이력만 추가하고 현재 순위는 보존합니다.
6. 새 행동 이력에 서버 서명을 붙여 돌려주고, 화면은 새 Snapshot과 전후 차이를 다시 조회합니다.

서버 actor는 서비스에서 정합니다. 브라우저가 보낸 actor, 점수, 문장 또는 원문 해시를 권위 있는 입력으로 받아들이지 않습니다. 단순한 이벤트 미리보기도 현재 승인된 상태를 변경하지 않습니다.

## 데모 상태와 저장 경계

브라우저 탭의 `dcc.Store(memory)`에는 서명된 행동 이력 토큰과 화면에 필요한 revision이 있습니다. 토큰은 Flask가 만든 브라우저 세션에 결합되며 다른 세션에서 재사용할 수 없습니다. 탭마다 진행 이력이 분리되고 새로고침과 `Reset demo`는 초기 진행으로 돌아갑니다.

서버는 원문 pack을 재사용할 수 있지만 방문자 모델과 행동 이력을 공유 mutable state로 보관하지 않습니다. 각 요청은 원본 모델의 복사본에서 재생됩니다. 기존 Demo 정책에 따라 방문자용 영속 SQLite를 열지 않습니다. 따라서 웹 데모는 `ReviewService`의 SQLite 인스턴스를 직접 사용하지 않고, 동일한 도메인 전이와 ActorContext 경계를 재사용합니다. 기존 SQLite 서비스와 그 테스트는 유지됩니다.

서명된 과거의 유효 토큰은 해당 시점의 합성 진행을 재현하는 분기입니다. 이를 다중 사용자 영속 데이터베이스의 최신 revision 잠금이나 실제 조직의 장기 감사 저장소로 표현하지 않습니다. 반려된 순차 이벤트 분기에서는 이후 이벤트로 진행하지 않으며 초기화 후 다른 결정을 시연합니다.

검토 결정과 감사 로그의 시각은 `event.created_at + 1분`으로 정해지는 합성 재생 시각입니다. 기존 데모의 fixture-relative 재생 방식을 따라 동일한 과거 토큰과 동일 명령의 재시도가 같은 결과를 재현하게 합니다. 이 시각을 실제 사용자의 클릭 시각이나 인증된 검토자의 법적 서명 시각으로 사용하지 않습니다. 내보내기 승인 receipt는 별도 승인 동작이며, 증빙 검토 이력의 재생 시각과 구별합니다.

## 원문과 단계별 공개

Northstar 심화 `nb`와 제조업 `mf`는 `chunk3_synthetic_evaluation`의 실제 source inventory·원문·초기 상태·update 파일을 사용합니다. Lumen `lm`은 기존 native runtime pack을 사용합니다. 화면의 공개 사례는 고정된 선택 목록이며 임의 경로나 사용자 파일을 받지 않습니다.

Source inspector는 검증된 원문에서 prefix/quote/suffix를 분리하여 텍스트로 렌더링합니다. 원문 문자열을 실행 가능한 HTML로 삽입하지 않습니다. PDF는 page/block, PPTX는 slide/shape/paragraph, DOCX는 문단 또는 표 구조를 표시합니다. 원본 파일의 시각적 좌표 강조는 구현 범위가 아닙니다.

`Download original source`는 현재 검증된 작업대의 문서 ID만 받습니다. `WebWorkspace.document_bytes()`가 native resolver에서 원본을 읽고 SHA-256을 대조한 뒤 `dcc.Download`로 반환합니다. 사용자가 임의 파일 경로를 지정하거나 아직 현재 상태에 포함되지 않은 미래 문서를 내려받을 수 없습니다.

검토 미리보기에서는 다음 허용 이벤트의 원문과 제안된 영향을 읽을 수 있습니다. 승인 전에는 해당 이벤트의 내용을 현재 승인된 분석 결과와 섞지 않습니다. 평가용 gold, 예상 정답, 미래 단계의 비공개 증빙을 질문 분석의 입력으로 사용하지 않습니다.

## 정량 분석의 범위

제품 순위는 계속 scoring 1.0.0의 `9G + 8M + 3O`입니다. 기존 Bayesian/EIG 함수는 명시된 가상 이진 시나리오의 prior, likelihood와 증빙을 계산합니다. EIG는 bits로 표시하고 우선순위 점수와 독립된 비교 지표로 다룹니다.

제조업 및 확률 가정이 없는 질문에는 숫자를 만들어 넣지 않습니다. 계산 불가 상태는 0이 아닌 미제공으로 표시합니다. 재무 driver의 연결은 정성적 영향 범위이며 DCF, 기업가치 또는 실증적 투자 성공확률 계산을 뜻하지 않습니다. authored fixture의 동작 재생은 실제 LLM의 B0–B3 성능 실험과 구별합니다.

## 내보내기 계약

사용자는 화면에서 형식과 현재 Snapshot을 검토하고 명시적으로 내보내기를 승인합니다. 체크박스의 새로운 승인 동작만 승인 receipt를 만들며, 그때 서버 상태가 실제 렌더링된 토큰·revision·Snapshot과 일치해야 합니다. 토큰 또는 형식 변화는 체크박스의 화면 초기화가 끝나기 전에도 기존 동의를 무효화합니다. 다운로드 버튼은 이미 생성된 승인을 검사하여 파일을 생성하며 최신 상태를 몰래 새로 승인하지 않습니다.

`ExportService`는 current state와 native grounding을 다시 검사하고, 서버 reviewer와 브라우저 세션에 결합된 승인 receipt를 생성합니다. 승인은 Snapshot ID/input digest, 현재 포함 질문 IDs, 형식, 전체 상태 digest에 결합됩니다. 상태·세션·형식이 달라지면 이전 승인을 사용할 수 없습니다.

CSV/XLSX 실사 목록은 같은 서버 데이터와 열 계약을 사용합니다. 증빙 CSV와 예비 검토 메모는 원문 참조, 검토 상태, 반증과 미해결 사항, 증빙 변경 이력과 내보내기 승인 정보를 포함합니다. 파일은 메모리에서 생성해 `dcc.Download`로 제공하며 사용자가 임의 서버 저장 경로를 지정하지 않습니다. 파일명은 Deal, 형식과 revision으로 정합니다.

지원 형식은 `dd_csv`, `dd_xlsx`, `evidence_csv`, `memo_md`, `memo_docx`입니다. PDF는 지원 형식으로 표시하지 않습니다. 보고서는 템플릿 기반이며 LLM 호출에 의존하지 않습니다. 수식으로 해석될 수 있는 셀 값은 CSV/XLSX 내보내기에서 안전하게 처리합니다. 내보내기 receipt는 제품의 투자 승인이 아닙니다.

## 실행과 검증의 한계

기본 진입점은 loopback 주소 `127.0.0.1:8050`을 사용하는 합성 Demo입니다. 웹 Local Live, 임의 문서 업로드, 실제 provider 실행은 지원하지 않으며 설정만 바꿔 활성화되지 않습니다. 공개 호스팅·다중 계정 협업·조직 인증·실제 VDR 운영 기능은 이번 구현 범위에 포함되지 않습니다.

전체 기존 회귀 테스트, 새 서비스·내보내기·HTTP 경계 테스트, 브라우저 시연과 화면 점검의 실제 결과는 `implementation_evidence/CHUNK_04.md`에 기록합니다. 이 구조 문서는 실행 증거를 대신하지 않습니다. Windows 설치 절차를 제공하더라도 실제 Windows에서 실행하지 않은 항목을 검증 완료로 적지 않습니다.
