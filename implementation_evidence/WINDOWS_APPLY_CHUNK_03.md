# Windows에서 Chunk 3 적용

이 ZIP은 첨부 Chunk 2를 기준으로 만든 전체 프로젝트입니다. 원격 GitHub 저장소의 현재 상태는 조회하지 않았습니다. 인증이나 개인 키는 이 작업에 사용하지 않았습니다. 아래 명령은 사용자의 개인 Windows PC에서 실행합니다.

1. 현재 저장소의 미반영 변경을 보존하고 별도 브랜치를 만듭니다.

```powershell
git status --short
git switch -c feature/chunk-03-synthetic-evaluation
```

2. 현재 코드가 제공했던 Chunk 2와 같다면 ZIP의 `review/CHUNK_03.patch`를 적용합니다. 먼저 확인 명령이 성공해야 합니다. 현재 저장소에 추가 변경이 있으면 충돌을 먼저 검토하고 강제로 덮어쓰지 않습니다.

```powershell
git apply --check C:\path\to\review\CHUNK_03.patch
git apply C:\path\to\review\CHUNK_03.patch
```

Git을 사용하지 않고 실행부터 확인하려면 ZIP의 `orion-deal-intelligence` 폴더를 새 폴더에 풀고 그 안에서 다음 명령을 실행하면 됩니다. `.git`, 가상환경, 개인 DB와 인증정보는 ZIP에 포함하지 않습니다.

3. Python 3.12 환경에 기존 Windows hash lock과 프로젝트를 설치합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python scripts\validate_chunk03.py
```

검증기는 실제 합성 문서 생성·parsing·재무/정답/입력 경계 검증·시나리오·fixture 평가·전체 pytest를 실행합니다. 결과는 `implementation_evidence/chunk03-validation.json`과 `logs/chunk03-*.log`에 기록합니다. 실시간 LLM 호출이나 공개 웹서버를 실행하지 않습니다.

4. 변경 내용과 테스트 결과를 확인한 뒤 사용자가 commit/push합니다.

```powershell
git diff --check
git diff --stat
git status --short
git add .
git commit -m "Implement Chunk 3 synthetic data and evaluation"
git push -u origin feature/chunk-03-synthetic-evaluation
```

위 commit/push는 안내일 뿐 이 작업 환경에서 실행하지 않았습니다. Windows 실행은 Linux 결과를 그대로 성공으로 간주하지 말고 개인 PC 또는 Windows CI의 실제 로그로 확인해야 합니다. Git 설정·원격 주소·인증 방식은 기존 개인 저장소 설정을 사용합니다.
