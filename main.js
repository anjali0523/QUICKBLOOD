/* QUICKBLOOD Interactive JavaScript Engine */

document.addEventListener('DOMContentLoaded', () => {
    initAvailabilityToggle();
    initDashboardTabs();
    initModalSystem();
    initCompatibilityTool();
    initFilterAutoSubmit();
});

/**
 * Handle donor availability toggle switch via AJAX
 */
function initAvailabilityToggle() {
    const toggleBtn = document.getElementById('toggle-avail-btn');
    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', async () => {
        toggleBtn.disabled = true;

        try {
            const response = await fetch('/api/toggle-availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await response.json();

            if (data.success) {
                const statusBadge = document.getElementById('user-status-badge');
                const statusText = document.getElementById('user-status-text');

                if (statusBadge && statusText) {
                    statusText.textContent = data.status_text;
                    if (data.is_available) {
                        statusBadge.className = 'status-badge status-available';
                        toggleBtn.className = 'btn btn-outline btn-sm';
                        toggleBtn.innerHTML = '<i class="fas fa-toggle-on"></i> <span>Set to Unavailable</span>';
                    } else {
                        statusBadge.className = 'status-badge status-unavailable';
                        toggleBtn.className = 'btn btn-primary btn-sm';
                        toggleBtn.innerHTML = '<i class="fas fa-toggle-off"></i> <span>Set to Available (Ready)</span>';
                    }
                }
                showToast(data.message, 'success');
            } else {
                showToast(data.message || 'Failed to update status', 'danger');
            }
        } catch (err) {
            console.error(err);
            showToast('Network error while updating status', 'danger');
        } finally {
            toggleBtn.disabled = false;
        }
    });
}

/**
 * Dashboard Tabs Controller
 */
function initDashboardTabs() {
    const tabBtns = document.querySelectorAll('.dash-tab-btn');
    if (!tabBtns.length) return;

    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTabId = btn.getAttribute('data-tab');
            if (!targetTabId) return;

            // Deactivate all tab buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Deactivate all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });

            // Activate target tab content
            const targetContent = document.getElementById(targetTabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });
}

/**
 * Modal System Controller
 */
function initModalSystem() {
    const modalTriggers = document.querySelectorAll('[data-modal-target]');
    modalTriggers.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute('data-modal-target');
            const modal = document.getElementById(targetId);
            if (modal) {
                modal.classList.add('active');
            }
        });
    });

    const closeBtns = document.querySelectorAll('.modal-close, [data-modal-close]');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const modal = btn.closest('.modal-backdrop');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });

    // Close on clicking backdrop outside modal-box
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.classList.remove('active');
            }
        });
    });

    // Close on Escape key press
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-backdrop.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });
}

/**
 * Blood Compatibility Matcher
 */
function initCompatibilityTool() {
    const bgSelect = document.getElementById('calc-blood-group');
    const resultBox = document.getElementById('calc-result');
    if (!bgSelect || !resultBox) return;

    const compatData = {
        'A+': { can_receive: ['A+', 'A-', 'O+', 'O-'], can_donate: ['A+', 'AB+'] },
        'A-': { can_receive: ['A-', 'O-'], can_donate: ['A+', 'A-', 'AB+', 'AB-'] },
        'B+': { can_receive: ['B+', 'B-', 'O+', 'O-'], can_donate: ['B+', 'AB+'] },
        'B-': { can_receive: ['B-', 'O-'], can_donate: ['B+', 'B-', 'AB+', 'AB-'] },
        'AB+': { can_receive: ['ALL (Universal Recipient)'], can_donate: ['AB+'] },
        'AB-': { can_receive: ['AB-', 'A-', 'B-', 'O-'], can_donate: ['AB+', 'AB-'] },
        'O+': { can_receive: ['O+', 'O-'], can_donate: ['O+', 'A+', 'B+', 'AB+'] },
        'O-': { can_receive: ['O- (Universal Donor)'], can_donate: ['ALL (Universal Donor)'] }
    };

    bgSelect.addEventListener('change', () => {
        const bg = bgSelect.value;
        if (!bg || !compatData[bg]) {
            resultBox.style.display = 'none';
            return;
        }

        const info = compatData[bg];
        resultBox.style.display = 'block';
        resultBox.innerHTML = `
            <div style="margin-top: 1rem; padding: 1rem; background: rgba(230,57,70,0.1); border-radius: 8px; border: 1px solid rgba(230,57,70,0.3);">
                <h5 style="color: var(--accent-red); margin-bottom: 0.5rem; font-weight:700;">Blood Group ${bg} Compatibility</h5>
                <p style="font-size:0.9rem; margin-bottom: 0.3rem;"><strong>Can Receive Blood From:</strong> ${info.can_receive.join(', ')}</p>
                <p style="font-size:0.9rem;"><strong>Can Donate Blood To:</strong> ${info.can_donate.join(', ')}</p>
            </div>
        `;
    });
}

/**
 * Filter auto submit on dropdown change
 */
function initFilterAutoSubmit() {
    const filterSelects = document.querySelectorAll('.auto-submit');
    filterSelects.forEach(select => {
        select.addEventListener('change', () => {
            select.closest('form').submit();
        });
    });
}

/**
 * Toast Notification helper
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert-box alert-${type}`;
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.zIndex = '3500';
    toast.style.boxShadow = '0 12px 35px rgba(0,0,0,0.6)';
    toast.style.maxWidth = '420px';
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-circle-check' : type === 'danger' ? 'fa-triangle-exclamation' : 'fa-info-circle'}"></i> <span>${message}</span>`;
    
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}
