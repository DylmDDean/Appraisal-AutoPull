/**
 * save_email.js - Frontend script for email capture and verification
 * Handles user email input, sends to backend, and provides user-friendly feedback
 */

document.addEventListener('DOMContentLoaded', function() {
    const emailInput = document.getElementById('email-input');
    const saveButton = document.getElementById('save-email-btn');
    
    if (!emailInput || !saveButton) {
        console.warn('Email capture elements not found on page');
        return;
    }
    
    // Load saved email from localStorage if available
    const savedEmail = localStorage.getItem('userEmail');
    if (savedEmail) {
        emailInput.value = savedEmail;
    }
    
    // Handle save button click
    saveButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        const email = emailInput.value.trim();
        
        // Basic email validation
        if (!email) {
            alert('Please enter your email address.');
            emailInput.focus();
            return;
        }
        
        if (!isValidEmail(email)) {
            alert('Please enter a valid email address.');
            emailInput.focus();
            return;
        }
        
        // Disable button during request
        saveButton.disabled = true;
        saveButton.textContent = 'Sending...';
        
        // Send email to backend
        saveEmail(email);
    });
    
    // Allow Enter key to submit
    emailInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            saveButton.click();
        }
    });
});

/**
 * Validate email format using a simple regex
 */
function isValidEmail(email) {
    // Simple but effective email regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Send email to backend for verification
 */
function saveEmail(email) {
    const saveButton = document.getElementById('save-email-btn');
    
    fetch('/save_email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email })
    })
    .then(response => response.json())
    .then(data => {
        // Re-enable button
        saveButton.disabled = false;
        saveButton.textContent = 'Save My Email';
        
        if (data.success) {
            // Save to localStorage on success
            localStorage.setItem('userEmail', email);
            
            alert('✓ Success! Please check your email for a verification link.');
            
            // Clear the input
            document.getElementById('email-input').value = '';
        } else {
            // Show error message
            alert('Error: ' + (data.message || 'Failed to save email. Please try again.'));
        }
    })
    .catch(error => {
        // Re-enable button
        saveButton.disabled = false;
        saveButton.textContent = 'Save My Email';
        
        console.error('Error saving email:', error);
        alert('Network error. Please check your connection and try again.');
    });
}
