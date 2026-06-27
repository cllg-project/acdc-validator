(function () {
  'use strict';

  var startTime = null;
  var mode = window.ANNOTATOR_MODE; // 'validate' | 'review' | undefined

  // ── Ready modal ──────────────────────────────────────────────
  var modal = document.getElementById('ready-modal');
  var readyBtn = document.getElementById('ready-btn');
  var area = document.getElementById('annotation-area');

  function dismissModal() {
    modal.style.display = 'none';
    area.style.display = '';
    startTime = Date.now();
    if (mode === 'review') {
      var tf = document.getElementById('text-field');
      if (tf) tf.focus();
    }
  }

  if (modal && readyBtn && area) {
    readyBtn.addEventListener('click', dismissModal);

    document.addEventListener('keydown', function (e) {
      if (modal.style.display === 'none') return;
      if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        dismissModal();
      }
    });
  }

  // ── Save-edit button: dim until text changes ─────────────────
  if (mode === 'review') {
    var textField = document.getElementById('text-field');
    var saveBtn = document.getElementById('btn-save-edit');
    if (textField && saveBtn) {
      var originalText = textField.value;
      function updateSaveBtn() {
        var changed = textField.value !== originalText;
        saveBtn.classList.toggle('btn-primary', changed);
        saveBtn.classList.toggle('btn-muted', !changed);
      }
      updateSaveBtn();
      textField.addEventListener('input', updateSaveBtn);
    }
  }

  // ── Inject elapsed time on form submit ───────────────────────
  var form = document.getElementById('annotation-form');
  if (form) {
    form.addEventListener('submit', function () {
      var field = document.getElementById('elapsed-field');
      if (field && startTime !== null) {
        field.value = ((Date.now() - startTime) / 1000).toFixed(2);
      }
    });
  }

  // ── Keyboard shortcuts ───────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    if (!area || area.style.display === 'none') return;

    // Don't fire when typing in the textarea
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

    if (mode === 'validate') {
      if (e.key === 'v' || e.key === 'V') submitAction('validated');
      if (e.key === 'e' || e.key === 'E') submitAction('skip_edited');
      if (e.key === 's' || e.key === 'S') submitAction('skipped');
      if (e.key === 'u' || e.key === 'U') submitAction('abstained');
    } else if (mode === 'review') {
      if (e.key === 'v' || e.key === 'V') submitAction('validated');
      if (e.key === 's' || e.key === 'S') submitAction('skipped');
      if (e.key === 'x' || e.key === 'X') submitAction('rejected');
      if (e.key === 'Enter' && !e.shiftKey) submitAction('edited');
    }
  });

  function submitAction(action) {
    if (!form) return;
    var field = document.getElementById('elapsed-field');
    if (field && startTime !== null) {
      field.value = ((Date.now() - startTime) / 1000).toFixed(2);
    }
    // Find the matching submit button and click it to carry its name/value
    var btn = form.querySelector('button[value="' + action + '"]');
    if (btn) btn.click();
  }
})();
