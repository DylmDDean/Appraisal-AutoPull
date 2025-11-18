// static/save_email.js
// Minimal front-end for saving a user's contact email.
// POSTs JSON to /save_email and shows friendly messages.

(function() {
  const emailInput = document.getElementById('email-input');
  const nameInput = document.getElementById('name-input');
  const optinCheckbox = document.getElementById('optin-checkbox');
  const saveBtn = document.getElementById('save-email-btn');
  const msg = document.getElementById('save-email-message');

  // If those elements don't exist on the page, do nothing.
  if (!saveBtn || !emailInput || !msg) return;

  function showMessage(text, isError) {
    msg.textContent = text;
    msg.style.color = isError ? '#b00020' : '#166534';
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

    saveBtn.disabled = true;
    const prevText = saveBtn.textContent;
    showMessage('Sending confirmation — check your inbox...', false);
    saveBtn.textContent = 'Sending…';

    try {
      const resp = await fetch('/save_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, name: name, opt_in: opt_in })
      });

      let data;
      try {
        data = await resp.json();
      } catch (e) {
        data = null;
      }

      if (resp.ok && data && data.success) {
        // store locally for convenience
        try { localStorage.setItem('saved_email', email); } catch(e) {}
        showMessage('Verification email sent. Click the link in your inbox to confirm.', false);
        saveBtn.textContent = 'Saved';
      } else {
        // Respect returned message or fallback messages
        const errorMsg = data && (data.error || data.message) ? (data.error || data.message) : 'Failed to send verification.';
        showMessage(errorMsg, true);
        saveBtn.textContent = prevText;
      }
    } catch (err) {
      console.error('save_email error', err);
      showMessage('Network error. Try again in a moment.', true);
      saveBtn.textContent = prevText;
    } finally {
      saveBtn.disabled = false;
    }
  }

  saveBtn.addEventListener('click', function (ev) {
    ev.preventDefault();
    handleSave();
  });

  // Pre-fill saved email if present
  try {
    const saved = localStorage.getItem('saved_email');
    if (saved && !emailInput.value) emailInput.value = saved;
  } catch(e){}
})();