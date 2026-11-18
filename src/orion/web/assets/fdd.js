var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};
dagfuncs.fwNumber = function (params) {
    if (params.value === null || params.value === undefined || params.value === '') return '미제공 / 미정량';
    const value = Number(params.value);
    if (!Number.isFinite(value)) return '미제공';
    return value.toLocaleString('ko-KR', {minimumFractionDigits: 1, maximumFractionDigits: 2});
};

// Native <details> owns its open state. Close on selection without a stale Dash
// `open:false` prop that can diverge after the user opens the drawer again.
document.addEventListener('click', function (event) {
    if (!event.target.closest) return;
    const tools = event.target.closest('#support-tools-drawer button');
    const source = event.target.closest('#source-library-drawer .studio-file');
    if (tools) document.getElementById('support-tools-drawer').open = false;
    if (source) document.getElementById('source-library-drawer').open = false;
});
