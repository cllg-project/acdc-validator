(function () {
  'use strict';

  var startTime = null;
  var elapsed = 0;       // accumulated ms while visible
  var hidden = false;
  var mode = window.ANNOTATOR_MODE; // 'validate' | 'review' | undefined

  document.addEventListener('visibilitychange', function () {
    if (!startTime) return;
    if (document.hidden) {
      // Tab hidden: bank elapsed time, pause
      elapsed += Date.now() - startTime;
      startTime = null;
      hidden = true;
    } else {
      // Tab visible again: resume
      startTime = Date.now();
      hidden = false;
    }
  });

  // ── Ready modal ──────────────────────────────────────────────
  var modal = document.getElementById('ready-modal');
  var readyBtn = document.getElementById('ready-btn');
  var area = document.getElementById('annotation-area');

  function dismissModal() {
    modal.style.display = 'none';
    area.style.display = '';
    elapsed = 0;
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

  // ── Betacode → Unicode conversion ───────────────────────────
  var BETA_LETTERS = {
    a:'α',b:'β',g:'γ',d:'δ',e:'ε',z:'ζ',h:'η',q:'θ',i:'ι',
    k:'κ',l:'λ',m:'μ',n:'ν',c:'ξ',o:'ο',p:'π',r:'ρ',s:'σ',
    t:'τ',u:'υ',f:'φ',x:'χ',y:'ψ',w:'ω',v:'ϝ'
  };
  var BETA_DIA = {')':'̓','(':'̔','/':'́','\\':'̀','=':'͂','+':'̈','|':'ͅ'};
  // Greek punctuation inserted directly (not part of word conversion)
  var BETA_PUNCT = {':':'·', ';':';'}; // ano teleia · (U+0387), erotimatiko ; (U+037E)

  function betaToGreek(text) {
    var clusters = [], pendingUpper = false, pendingMarks = [];
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (ch === '*') { pendingUpper = true; pendingMarks = []; continue; }
      if (BETA_DIA[ch] !== undefined) {
        if (pendingUpper) pendingMarks.push(BETA_DIA[ch]);
        else if (clusters.length) clusters[clusters.length-1][1].push(BETA_DIA[ch]);
        continue;
      }
      var low = ch.toLowerCase();
      var base = BETA_LETTERS[low] !== undefined
        ? ((pendingUpper || ch !== low) ? BETA_LETTERS[low].toUpperCase() : BETA_LETTERS[low])
        : ch;
      clusters.push([base, pendingMarks.slice()]);
      pendingUpper = false; pendingMarks = [];
    }
    var s = clusters.map(function(c){ return c[0]+c[1].join(''); }).join('');
    s = s.replace(/σ(?![Ͱ-Ͽἀ-῿])/g, 'ς');
    return s.normalize('NFC');
  }

  // ── Save-edit button: dim until text changes ─────────────────
  if (mode === 'review') {
    var textField = document.getElementById('text-field');
    var saveBtn = document.getElementById('btn-save-edit');
    var betaToggle = document.getElementById('beta-toggle');
    if (textField && saveBtn) {
      var originalText = textField.value;
      var betaRaw = '';   // raw betacode buffer while toggle is on

      function updateSaveBtn() {
        var changed = textField.value !== originalText;
        saveBtn.classList.toggle('btn-primary', changed);
        saveBtn.classList.toggle('btn-muted', !changed);
      }
      updateSaveBtn();
      textField.addEventListener('input', function() {
        if (!betaToggle || !betaToggle.checked) updateSaveBtn();
      });

      // Betacode toggle
      if (betaToggle) {
        textField.addEventListener('keydown', function(e) {
          if (!betaToggle.checked) return;
          if (e.key === 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;

          var cursor = textField.selectionStart;

          if (e.key === 'Backspace') {
            e.preventDefault();
            if (betaRaw.length > 0) {
              // Remove last betacode char
              betaRaw = betaRaw.slice(0, -1);
            } else {
              // betaRaw exhausted — delete one Unicode char before cursor
              var v = textField.value;
              textField.value = v.slice(0, cursor - 1) + v.slice(cursor);
              textField.setSelectionRange(cursor - 1, cursor - 1);
              updateSaveBtn();
              return;
            }
          } else if (BETA_PUNCT[e.key] !== undefined) {
            // Greek punctuation: flush current word, insert punct, reset buffer
            e.preventDefault();
            var parts = textField.value.split(' ');
            parts[parts.length - 1] = betaToGreek(betaRaw) + BETA_PUNCT[e.key];
            betaRaw = '';
            textField.value = parts.join(' ');
            // move cursor to end of inserted punctuation
            textField.setSelectionRange(textField.value.length, textField.value.length);
            updateSaveBtn();
            return;
          } else if (e.key === ' ') {
            // Space: flush current betacode word, start fresh
            e.preventDefault();
            var parts2 = textField.value.split(' ');
            parts2[parts2.length - 1] = betaToGreek(betaRaw);
            betaRaw = '';
            textField.value = parts2.join(' ') + ' ';
            textField.setSelectionRange(textField.value.length, textField.value.length);
            updateSaveBtn();
            return;
          } else if (e.key.length === 1) {
            e.preventDefault();
            betaRaw += e.key;
          } else {
            return; // arrow keys etc. — don't intercept
          }

          // Re-render last word, preserving cursor position for earlier text
          var prefix = textField.value.lastIndexOf(' ') + 1; // start of last word
          var safeCursor = Math.min(cursor, prefix);         // keep cursor if before last word
          var parts3 = textField.value.split(' ');
          parts3[parts3.length - 1] = betaToGreek(betaRaw);
          textField.value = parts3.join(' ');
          // Restore cursor: if it was before the last word, keep it there; otherwise go to end
          var newPos = cursor <= prefix ? safeCursor : textField.value.length;
          textField.setSelectionRange(newPos, newPos);
          updateSaveBtn();
        });
        // When toggling on, seed betaRaw from current last word
        betaToggle.addEventListener('change', function() {
          if (betaToggle.checked) {
            var parts = textField.value.split(' ');
            betaRaw = parts[parts.length - 1];
          }
          var label = document.getElementById('beta-label');
          if (label) label.textContent = betaToggle.checked ? 'Betacode ON' : 'Betacode OFF';
          textField.focus();
        });

      // Help panel toggle
      var helpBtn = document.getElementById('beta-help-btn');
      var helpPanel = document.getElementById('beta-help');
      if (helpBtn && helpPanel) {
        helpBtn.addEventListener('click', function() {
          var hidden = helpPanel.hidden;
          helpPanel.hidden = !hidden;
          helpBtn.textContent = hidden ? '✕ close reference' : '? reference';
        });
      }
      }
    }
  }

  // ── Inject elapsed time on form submit ───────────────────────
  function writeElapsed() {
    var field = document.getElementById('elapsed-field');
    if (field) {
      field.value = ((elapsed + (startTime ? Date.now() - startTime : 0)) / 1000).toFixed(2);
    }
  }

  var form = document.getElementById('annotation-form');
  if (form) {
    form.addEventListener('submit', writeElapsed);
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
    writeElapsed();
    var btn = form.querySelector('button[value="' + action + '"]');
    if (btn) btn.click();
  }
})();
