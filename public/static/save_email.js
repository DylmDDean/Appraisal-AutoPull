// public/static/save_email.js
// Minimal front-end for saving a user's contact email.
// POSTs JSON to /save_email and shows friendly messages.
// This file is CSP-safe (no eval/new Function/setTimeout(string)). It waits for
// DOMContentLoaded, validates email, uses AbortController timeout, and handles
// non-JSON responses gracefully.

(function () {
  document.addEventListener('DOMContentLoaded', function () {
    const emailInput = document.getElementById('email-input');
    const nameInput = document.getElementById('name-input');
    const optinCheckbox = document.getElementById('optin-checkbox');
    const saveBtn = document.getElementById('save-email-btn');
    const msg = document.getElementById('save-email-message');

    // If required elements don't exist on the page, do nothing.
    if (!saveBtn || !emailInput || !msg) return;

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const DEFAULT_TIMEOUT_MS = 15000;

    function showMessage(text, isError = false) {
      msg.textContent = text;
      msg.style.color = isError ? '#b00020' : '#166534';
    }

    function setButtonLoading(isLoading, loadingText = 'Sending…') {
      if (isLoading) {
        saveBtn.disabled = true;
        saveBtn.dataset.prevText = saveBtn.textContent;
        saveBtn.textContent = loadingText;
      } else {
        saveBtn.disabled = false;
        if (saveBtn.dataset.prevText) {
          saveBtn.textContent = saveBtn.dataset.prevText;
          delete saveBtn.dataset.prevText;
        }
      }
    }

    async function handleSave() {
      const email = (emailInput.value || '').trim();
      const name = (nameInput && nameInput.value) ? nameInput.value.trim() : '';
      const opt_in = (optinCheckbox && optinCheckbox.checked) ? true : false;

      if (!email) {
        showMessage('Please enter your email.', true);
        emailInput.focus();
        return;
      }

      if (!EMAIL_RE.test(email)) {
        showMessage('Please enter a valid email address.', true);
        emailInput.focus();
        return;
      }

      // Prevent double submit if already in-flight
      if (saveBtn.disabled) return;

      setButtonLoading(true);
      showMessage('Sending confirmation — check your inbox...', false);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

      try {
        const resp = await fetch('/save_email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email, name: name, opt_in: opt_in }),
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        // Try to parse JSON if possible, but handle non-JSON too
        let data = null;
        const text = await resp.text();
        try {
          data = text ? JSON.parse(text) : null;
        } catch (err) {
          // non-JSON response, keep raw text in `text`
        }

        if (resp.ok) {
          if (data && data.success) {
            try { localStorage.setItem('saved_email', email); } catch (e) { /* ignore */ }
            showMessage('Verification email sent. Click the link in your inbox to confirm.', false);
            saveBtn.textContent = 'Saved';
            setTimeout(() => setButtonLoading(false), 1000);
          } else {
            const fallbackMsg = (data && (data.message || data.error)) ? (data.message || data.error) : 'Verification sent (no success flag returned).';
            showMessage(fallbackMsg, false);
            setButtonLoading(false);
          }
        } else {
          const serverMsg = data && (data.error || data.message) ? (data.error || data.message) : text || `Server returned ${resp.status}`;
          showMessage(serverMsg, true);
          setButtonLoading(false);
        }
      } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          showMessage('Request timed out. Try again in a moment.', true);
        } else {
          console.error('save_email error', err);
          showMessage('Network error. Try again in a moment.', true);
        }
        setButtonLoading(false);
      }
    }

    // Support click and Enter key when focus is in an input
    saveBtn.addEventListener('click', function (ev) {
      ev.preventDefault();
      handleSave();
    });

    // Submit on Enter from email or name input
    [emailInput, nameInput].forEach(function (el) {
      if (!el) return;
      el.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          handleSave();
        }
      });
    });

    // Pre-fill saved email if present
    try {
      const saved = localStorage.getItem('saved_email');
      if (saved && !emailInput.value) emailInput.value = saved;
    } catch (e) {
      // ignore localStorage errors (e.g., disabled)
    }
  });
})();
