var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};
dagfuncs.fwNumber = function (params) {
    if (params.value === null || params.value === undefined || params.value === '') return '미제공 / 미정량';
    const value = Number(params.value);
    if (!Number.isFinite(value)) return '미제공';
    return value.toLocaleString('ko-KR', {minimumFractionDigits: 1, maximumFractionDigits: 2});
};

// Native details owns its open state; choosing a tool closes only that menu.
(function () {
    let dirty = false;
    let blockedClick = false;
    function showDirty(value) {
        dirty = value;
        const notice = document.getElementById('frame-unsaved');
        if (notice) notice.textContent = value ? '미저장 입력이 있습니다.' : '';
    }
    function editable(target) {
        return target && target.closest && target.closest('[id*="fw-field"], #studio-edit-issue, #studio-edit-request, #studio-edit-note, #studio-memo, #review-reason');
    }
    document.addEventListener('input', function (event) { if (event.isTrusted && editable(event.target)) showDirty(true); });
    document.addEventListener('change', function (event) { if (event.isTrusted && editable(event.target)) showDirty(true); });
    function protect(event) {
        if (!dirty || !event.target.closest) return;
        if (event.type === 'keydown' && !['Enter', ' ', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        const destination = event.target.closest('#deal-selector .Select-option, #deal-selector .VirtualizedSelectOption, #fw-role .Select-option, #fw-role .VirtualizedSelectOption, #fw-period .Select-option, #fw-period .VirtualizedSelectOption, #workflow-open-question, #workflow-question-issue, #workflow-origin-issue, #fdd-stage label, #stage-view label, #workspace-tabs label, #support-tools-drawer button, #fw-area label, .studio-file, #reset-demo');
        const keyboardChoice = event.type === 'keydown' && event.key === 'Enter' && event.target.closest('#deal-selector, #fw-role, #fw-period');
        if (!destination && !keyboardChoice) return;
        if (!window.confirm('미저장 입력이 있습니다. 저장하지 않고 이동하시겠습니까? 취소하면 현재 화면에서 저장할 수 있습니다.')) {
            if (event.type === 'mousedown') blockedClick = true;
            event.preventDefault(); event.stopImmediatePropagation();
        } else showDirty(false);
    }
    // React Select changes its value on mousedown, before click.
    document.addEventListener('mousedown', protect, true);
    document.addEventListener('keydown', protect, true);
    document.addEventListener('mouseup', function (event) {
        if (blockedClick) { event.preventDefault(); event.stopImmediatePropagation(); }
    }, true);
    document.addEventListener('click', function (event) {
        if (blockedClick) {
            blockedClick = false;
            event.preventDefault(); event.stopImmediatePropagation();
        }
    }, true);
    document.addEventListener('click', function (event) {
        if (!event.target.closest) return;
        if (editable(event.target) && event.target.closest('.Select-option, .VirtualizedSelectOption')) showDirty(true);
        const file = event.target.closest('.studio-file');
        if (file) {
            document.querySelectorAll('#frame-file-list .studio-file.selected').forEach(button => button.classList.remove('selected'));
            file.classList.add('selected');
        }
        const tools = event.target.closest('#support-tools-drawer button');
        if (tools) document.getElementById('support-tools-drawer').open = false;
    });
    window.addEventListener('beforeunload', function (event) {
        if (dirty) { event.preventDefault(); event.returnValue = ''; }
    });
    const savedMessages = {};
    let project = '';
    let savedRevision = '';
    function sync() {
        const marker = document.querySelector('.finance-page-marker');
        let page = marker ? marker.dataset.page : null;
        const selected = document.querySelector('#workspace-tabs input:checked');
        if (selected) page = selected.value;
        // RadioItems has no checked option for a support-tool page. Use the common title.
        const title = document.getElementById('fw-title');
        const text = title ? title.textContent : '';
        document.querySelectorAll('#support-tools-drawer button').forEach(function (button) {
            const active = button.textContent === text;
            if (active && button.getAttribute('aria-current') !== 'page') button.setAttribute('aria-current', 'page');
            if (!active && button.hasAttribute('aria-current')) button.removeAttribute('aria-current');
        });
        const heading = document.getElementById('deal-heading');
        const currentProject = heading ? heading.textContent : '';
        if (project && project !== currentProject) showDirty(false);
        project = currentProject;
        const revision = ['snapshot-summary','fw-status-pills','studio-history'].map(id => document.getElementById(id)?.textContent || '').join('|');
        if (savedRevision && savedRevision !== revision) showDirty(false);
        savedRevision = revision;
        ['fw-message','studio-message','status-live-region'].forEach(function (id) {
            const message = document.getElementById(id)?.textContent || '';
            if (message !== savedMessages[id]) {
                if (/저장했습니다|초안을 저장했습니다|메모를 저장|초기화했습니다|증빙을 승인|증빙을 반려/.test(message)) showDirty(false);
                savedMessages[id] = message;
            }
        });
        if (title && title.getAttribute('title') !== text) title.setAttribute('title', text);
    }
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {childList:true, subtree:true, characterData:true});
})();
