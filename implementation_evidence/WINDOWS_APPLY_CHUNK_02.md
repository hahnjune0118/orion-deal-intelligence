# 개인 Windows PC에서 Chunk 2 반영하기

이 패키지는 첨부된 Chunk 1 ZIP에 Chunk 2를 통합한 전체 소스입니다. 회사 GPT 환경에서 GitHub 원격 접근·인증·commit·push를 수행하지 않았습니다. `review/CHUNK_02.patch`는 **첨부된 Chunk 1과의 diff**이며 개인 GitHub 저장소의 현재 HEAD와 직접 비교한 결과가 아닙니다.

## 기존 저장소에 적용

1. ZIP을 기존 저장소 밖의 별도 폴더에 압축 해제합니다. 전체 통합 소스는 `orion-deal-intelligence/`, 검토 자료는 `review/`입니다.
2. 개인 PC의 기존 저장소에서 `git status --short`를 확인합니다. 미저장 작업이 있으면 먼저 commit 또는 별도 백업으로 보존합니다.
3. 작업 브랜치를 생성합니다. 이미 브랜치가 있으면 `git switch feature/chunk-02-core-engine`으로 이동하고 현재 변경과 충돌 여부부터 검토합니다.

```powershell
git switch -c feature/chunk-02-core-engine
```

4. ZIP에서 꺼낸 실제 patch 경로를 지정합니다. 아래 예시 경로는 자신의 압축 해제 위치로 바꿉니다.

```powershell
$chunkPatch = 'C:\Downloads\ORION_CHUNK_02_CORE_ENGINE_INTEGRATED\review\CHUNK_02.patch'
git apply --check $chunkPatch
```

`--check`가 성공하면 적용합니다. 실패하면 강제 적용하거나 기존 폴더 전체를 덮어쓰지 말고 `review/CHANGED_FILES.txt`와 통합 소스를 비교하여 다른 변경과 병합합니다. `.git`, 로컬 `.env`, DB, 가상환경은 패키지에 없으므로 기존 것을 삭제하지 마세요.

```powershell
git apply $chunkPatch
git diff --check
git diff --stat
git status --short
```

## 설치와 전체 테스트

기존 lock은 변경하지 않았으며 Python 3.12를 사용합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m pytest -q --strict-markers
.\.venv\Scripts\python scripts/verify_spec.py
.\.venv\Scripts\python -m orion.cli rank --state spec/EXAMPLES/initial_state.json
.\.venv\Scripts\python -m orion.cli replay --case ns --event staged --approve --output build/ns_after.json
.\.venv\Scripts\python -m orion.cli replay --case cd --event staged --approve --output build/cd_after.json
.\.venv\Scripts\python -m orion.cli replay --case lm --event staged --approve --output build/lm_after.json
```

Linux의 실제 실행 결과는 `implementation_evidence/CHUNK_02.md`와 `chunk02-validation.json`에 있습니다. Windows native 실행 및 GitHub Actions는 이 작업에서 `not_run`이며 위 실행으로 직접 확인해야 합니다.

## 검토 후 직접 commit 및 push

변경 파일과 로그를 검토한 뒤, 의도한 파일만 stage하고 본인의 Git 설정·인증으로 commit/push합니다. 이 단계는 사용자가 개인 PC에서 직접 수행합니다.

```powershell
git add -u
git add src/orion/domain/scoring.py src/orion/domain/transitions.py src/orion/services tests/core tests/transitions tests/integration
git add implementation_evidence/CHUNK_02.md implementation_evidence/WINDOWS_APPLY_CHUNK_02.md implementation_evidence/chunk02-validation.json implementation_evidence/chunk02-pytest.xml implementation_evidence/chunk02-targeted-pytest.xml implementation_evidence/chunk02-artifacts implementation_evidence/logs/chunk02-*
git add artifacts/orion_deal_intelligence-0.2.0-py3-none-any.whl
git diff --cached --check
git diff --cached --stat
git commit -m "Implement Chunk 2 Adaptive DD Core Engine"
git push -u origin feature/chunk-02-core-engine
```

`git add -u`는 이미 추적 중인 변경만 포함합니다. `git status --short`로 추가 파일 누락과 무관한 개인 변경 포함 여부를 반드시 확인하세요. `review/`는 검토용 부속물로 저장소 밖에 두어도 됩니다. Package version만 0.2.0으로 올렸으며 contract/scoring은 1.0.0으로 유지합니다.
