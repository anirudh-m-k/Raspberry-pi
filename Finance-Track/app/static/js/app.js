/**
 * Global JavaScript - Theme toggle, sidebar toggle, user menu, auth check
 * NOTE: JWT is stored in localStorage. For production, migrate to HttpOnly cookies.
 */

// HTML escaping utility to prevent XSS (SECURITY: XSS-01 fix)
function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// Toast notification system
function showToast(message, type = 'info', duration = 3500) {
    // Ensure toast container exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;top:1.25rem;right:1.25rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;max-width:360px;pointer-events:none;';
        document.body.appendChild(container);
    }

    const colors = {
        success: { bg: '#10b981', icon: '✓' },
        error:   { bg: '#ef4444', icon: '✕' },
        warning: { bg: '#f59e0b', icon: '⚠' },
        info:    { bg: '#6366f1', icon: 'ℹ' },
    };
    const { bg, icon } = colors[type] || colors.info;

    const toast = document.createElement('div');
    toast.style.cssText = `
        display:flex;align-items:center;gap:0.75rem;
        background:${bg};color:#fff;
        padding:0.75rem 1rem;border-radius:0.625rem;
        box-shadow:0 4px 24px rgba(0,0,0,0.18);
        font-size:0.875rem;font-weight:500;
        pointer-events:auto;
        opacity:0;transform:translateX(1rem);
        transition:opacity 0.25s ease,transform 0.25s ease;
        font-family:inherit;
    `;
    toast.innerHTML = `<span style="flex-shrink:0;font-size:1rem;line-height:1">${icon}</span><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        });
    });

    // Auto-remove
    const removeToast = () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(1rem)';
        setTimeout(() => toast.remove(), 280);
    };
    setTimeout(removeToast, duration);
    toast.addEventListener('click', removeToast);
}

// Theme Management
function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    applyTheme(saved);
}

function applyTheme(theme) {
    const html = document.documentElement;
    const lightIcon = document.getElementById('theme-icon-light');
    const darkIcon = document.getElementById('theme-icon-dark');

    if (theme === 'dark') {
        html.classList.add('dark');
        if (lightIcon) lightIcon.classList.remove('hidden');
        if (darkIcon) darkIcon.classList.add('hidden');
    } else {
        html.classList.remove('dark');
        if (lightIcon) lightIcon.classList.add('hidden');
        if (darkIcon) darkIcon.classList.remove('hidden');
    }

    localStorage.setItem('theme', theme);
}

function toggleTheme() {
    const current = localStorage.getItem('theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

// Sidebar Management
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (sidebar) {
        sidebar.classList.toggle('-translate-x-full');
    }
    if (overlay) {
        overlay.classList.toggle('hidden');
    }
}

// User Menu
function toggleUserMenu() {
    const menu = document.getElementById('user-menu');
    if (menu) {
        menu.classList.toggle('hidden');
    }
}

// Close user menu when clicking outside
document.addEventListener('click', function(e) {
    const menu = document.getElementById('user-menu');
    const button = e.target.closest('[onclick="toggleUserMenu()"]');
    if (menu && !menu.contains(e.target) && !button) {
        menu.classList.add('hidden');
    }
});

// Active sidebar link
function setActiveSidebarLink() {
    const path = window.location.pathname;
    const links = document.querySelectorAll('.sidebar-link');

    links.forEach(link => {
        const href = link.getAttribute('href');
        if (path === href || (href !== '/dashboard' && path.startsWith(href))) {
            link.classList.remove('sidebar-link');
            link.classList.add('sidebar-link-active');
        } else {
            link.classList.remove('sidebar-link-active');
            link.classList.add('sidebar-link');
        }
    });
}

// Set page title
function setPageTitle(title) {
    const el = document.getElementById('page-title');
    if (el) {
        el.textContent = title;
    }
    document.title = `${title} - FinanceTrack`;
}

// User info in topbar
function initUserInfo() {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const avatarEl = document.getElementById('user-avatar');
    const nameEl = document.getElementById('user-name');
    const emailEl = document.getElementById('user-email');

    if (user.name && avatarEl) {
        avatarEl.querySelector('span').textContent = user.name.charAt(0).toUpperCase();
    }
    if (user.name && nameEl) {
        nameEl.textContent = user.name;
    }
    if (user.email && emailEl) {
        emailEl.textContent = user.email;
    }

    // Show admin nav link for admin users
    const adminNavLink = document.getElementById('admin-nav-link');
    if (adminNavLink && user.role === 'admin') {
        adminNavLink.classList.remove('hidden');
    }
}

// Logout
async function logout() {
    try {
        await api.post('/auth/logout');
    } catch (e) {
        // Ignore logout API errors
    }
    api.removeToken();
    window.location.href = '/login';
}

// Per-card Amount Visibility (Eye Button)
// Each card has its own eye button. Clicking toggles the amount text in that card.
// State is persisted in localStorage per button data-eye-id.
// Default state: HIDDEN (amounts masked until user clicks eye)

function isEyeHidden(btn) {
    const id = btn.getAttribute('data-eye-id');
    // Default to hidden if no stored preference
    const stored = localStorage.getItem(`eye_${id}`);
    return stored === null ? true : stored === 'true';
}

function toggleCardVisibility(btn) {
    const id = btn.getAttribute('data-eye-id');
    if (!id) return;
    const hidden = isEyeHidden(btn);
    localStorage.setItem(`eye_${id}`, !hidden);
    applyCardVisibility(btn, !hidden);
}

function applyCardVisibility(btn, hidden) {
    const card = btn.closest('.card, .card-hover');
    if (!card) return;

    const eyeOpen = btn.querySelector('.eye-open');
    const eyeClosed = btn.querySelector('.eye-closed');

    // Find the amount element - look for bold text elements that look like currency
    const amountEl = card.querySelector('.font-bold.text-lg, .font-bold.text-xl, .font-bold.text-2xl, .font-bold.text-3xl');
    if (!amountEl) return;

    const currentText = amountEl.textContent.trim();
    if (currentText !== '••••••' && currentText !== '-' && currentText !== '₹0.00') {
        amountEl.dataset.original = currentText;
    }

    if (hidden) {
        amountEl.textContent = '••••••';
        if (eyeOpen) eyeOpen.classList.add('hidden');
        if (eyeClosed) eyeClosed.classList.remove('hidden');
    } else {
        const originalVal = amountEl.dataset.original;
        if (originalVal && originalVal !== '••••••') {
            amountEl.textContent = originalVal;
        } else if (currentText !== '••••••') {
            amountEl.textContent = currentText;
        }
        if (eyeOpen) eyeOpen.classList.remove('hidden');
        if (eyeClosed) eyeClosed.classList.add('hidden');
    }
}

function initAmountVisibility() {
    document.querySelectorAll('.eye-btn[data-eye-id]').forEach(btn => {
        applyCardVisibility(btn, isEyeHidden(btn));
    });
}

// Format currency (simple)
function formatCurrency(amount, symbol = '₹') {
    const value = parseFloat(amount);
    return `${symbol}${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Format date
function formatDate(dateStr, format = 'short') {
    const date = new Date(dateStr);
    if (format === 'short') {
        return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    }
    if (format === 'long') {
        return date.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    return date.toLocaleDateString('en-IN');
}

// Compress an image client-side (canvas -> JPEG) to reduce upload size.
// Returns a Promise<Blob>. Original pixels are kept up to maxDimension;
// larger images are downscaled so clarity is preserved on screen.
async function compressImage(file, { maxDimension = 2560, quality = 0.9 } = {}) {
    if (!file || !file.type.startsWith('image/')) {
        return file;
    }

    const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });

    const img = await new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('Failed to load image'));
        image.src = dataUrl;
    });

    const scale = Math.min(1, maxDimension / Math.max(img.width, img.height));
    const width = Math.round(img.width * scale);
    const height = Math.round(img.height * scale);

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, width, height);

    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (blob) {
                const compressed = new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' });
                resolve(compressed);
            } else {
                resolve(file);
            }
        }, 'image/jpeg', quality);
    });
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Disable browser autocomplete/recommendation popups across all input fields
function disableAutocompleteRecommendations() {
    document.querySelectorAll('form').forEach(f => f.setAttribute('autocomplete', 'off'));
    document.querySelectorAll('input, select, textarea').forEach(el => {
        const type = el.getAttribute('type');
        if (type !== 'hidden' && type !== 'checkbox' && type !== 'radio' && type !== 'file' && type !== 'color') {
            el.setAttribute('autocomplete', 'off');
        }
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    setActiveSidebarLink();
    initUserInfo();
    initAmountVisibility();
    disableAutocompleteRecommendations();
});

// Also re-run on focus to catch any dynamically injected modal/dynamic inputs
document.addEventListener('focusin', function(e) {
    if (e.target && e.target.tagName === 'INPUT') {
        const type = e.target.getAttribute('type');
        if (type !== 'hidden' && type !== 'checkbox' && type !== 'radio' && type !== 'file' && type !== 'color') {
            e.target.setAttribute('autocomplete', 'off');
        }
    }
});
