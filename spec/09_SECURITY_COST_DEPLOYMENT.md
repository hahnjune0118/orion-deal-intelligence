# Security Cost and Deployment

Contract 1.0.0 · 외부 문서 확인일 2026-11-03. 설계 정책·공식 기능 확인·미실행 시험을 구별한다.

## 실행 모드와 권한

| 항목 | Public Demo | Local Live |
|---|---|---|
| 입력 | 배포된 3개 합성 pack과 allowlist 이벤트 | 본인이 사용 권한을 확인한 synthetic/public 파일만 |
| API | adapter가 없어야 함, 호출 0 | server-side 개인 key와 pricing 검증 후 |
| 업로드 | UI 숨김+서버 거부 | 형식·크기·내용 제한 적용 |
| 상태 | 탭별 stateless replay, 새로고침 reset | SQLite와 원문 bytes의 로컬 지속성 |
| 사용자 | synthetic reviewer 시뮬레이션 | 단일 OS 사용자, loopback bind |
| export | 합성 branch에서 명시 승인 | 현재 Snapshot reviewer 승인 |
| key | 공개 환경에 설치하지 않음 | 환경변수/로컬 .env, gitignore, client 미전송 |

Demo가 local key를 발견했다고 Live로 전환하지 않는다. mode는 startup configuration이며 client가 바꿀 수 없다. CI는 dummy key가 설정된 Demo에서도 outbound network 0을 검증한다. static assets는 self-host하고 CDN·analytics·외부 font 요청을 기본 사용하지 않는다. UI의 disabled 버튼 외에 service layer에서 upload/live/export 권한을 검사한다.

## 위협과 구체적 통제

| 위협 | 통제 | 시험 |
|---|---|---|
| 문서 prompt injection | 원문은 데이터; tool call/SQL/승인 instruction 무시, structured draft만 허용 | 악성 문서가 state/권한을 바꾸지 못함 |
| key 유출 | 환경변수 `OPENAI_API_KEY`; Store/HTML/log/export에 절대 포함 금지 | response·bundle·git·log scan |
| cross-visitor state | 불변 fixture + client action allowlist replay, 공유 mutable state 금지 | 두 탭 동시 시나리오 |
| path traversal/외부 URL | bytes upload만, hash 기반 저장 경로, 외부 URL fetch 없음 | `../`, file URL, arbitrary path 거절 |
| file bomb/parser 과부하 | 파일/expanded-size/page/shape/텍스트 한도·subprocess timeout | oversized/zip-bomb fixture |
| source HTML/CSV injection | HTML escaping; CSV/XLSX의 `= + - @` 시작 문자열은 text escape | export formula payload 검사 |
| stale/중복 승인 | revision check·idempotency·transaction | 동일/다른 payload key, rollback |
| client role 위조 | actor는 server context에서만 | analyst→reviewer 위조 거부 |
| XSS/CSRF | unsafe HTML 금지, Local origin/Host allowlist, 인증이 필요한 확장은 별도 설계 | 임의 callback·cross-origin POST 거절 |

로그는 metadata 중심이며 raw 문서를 외부 error tracker로 보내지 않는다. local .env·source uploads·SQLite·개인 export는 gitignore에 포함한다. 공개 repo에는 합성 fixture만 포함한다. 라이선스 notice와 secret scan을 release gate에 둔다.

## API 전송과 retention

Local Live는 검토자가 확인한 발췌 범위만 보낸다. 파일 업로드 API·hosted vector store·conversation store는 MVP에서 사용하지 않는다. 가능한 request에서는 `store=false`를 설정하지만 이를 zero retention이나 법률 준수 보장으로 설명하지 않는다. OpenAI 공식 data-control 문서는 endpoint와 조직 설정에 따라 보관·abuse monitoring 조건이 다름을 설명한다. 실제 계정 조건과 최신 모델/API 정책을 실행 전에 확인한다. 출처 [S09](11_DECISION_LOG_AND_SOURCES.md).

프로젝트 자료의 법률 내용은 **학술 source가 제기한 쟁점**으로만 기록한다. KRX 조항, 개인정보 국외이전, 금융투자업, AI 기본법 적용 여부를 여기서 현행 법률 결론으로 확정하지 않는다. 이 MVP는 해당 데이터를 수집하지 않으며 실제 비공개 자료·상용화 기능을 추가할 때 공식 법령·약관과 별도 검토가 필요하다. 이번 범위에 불필요한 법률 조사나 내부 회사자료 요청을 하지 않는다.

## 비용 한도 정책

제품 기본값(실제 API 가격 아님): 실행당 0.50 USD, 일간 2.00 USD, 전체 평가 명령당 5.00 USD; active run 1개; 총 provider 요청 최대3회/run(최초·transport retry·format repair 모두 포함). request input 12,000 tokens 이하, output 2,000 tokens 이하. SDK automatic retry는 0으로 두고 app budget controller에서만 retry한다. provider tool 호출·외부 웹검색·reasoning 설정의 불명확한 과금 항목은 금지한다.

일간 budget은 UTC 00:00 기준 calendar day로 집계하고 화면에 UTC 기준임을 표시한다. 날짜가 바뀌어도 미확정 reserve를 소멸시키지 않는다. 평가 명령의 총 budget은 자정을 넘어도 같은 invocation에 누적한다.

모델 이름/가격은 [CONFIG/live_pricing.example.json](CONFIG/live_pricing.example.json)에 **null로 둔다**. 사용자가 보유한 계정에서 지원되는 모델의 공식 input/output 단가와 output token cap 동작을 검증하고 `pricing_version`·확인일을 기입하기 전에는 Live 실행을 차단한다. model availability/가격을 추정해 기본값을 넣지 않는다. 7일 이상 지난 가격 확인은 재확인을 요구하는 프로젝트 정책이다.

예약비용은 `(max_input_tokens×input_rate + max_output_tokens×output_rate)/1,000,000`이며 token count 실패는 fail closed다. 비용 단가는 USD/million tokens다. provider별 billable output(해당하는 경우 reasoning token 포함)의 한도가 실제로 적용되는지 adapter 시험에서 확인한다. token ceiling이 청구 상한을 보장하지 않는 모델이면 지원 대상에서 제외한다.

SQLite budget transaction에서 `spent + reserved + worst_case_request_cost ≤ cap`을 만족할 때만 reserve한다. 동시에 들어온 두 요청은 직렬 검증한다. 완료 시 actual usage 비용으로 settle, 확실히 전송 전 실패한 요청만 reserve 해제한다. timeout/응답 분실은 청구 불확실 상태로 예약금을 유지하여 budget 우회를 막는다. 수동 해제는 provider usage 확인과 audit reason이 필요하다. 캐시 hit는 비용0이며 호출도0이다. 이 정책은 추적 가능한 어댑터 경계의 제한이며 다른 앱이 같은 API key로 쓰는 계정 전체 비용까지 제한하지 않는다.

## Dependency pin 정책

직접 의존성 후보는 [CONFIG/requirements-candidate.txt](CONFIG/requirements-candidate.txt)와 [QA/dependency_metadata.json](QA/dependency_metadata.json)에 exact version으로 고정했다. PyPI 공식 배포 메타데이터에서 각 release 존재·Python 범위·license 정보를 조회했다. 설치 호환성·최신 보안 취약점 부재까지 확인한 것은 아니다. 의도적으로 Dash 3 계열의 검토 가능한 baseline을 쓰며 latest라는 주장을 하지 않는다.

복구한 Linux CPython 3.12 환경에서 17개 직접 의존성의 resolver dry-run은 성공했고 총 63개 패키지로 해석됐다. [resolver 요약](QA/dependency_resolution_summary.json)과 [Linux hash-lock 후보](CONFIG/requirements-linux-resolved.lock)를 포함한다. 실제 설치·브라우저 통합·Windows 호환·취약점 검사가 끝난 release lock은 아니며 Chunk 1에서 검증 후 채택한다.

Chunk 1은 Python 3.12 Windows/Ubuntu에서 resolve/import/smoke 후 OS별 transitive hash lock을 생성한다. `pip check`, 취약점/라이선스 검토, Dash+Grid 브라우저 smoke를 통과해야 구현 baseline으로 채택한다. 실패하면 패키지를 무작정 최신으로 올리지 않고 영향·검증을 기록한다. DMC는 MVP에 없고 AG Grid Community만 사용한다. Dash 3 공식 migration은 AG Grid와 DMC의 최소 호환 버전을 안내하지만 이 pin 조합의 제품 시험을 대신하지 않는다.

## Windows 시작 순서

다음은 **Chunk 1이 저장소와 lock을 생성한 뒤** 사용할 명령이다. 현 명세 패키지 자체에는 실행 앱이 없다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m pip install --no-deps -e .
$env:ORION_MODE = 'demo'
.\.venv\Scripts\python -m orion.cli seed-demo
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m orion.app
```

위 editable 설치는 Chunk 1에서 만든 src-layout 프로젝트를 Python이 찾도록 한다. PowerShell execution policy 변경 없이 venv python을 직접 호출한다. UI 개발용 debug는 loopback에서만 사용한다. Live 실행은 pricing config·예산·전송 범위를 확인한 후 ORION_MODE=local_live로 재시작한다. key 값을 문서·terminal recording·git에 넣지 않는다.

GitHub Actions는 Windows/Ubuntu Python3.12 matrix, hash-lock install, pip check, schema/contracts/core/integration tests, browser smoke, secret scan, artifact retention을 실행한다. CI 기본 outbound LLM 호출은 금지하고 fake provider로 비용·오류를 시험한다. CI cloud deploy는 별도 release 단계다.

## 호스팅 후보와 지속성

| 후보 | 공식 확인한 조건 | 비용·한계 | 본 제품 판단 |
|---|---|---|---|
| Render Free Web Service | 15분 idle 후 spin-down, filesystem ephemeral, persistent disk 불가, workspace 월750 free instance hours | 무료 compute 조건은 있으나 bandwidth/build 초과·계정 조건 존재. 상시 무료/SLA 보장 아님 | Stateless Demo 우선 후보. cold start 안내와 실제 배포 smoke 필요 |
| Render paid + disk | paid web service에 disk 부착, mount 내부만 보존 | pricing 페이지에서 정확한 현재 paid SKU 금액을 본 조사로 확보하지 못함. 구매 전 확인 | 이번 Demo에는 불필요. 미래 cloud SQLite용 후보일 뿐 |
| Railway Hobby | 월 $5 minimum commitment에 첫 $5 사용 포함, 초과 사용 추가 청구 | 정액 무제한 아님. CPU/RAM/egress/volume 사용량 과금 | 유료 허용 시 대안. usage cap·현재 견적을 확인하고 선택 |

공식 출처는 [S07–S08](11_DECISION_LOG_AND_SOURCES.md)이다. 파일 저장이 필요 없는 Demo는 volume을 요청하지 않는다. 다중 worker에서 in-memory session state를 공유할 수 있다고 가정하지 않는다. stateless replay를 지키면 재시작/다중 instance에서도 합성 상태를 재구성할 수 있으나 초기 운영은 작은 한 인스턴스로 제한한다.

배포 성공 기준: 외부 URL 200, cold start 후 재접속, 세 Deal interaction, approved export, two-tab isolation, 서버 재시작, server/env/asset secret scan, API counter0. 실제 배포 계정 생성·비용 지출·공개 publication은 이번 **명세 제작 범위에 포함하지 않는다**.
