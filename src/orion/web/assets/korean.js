/* Presentation formatters preserve row data, source filenames and locator numbers. */
var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};
dagfuncs.orionKoreanValue = function (params) {
    var labels = params.context.displayLabels;
    if (params.value === null || params.value === undefined) return '';
    var values = Array.isArray(params.value) ? params.value : String(params.value).split(', ');
    return values.map(function (value) {
        return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : value;
    }).join(Array.isArray(params.value) ? '; ' : ', ');
};
dagfuncs.orionSourceReferences = function (params) {
    if (!params.value) return '';
    return String(params.value).split('; ').map(function (reference) {
        var separator = reference.indexOf(' · ');
        if (separator < 0) return reference;
        var filename = reference.slice(0, separator + 3);
        var locator = reference.slice(separator + 3);
        locator = locator.replace(/^PDF page (\d+), block (\d+)$/, 'PDF 페이지 $1, 블록 $2')
            .replace(/^Slide (\d+), shape (\d+), paragraph (\d+)/, '슬라이드 $1, 도형 $2, 문단 $3')
            .replace(/^DOCX table (\d+), row (\d+), column (\d+), paragraph (\d+)$/, 'Word 표 $1, 행 $2, 열 $3, 문단 $4')
            .replace(/^DOCX paragraph (\d+), block (\d+)$/, 'Word 문단 $1, 블록 $2')
            .replace(/, table row (\d+), column (\d+)$/, ', 표 행 $1, 열 $2');
        return filename + locator;
    }).join('; ');
};

// Dash 3.2's Dropdown does not expose React Select's noResultsText property.
// Localize only its fallback message; leave options, searches and values alone.
function localizeDocumentSearch() {
    var observer = new MutationObserver(function () {
        document.querySelectorAll('#document-selector .Select-noresults').forEach(function (message) {
            if (message.textContent === 'No results found') {
                message.textContent = '검색 결과가 없습니다';
            }
        });
    });
    observer.observe(document.body, {childList: true, subtree: true});
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', localizeDocumentSearch, {once: true});
} else {
    localizeDocumentSearch();
}
