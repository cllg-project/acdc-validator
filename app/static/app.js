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
      // Start visible timer
      var timerEl = document.getElementById('timer');
      if (timerEl) {
        setInterval(function() {
          if (startTime === null) return;
          var s = Math.floor((Date.now() - startTime) / 1000);
          timerEl.textContent = '⏱ ' + Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2);
        }, 1000);
      }
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
  // Canonical order for polytonic Greek combining marks (breathing → diaeresis → accent → iota sub)
  var DIA_ORDER = {'̓':1,'̔':1,'̈':2,'́':3,'̀':3,'͂':3,'ͅ':4};
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
      var betaPending = ''; // pending uppercase flag (*) for next letter

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
            if (pendingUpper || clusters.length === 0) pendingMarks.push(BETA_DIA[ch]);
            else clusters[clusters.length - 1][1].push(BETA_DIA[ch]);
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

      // Returns true for Unicode combining diacritical marks (U+0300–U+036F)
      function isCombining(cp) { return cp >= 0x0300 && cp <= 0x036F; }

      // Apply a combining diacritic to the grapheme cluster immediately before the cursor.
      // Toggles the mark off if already present; always reorders marks into canonical form
      // (breathing → diaeresis → accent → iota subscript) so NFC produces precomposed chars.
      function applyDia(dia) {
        if (textField.selectionStart !== textField.selectionEnd) return;
        var pos = textField.selectionStart;
        var before = textField.value.slice(0, pos);
        if (!before.length) return;
        var nfd = before.normalize('NFD');
        var i = nfd.length - 1;
        while (i >= 0 && isCombining(nfd.charCodeAt(i))) i--;
        if (i < 0) return;
        var base   = nfd[i];
        var marks  = nfd.slice(i + 1).split('');
        var idx = marks.indexOf(dia);
        if (idx >= 0) marks.splice(idx, 1);
        else marks.push(dia);
        marks.sort(function(a, b) { return (DIA_ORDER[a] || 99) - (DIA_ORDER[b] || 99); });
        var newBefore = (nfd.slice(0, i) + base + marks.join('')).normalize('NFC');
        textField.value = newBefore + textField.value.slice(pos);
        textField.setSelectionRange(newBefore.length, newBefore.length);
        updateSaveBtn();
      }

      // Convert the previous grapheme cluster (or the selection) to upper/lowercase.
      function convertCase(toUpper) {
        var start = textField.selectionStart;
        var end   = textField.selectionEnd;
        if (start !== end) {
          var sel  = textField.value.slice(start, end);
          var conv = toUpper ? sel.toUpperCase() : sel.toLowerCase();
          textField.value = textField.value.slice(0, start) + conv + textField.value.slice(end);
          textField.setSelectionRange(start, start + conv.length);
        } else {
          if (!start) return;
          var nfd = textField.value.slice(0, start).normalize('NFD');
          var i = nfd.length - 1;
          while (i >= 0 && isCombining(nfd.charCodeAt(i))) i--;
          if (i < 0) return;
          var conv = toUpper
            ? (nfd.slice(0, i) + nfd.slice(i).toUpperCase())
            : (nfd.slice(0, i) + nfd.slice(i).toLowerCase());
          var newBefore = conv.normalize('NFC');
          textField.value = newBefore + textField.value.slice(start);
          textField.setSelectionRange(newBefore.length, newBefore.length);
        }
        updateSaveBtn();
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

      // Betacode toggle — diacritics apply to the previous letter; * makes next letter uppercase
      if (betaToggle) {
        textField.addEventListener('keydown', function(e) {
          if (!betaToggle.checked) return;
          if (e.key === 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;

          if (e.key === 'Backspace') {
            betaPending = '';
            return;
          }

          // Diacritics: apply retroactively to the previous letter
          if (BETA_DIA[e.key] !== undefined) {
            e.preventDefault();
            betaPending = '';
            applyDia(BETA_DIA[e.key]);
            return;
          }

          // * buffers for the next letter (uppercase)
          if (e.key === '*') {
            betaPending = '*';
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
          if (label) label.textContent = betaToggle.checked ? 'ON' : 'off';
          var pill = document.getElementById('beta-pill-track');
          if (pill) pill.classList.toggle('beta-on', betaToggle.checked);
          textField.focus();
        });

        document.addEventListener('keydown', function(e) {
          if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            betaToggle.checked = !betaToggle.checked;
            betaToggle.dispatchEvent(new Event('change'));
          }
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

      // Char-insert bar
      function insertCharAt(ch) {
        var start = textField.selectionStart;
        var end   = textField.selectionEnd;
        textField.value = textField.value.slice(0, start) + ch + textField.value.slice(end);
        textField.setSelectionRange(start + ch.length, start + ch.length);
        textField.focus();
        updateSaveBtn();
      }

      document.querySelectorAll('.char-btn').forEach(function(btn) {
        btn.addEventListener('mousedown', function(e) {
          e.preventDefault(); // keep textarea focus
          if (btn.hasAttribute('data-ch'))  insertCharAt(btn.getAttribute('data-ch'));
          else if (btn.hasAttribute('data-dia')) applyDia(btn.getAttribute('data-dia'));
        });
      });


      // Strip-action buttons
      function stripMarks(marks) {
        var s = textField.value.normalize('NFD');
        marks.forEach(function(cp) { s = s.split(cp).join(''); });
        textField.value = s.normalize('NFC');
        updateSaveBtn();
      }

      var btnStripAccents = document.getElementById('btn-strip-accents');
      var btnStripSpirits = document.getElementById('btn-strip-spirits');
      var btnStripNumbers = document.getElementById('btn-strip-numbers');
      if (btnStripAccents) {
        btnStripAccents.addEventListener('click', function() {
          stripMarks(['́', '̀', '͂']);
        });
      }
      if (btnStripSpirits) {
        btnStripSpirits.addEventListener('click', function() {
          stripMarks(['̓', '̔']);
        });
      }
      if (btnStripNumbers) {
        btnStripNumbers.addEventListener('click', function() {
          textField.value = textField.value.replace(/\s\d+\.?\s/g, ' ');
          updateSaveBtn();
        });
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
      if (e.key === 'x' || e.key === 'X') submitAction('rejected');
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
