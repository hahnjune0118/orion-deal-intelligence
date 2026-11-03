# Chunk 5 Integration and Release 구현 프롬프트

G1–G4를 확인하고 export·Live 경계·공개 Demo·실제 평가를 완성하라. 계획10시간+잔여 버퍼. 이전 계약의 범위를 넓히지 않는다.

## 정확한 입력

`implementation_evidence/CHUNK_01.md`부터 `CHUNK_04.md`, `spec/02_PRD_AND_ACCEPTANCE_TESTS.md`, `spec/08_EVALUATION_PROTOCOL.md`, `spec/09_SECURITY_COST_DEPLOYMENT.md`, `spec/CONFIG/live_pricing.example.json`, 모든 구현 source, OS lock, synthetic native files, evaluation harness, `.github/workflows/ci.yml`.

## 출력

- `services/export.py`: 현재 Snapshot+selection_digest에 대한 reviewer 승인, 동일 행의 CSV/XLSX, source-linked Markdown memo, formula injection escape.
- `adapters/openai_llm.py`, `services/budget.py`: 현재 확인한 모델/가격 설정, token/cost reserve/settle, max3 calls, SDK 자동 retry0, timeout 불확실 비용 유지. key/server boundary tests.
- Demo 배포 설정·start command·health endpoint, stateless replay/restart tests. public runtime에 개인 key·Live adapter가 없음을 검증.
- B0–B3와 B1-R 실제 evaluation report, raw manifest/annotations, ablation/negative results. 비용 부족/미실행은 not_measured.
- README 운영 절차·지원 입력·reset/backup·한계, 3–5분 demo video script와 실제 영상, 짧은 portfolio text.

## 실행 명령

```bash
python -m pytest -q --strict-markers
python -m orion.cli export --case ns --snapshot latest --format all --require-approval
python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode cached
python -m orion.cli verify-demo --deny-network --two-tabs --restart
git diff --check
```

검증된 개인 API 환경과 명시한 budget이 준비된 경우에만:

```bash
python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode live --budget-usd 5
```

Live를 실행할 수 없으면 숫자를 채우지 말고 차단 원인과 남은 정확한 명령을 남겨라. host 선택 시 현재 공식 가격·계정 조건을 확인하고 사용자의 배포/비용 권한 범위에 따른다. 본 prompt가 임의 유료계정 생성이나 비공개 데이터 업로드를 허용하는 것은 아니다.

## G5 Gate

AT01–30 전체 pass/fail/not_run 표, 실제 external URL/cold start/restart/API0/두 탭 격리/export 승인 결과를 제출하라. export는 digest 변경 후 과거 승인이 무효가 되어야 한다. provider timeout·동시 budget request·큰 input·가격 미검증을 차단해야 한다. 브라우저/로그/artifact에서 key를 검출하지 못해야 하며 scan 범위를 기록한다.

학술 목표를 달성하지 못해도 실패를 보고하라. cached author fixture의 perfect match를 LLM citation95%/Top3 80% 성과로 발표하지 않는다. user approval 없는 투자결정·DCF 수정·외부 발송을 추가하지 않는다.

마지막으로 `implementation_evidence/CHUNK_05.md`, `RELEASE_REPORT.md`, `evaluation/report.md`, `git diff`, 실행 로그, 남은 미검증 항목을 작성한다. App launch·demo publication·Local Live·academic evaluation의 완료 여부를 각각 구분하라. 전체가 실제로 검증되지 않았으면 부분 완료로 정확히 보고한다.
