# Chunk 3 Synthetic Data and Evaluation 구현 프롬프트

G2 통과를 확인하고 실제 문서 ingestion과 평가 harness를 구현하라. 예산10시간. UI 완성이나 기업자료 수집은 이 단계 범위가 아니다.

## 정확한 입력

`implementation_evidence/CHUNK_02.md`, `spec/07_SYNTHETIC_DEAL_DATASET_SPEC.md`, `spec/08_EVALUATION_PROTOCOL.md`, `spec/04_DATA_CONTRACTS.md`, `spec/DATASET_SPECS/financial_truth.json`, `spec/EXAMPLES/*.json`, `spec/DATASET_SPECS/cd/*.json`, `spec/DATASET_SPECS/lm/*.json`, `spec/EVAL_GOLD/*.json`, G1/G2 domain·repository·service modules.

## 구현과 출력

- Native synthetic sources 12개를 `data/synthetic/{ns,cd,lm}/`에 생성. 같은 숫자 truth로 PDF/DOCX/PPTX를 만들고 binary SHA-256 inventory 기록.
- PDF/PPTX/DOCX parsers: native locator, strict normalization, simple text/table, unsupported/scan fallback. source preview에 사용할 safe text units 제공.
- `retrieval.py`, `adapters/cached_llm.py`: deterministic candidate retrieval, authored cache와 실제 LLM cache provenance 구별. 초기 demo는 authored cache로 기능 검증 가능.
- `evaluation/` runner와 separate gold loader, arm prompt templates B0/B1/B2/B3/B1-R, run manifest, metric numerator/denominator/NA 계산.
- `evaluation/gold/`는 model input allowlist 밖에 놓고 `expected_top3_transition`도 input에서 제외.
- Native parser adversarial fixtures와 `tests/parsers/`, `tests/dataset/`, `tests/evaluation/`.
- CLI `generate-synthetic`, `ingest --case all`, `audit-model-inputs`, `evaluate --mode cached`.

## 명령

```bash
python -m orion.cli generate-synthetic --output data/synthetic
python -m orion.cli ingest --case all --mode demo
python -m orion.cli audit-model-inputs --cases all
python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode cached
python -m pytest tests/parsers tests/dataset tests/evaluation -q --strict-markers
```

실제 native 파일을 만들었으면 계약 fixture를 `data/parsed/`의 별도 runtime pack으로 복제하고 Document.file_sha256과 locator를 parser 결과로 채워라. `spec/EXAMPLES`와 계약 기대값을 덮어쓰지 않는다. runtime pack의 source mapping과 입력 digest 변화를 기록하고 같은 의미의 Top-3 전이가 유지됨을 검증하라. source text contract에 없던 회계 수치를 임의 추가하지 않는다. DOCX 페이지를 만들지 않는다. 이미지로 된 표를 성공적으로 추출했다고 주장하지 않는다.

## G3 Gate

세 형식의 올바른 source와 틀린 document/page/slide/paragraph/cell/quote를 구별해야 한다. 스캔 PDF·암호·복잡한 표는 정상 fallback, fabricated citation은 승인되지 않는다. 3개 case의 revenue/COGS/OPEX/customer totals/NWC/기간이 일치해야 한다. no double-count contract event. AT02–06/25–27을 검증한다.

기본3 transition+15 negative control이 실행 가능해야 하며, gold 없는 prompt dump를 보관하라. cached authored output은 실제 LLM 평가로 표시하지 않는다. 독립 gold 검토를 수행하지 못했으면 self-authored/provisional 상태를 유지한다. live 실험은 현재 key·가격·budget 경계가 준비된 뒤 Chunk5에서 수행한다.

`implementation_evidence/CHUNK_03.md`, source hash inventory, model-input audit, cached functional evaluation report와 git diff를 남겨라. Chunk4는 이 실제 source index를 사용해야 한다.
