# 파일 형식 아이콘 / File-type artwork

2026-11-18에 Microsoft Fluent UI의 공식 파일 형식 CDN에서 받은 SVG를 변경 없이 로컬 `web/assets/file-*.svg`로 제공한다. Word·Excel·PowerPoint의 파일 형식 아이콘이며 Orion의 로고나 제품 보증 표시로 사용하지 않는다. CSV는 Excel 문서와 다른 아이콘이다.

- 배포 API 설명: [Microsoft Fluent UI file-type icons](https://github.com/microsoft/fluentui/tree/master/packages/react-file-type-icons).
- 자산 조건: [Microsoft Fabric Assets License Agreement](https://aka.ms/fluentui-assets-license). 파일을 나타내거나 여는 제품 내 파일 형식 아이콘 사용을 기준으로 검토했다.
- 파일별 원본 URL·취득일·SHA256은 `src/orion/web/assets/file-icons-sources.json`에 기록했다. 아이콘은 24×24 원본 SVG이며, 실행 중 외부 사이트를 호출하지 않는다.

PDF에도 같은 공식 Fluent UI 파일 형식 아이콘을 사용한다. Blueprint의 Adobe Acrobat 아이콘 대신 PDF 파일 표시용 아이콘을 택했다. [Adobe 배포 조건](https://www.adobe.com/legal/permissions/icons-web-logos.html)은 Acrobat으로 생성된 PDF에 대한 링크, 주변 간격, 크기 유지 등으로 사용 범위를 한정하므로 현재 자료 목록에 일괄 적용하지 않았다. Microsoft·Adobe와의 제휴나 인증을 나타내지 않는다.
