/* Keyboard source inspection uses the same safe row-ID click event as a pointer. */
document.addEventListener('keydown', function (event) {
  if (event.key === 'Enter' && event.target.closest && event.target.closest('.ag-cell')) {
    event.target.closest('.ag-cell').click();
  }
  if (event.key === 'Escape' && event.target.closest && event.target.closest('.inspector-pane')) {
    const workspace = document.getElementById('main-workspace');
    if (workspace) workspace.focus();
  }
});
