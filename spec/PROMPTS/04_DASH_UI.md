# Chunk 4 Dash UI 구현 프롬프트

G3까지의 실제 service와 source index를 연결해 독립적인 문서 중심 UI를 구현하라. 예산10시간. scope 밖의 사업 로직·다른 screen은 추가하지 않는다.

## 정확한 입력

`implementation_evidence/CHUNK_03.md`, `spec/06_DASH_UI_UX_DESIGN_SYSTEM.md`, `spec/DESIGN/workspace-wireframe.svg`, `spec/DESIGN/update-review-wireframe.svg`, `spec/02_PRD_AND_ACCEPTANCE_TESTS.md`, `spec/03_SYSTEM_ARCHITECTURE.md`, 실제 `services/`, `demo.py`, `data/synthetic/`와 source index.

## 출력

- `src/orion/app.py`의 Dash app/server와 `ui/layout.py`, `ui/callbacks.py`, `assets/orion.css`.
- 세 pane, Top-3 3행, Matrix/Questions/Changes tabs, source highlight, exact native locators, clear review/verification badges.
- 문서·claim·question 선택의 stable ID 연동. priority와 screen sort 구별. optional columns chooser는 일반 Dash control.
- Preview는 승인 전 상태, approved commit 전에는 기존 Snapshot 유지. approved/duplicate/rejected/conflict/loading/errors를 동작으로 구현.
- Demo tab memory action replay와 두 탭 분리. 공개 업로드/Live 금지는 서버에서 함께 검증.
- `tests/ui/`, Playwright screenshots/keyboard evidence. Export UI는 승인 상태를 보여주고 실제 exporter가 없는 경우 완료된 척 파일을 만들지 않는다. 완전 연결은 Chunk5.

## 실행

```bash
python -m orion.app
```

다른 terminal에서:

```bash
python -m playwright install chromium
python -m pytest tests/ui -q --strict-markers
python -m pytest tests/core tests/transitions -q --strict-markers
```

14px보다 작은 본문·상태 글자로 정보를 억지 압축하지 마라. Hebbia 화면을 pixel clone하지 말고 명세의 teal/slate 토큰과 배치를 적용하라. AG Grid Enterprise modules, native Excel export, sidebar, row grouping을 활성화하지 않는다. DMC를 새로 도입하지 않는다.

## G4 Gate

1440×900/1280×720/1024×768 및200% zoom을 실제로 확인하라. Tab/arrow/Enter/Escape, focus 복귀, live-region, 색상+텍스트 상태, escaped source를 검사한다. Northstar source→staging→approve→comparison과 Lumen conflict reopen을 클릭으로 완료하라. 두 browser context의 독립 상태를 확인하고 client-tampered action을 서버에서 거절하라. AT20–22/28을 통과시키고 component-only smoke를 전체 UX 테스트로 보고하지 않는다.

`implementation_evidence/CHUNK_04.md`에 actual viewport, screenshot 경로, 사용성 결함·수정, pytest logs, git diff를 남겨라. 기술적으로 통과했더라도 읽기 어려운 화면은 QA 완료로 선언하지 않는다.
