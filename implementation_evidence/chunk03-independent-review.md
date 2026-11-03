# Chunk 3 engineering review evidence

기록 시각(UTC): 2026-11-03T08:15:57.540115Z

## 작성·검토 범위

이 기록은 팀 내 engineering review이며, 외부 Analyst의 독립·블라인드 평가가 아니다. 작성자는 parent의 명시적 업무 배정에 따라 `src/orion/synthetic/manufacturing.py`의 Ridgeway Homeware 사례를 직접 작성했다. 따라서 제조업 gold 또는 사업 판단에 대해 독립 검토자라고 주장하지 않는다. Northstar, quantitative engine, evaluation harness, native parsers는 코드·자료를 읽고 문제를 각 담당자에게 전달하는 방식으로 검토했으며 해당 구현 파일은 직접 수정하지 않았다.

직접 작성한 제조업 범위: 원본 가상 문서 6개, evidence 23개, DD question 9개, FY2024/FY2025 재무자료, 재고 실사 수량표, 한 단계 증빙 이벤트. 매출 증가와 재고 축적, 잠정 EBITDA normalization, maintenance CAPEX, working capital 및 cash conversion을 다룬다. 원문 표의 수량·단가가 실제 quantity reconciliation을 뒷받침하도록 count exhibit을 보완했다. 최종 검토 후 코드·원문·테스트는 추가 변경하지 않았다.

## 첨부 baseline 비교

ZIP bytes를 직접 열어 같은 상대 경로를 비교했다.

| 항목 | 실제 확인 |
|---|---|
| Foundation archive | ORION_CHUNK_01_FOUNDATION(4).zip, package 0.1.0, 252 repository entries |
| Integrated archive | ORION_CHUNK_02_CORE_ENGINE_INTEGRATED(2).zip, package 0.2.0, 296 repository entries |
| Foundation 파일 삭제 | 0 |
| 기존 테스트 파일 byte 변경 | 0 |
| 양쪽 Python 제약 | >=3.12,<3.13 |
| Foundation ZIP SHA-256 | edd75c0de94577b7cee3285650211d40610d892570f8d8870267d43971399260 |
| Integrated ZIP SHA-256 | 41d383e3e1ecc2cb9d793a3de498488a74d2315f9f11eb1fb52fa994743bb2d3 |

원격 저장소는 조회하지 않았다. 이 결과는 첨부 ZIP 간 비교이며 GitHub HEAD 동일성 확인이 아니다.

## 실제 실행한 adversarial probes

실행 환경은 저장소의 `PYTHONPATH=src`와 기존 Python 3.12 venv를 사용했다. source stage 변조는 `TemporaryDirectory`에 복사한 데이터에서 수행했고, gold 변조는 deepcopy한 메모리 객체에서만 수행했다. 배포 데이터는 변조하지 않았다. 아래 **12개 check가 최종 실행에서 모두 통과**했다. 이 수치는 전체 pytest 개수에 가산하지 않는 별도 ad-hoc engineering probe 수다.

| 번호 | 검사 | 실행 결과 |
|---:|---|---|
| 1 | Stage/manifest 동시 변조 | PASS — 임시 데이터셋 복사본에서 nb_doc_followup.available_stage를 4→0으로 바꾸고 machine_sha256와 inventory stage까지 함께 갱신했다. 고정 source disclosure allowlist가 ValueError로 거부했다. |
| 2 | 빈 실패 출력 | PASS — failed 상태의 빈 SystemOutput은 resolved_question_removal_accuracy에서 0을 받았다. |
| 3 | 미검토 중복 판정 | PASS — family mapping이 검토되지 않은 질문은 duplicate_question_rate=None, status=not_reviewed로 처리됐다. |
| 4 | Northstar 원본 gold | PASS — 변경하지 않은 nb gold의 answer_key_audit가 통과했고, analyst hypothesis의 source_span_ids가 비어 있어 문서 제목을 증거로 인용하지 않았다. |
| 5 | Northstar 허위 locator | PASS — company-reported claim source locator의 block_index에 100을 더한 변조를 audit가 거부했다. |
| 6 | Northstar 잘못된 evidence 참조 | PASS — 존재하지 않는 evidence_id를 claim-evidence 관계에 추가한 변조를 audit가 거부했다. |
| 7 | 미래 evidence의 T0 유입 | PASS — nb_ev_ownership(T4)을 T0 supporting_evidence_ids에 추가한 변조를 audit가 거부했다. |
| 8 | 미래 evidence의 현재 claim 판정 유입 | PASS — T0 company assertion의 판정 관계에 T4 ownership evidence를 추가한 변조를 audit가 거부했다. |
| 9 | T0 model input 경계 | PASS — nb stage0 bundle은 cim/financial/plan/crm 네 문서만 포함했다. 미래 네 문서와 Birch의 Aster 소유관계 답안은 포함하지 않았다. |
| 10 | 제조업 원본 gold | PASS — 변경하지 않은 mf gold의 answer_key_audit가 통과했고, analyst hypothesis가 문서 제목을 증거로 인용하지 않았다. |
| 11 | 제조업 허위 locator | PASS — company-reported claim source locator의 block_index에 100을 더한 변조를 audit가 거부했다. |
| 12 | 제조업 잘못된 evidence 참조 | PASS — 존재하지 않는 evidence_id를 claim-evidence 관계에 추가한 변조를 audit가 거부했다. |

첫 gold probe는 담당자가 새 `label_stage` 스키마와 산출물을 재생성하던 중 실행되어 `KeyError: label_stage`로 중단됐다. 이 시도를 통과로 세지 않았다. 담당자가 최종 재생성 완료를 알린 뒤 현재 gold를 다시 읽어 위 gold 관련 check를 실행했고 모두 통과했다.

추가로 두 가상 world에 대해 income statement, balance sheet, NWC/CFO, cash, PPE, equity roll-forward 및 주요 operating schedules의 정수 산술을 직접 실행했다. Northstar 21개, 제조업 28개 world arithmetic check가 모두 통과했다. 실제 native table·dataset 전체 검증과 최종 전체 pytest 결과는 주 실행 로그/CHUNK_03 보고서를 기준으로 한다.

## 검토에서 발견하여 담당자가 수정한 주요 사항

- Evidence dependence의 입력 순서와 duplicate-source alias를 통한 재계산 우회.
- Native SourceSpan ID가 문서 버전·원문 변경을 반영하지 않던 문제와 unsupported native content fallback.
- Machine metadata의 공개 stage 변경으로 미래 문서가 T0 input에 유입될 수 있던 경로.
- Engine-derived status를 다시 gold로 사용하던 순환 검증, 문서 제목을 hypothesis 근거로 인용하던 표현.
- 빈 실패 출력의 removal credit, 미검토 질문의 duplicate rate, 느슨한 locator metadata 검사.
- Expanded dataset에서 요청한 evaluation arms/mode를 무시하던 경로 및 실제 stale-revision control 구분.
- 제조업 financial driver mapping, 측정 기간, 원문 재무표와 world 간 검증 범위.

## 재현성 및 한계

아래 SHA-256은 **이 기록 작성 시점의 파일 snapshot**이다. 개별 probe 직전에 독립적으로 hash를 캡처한 것은 아니므로, 각 probe 실행 시각의 별도 봉인된 snapshot이라고 주장하지 않는다. 별도의 전체 테스트 source hash와 최종 패키지 checksum은 parent의 release 검증 자료를 따른다.

| 파일 | 기록 시점 SHA-256 |
|---|---|
| `src/orion/synthetic/manufacturing.py` | `0f2da5b6720912a9659d6d5752ba1dd224a86d662afa6c84cb0b2885ac4954ad` |
| `src/orion/synthetic/load.py` | `68cc1e908608515e7884e4411020aa46c4c05b4493488f6a2e43f5ec6eb91ecf` |
| `src/orion/synthetic/validate.py` | `6fe645f946d9fe0ce78e6b757abb5025a390835b1ac669358bda5dacb54564dd` |
| `src/orion/evaluation/metrics.py` | `aebd0a175192777c9926d620fc4a806bf08006c82268865787f5b42861d4989f` |
| `src/orion/evaluation/inputs.py` | `716e9243394fdc0a9b8000e90507d4a153c7157bef3f0ce266c215cb97dcbf1b` |
| `src/orion/evaluation/synthetic_bridge.py` | `e3b64008052257e60071b20f880c57a8d160187e487ac2d8625585a1fd39df28` |
| `src/orion/quant/bayes.py` | `25d814275a91f061c892b2de15edae0ca1c1e36452dc286bcf7719d5eaa140ac` |
| `src/orion/adapters/parsers/native.py` | `a6c5298693c39cac2594c89f561416524ae838c15280f98bea2b12b55a38e77f` |
| `chunk3_synthetic_evaluation/gold/nb_gold.json` | `cd63a16c7ee06eb645d48aa4357a10b5e19030853896b5c4ef6eb376fe8d3bd4` |
| `chunk3_synthetic_evaluation/gold/mf_gold.json` | `2e78291e4f4953d58f4c3bc4f28825f6c3dc5a8f6b54ddfed16954254eb2510f` |

Gold는 self-authored/provisional이다. 외부 인간 검토, blinded semantic agreement, 실제 B0–B3 LLM 성능, 실제 투자 예측력, Windows 실행 또는 공개 배포를 이 engineering review로 검증했다고 주장하지 않는다. 데이터 폴더의 공동 배치는 hostile code에 대한 filesystem sandbox가 아니며, 모델에 전달하는 source-only serialization 경계를 검사했다.
