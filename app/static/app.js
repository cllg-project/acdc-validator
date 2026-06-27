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
      var betaPending = ''; // pending modifier chars (*,),(/,\,=,+,|) awaiting base letter

      function updateSaveBtn() {
        var changed = textField.value !== originalText;
        saveBtn.classList.toggle('btn-primary', changed);
        saveBtn.classList.toggle('btn-muted', !changed);
      }
      updateSaveBtn();
      textField.addEventListener('input', function() { updateSaveBtn(); });

      // betaToGreek without σ→ς so we can insert σ and fix it at word boundaries
      function betaCharToGreek(raw) {
        var clusters = [], pendingUpper = false, pendingMarks = [];
        for (var i = 0; i < raw.length; i++) {
          var ch = raw[i];
          if (ch === '*') { pendingUpper = true; pendingMarks = []; continue; }
          if (BETA_DIA[ch] !== undefined) {
            if (pendingUpper) pendingMarks.push(BETA_DIA[ch]);
            else if (clusters.length) clusters[clusters.length - 1][1].push(BETA_DIA[ch]);
            continue;
          }
          var low = ch.toLowerCase();
          var base = BETA_LETTERS[low] !== undefined
            ? ((pendingUpper || ch !== low) ? BETA_LETTERS[low].toUpperCase() : BETA_LETTERS[low])
            : ch;
          clusters.push([base, pendingMarks.slice()]);
          pendingUpper = false; pendingMarks = [];
        }
        return clusters.map(function(c) { return c[0] + c[1].join(''); }).join('').normalize('NFC');
      }

      // Fix σ → ς when it sits immediately before the cursor (word boundary)
      function applyFinalSigma() {
        var pos = textField.selectionStart;
        if (pos > 0 && textField.value[pos - 1] === 'σ') {
          var v = textField.value;
          textField.value = v.slice(0, pos - 1) + 'ς' + v.slice(pos);
          textField.setSelectionRange(pos, pos);
        }
      }

      // Greek punctuation shortcuts — always active regardless of betacode mode
      textField.addEventListener('keydown', function(e) {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        if (betaToggle && betaToggle.checked) return; // handled inside betacode block below
        if (BETA_PUNCT[e.key] !== undefined) {
          e.preventDefault();
          var v = textField.value;
          var pos = textField.selectionStart;
          var ins = BETA_PUNCT[e.key];
          textField.value = v.slice(0, pos) + ins + v.slice(textField.selectionEnd);
          textField.setSelectionRange(pos + ins.length, pos + ins.length);
          updateSaveBtn();
        }
      });

      // Betacode toggle — character-by-character insertion; native Backspace handles deletion
      var BETA_MOD_KEYS = new Set([')', '(', '/', '\\', '=', '+', '|', '*']);
      if (betaToggle) {
        textField.addEventListener('keydown', function(e) {
          if (!betaToggle.checked) return;
          if (e.key === 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;

          if (e.key === 'Backspace') {
            betaPending = ''; // discard any dangling modifier
            return;           // let the browser delete the last inserted char
          }

          if (BETA_MOD_KEYS.has(e.key)) {
            betaPending += e.key;
            e.preventDefault();
            return;
          }

          if (e.key === ' ') {
            betaPending = '';
            applyFinalSigma(); // σ before space → ς
            // let the browser insert the space; input event will call updateSaveBtn
            return;
          }

          if (BETA_PUNCT[e.key] !== undefined) {
            e.preventDefault();
            betaPending = '';
            applyFinalSigma();
            var v = textField.value;
            var pos = textField.selectionStart;
            var ins = BETA_PUNCT[e.key];
            textField.value = v.slice(0, pos) + ins + v.slice(textField.selectionEnd);
            textField.setSelectionRange(pos + ins.length, pos + ins.length);
            updateSaveBtn();
            return;
          }

          if (e.key.length === 1) {
            e.preventDefault();
            var ch = betaCharToGreek(betaPending + e.key) || e.key;
            betaPending = '';
            var v2 = textField.value;
            var start = textField.selectionStart;
            var end = textField.selectionEnd;
            textField.value = v2.slice(0, start) + ch + v2.slice(end);
            textField.setSelectionRange(start + ch.length, start + ch.length);
            updateSaveBtn();
            return;
          }

          betaPending = ''; // arrow keys etc. — clear modifier and pass through
        });

        betaToggle.addEventListener('change', function() {
          betaPending = '';
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
    if (field && startTime !== null) {
      field.value = ((Date.now() - startTime) / 1000).toFixed(2);
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
