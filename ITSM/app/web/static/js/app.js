// ITSM Platform - Main JavaScript

// API Configuration
const API_BASE = '/api';
const ACCESS_TOKEN_KEY = 'access_token';

// Get stored token
function getToken() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
}

// Set token
function setToken(token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

// Handle SSO tokens from URL
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');
    const refreshToken = urlParams.get('refresh_token');
    if (accessToken) {
        setToken(accessToken);
        if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
        }
        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
})();

// Clear token
function clearToken() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
}

// Check if user is logged in
function isLoggedIn() {
    return !!getToken();
}

// Redirect to login if not authenticated
function redirectIfNotAuthenticated() {
    if (!isLoggedIn() && !window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
        window.location.href = '/login';
    }
}

// Setup HTMX default headers
htmx.config.defaultHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`
};

// Show toast notification
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast fade show`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    const bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-info';

    toast.innerHTML = `
        <div class="toast-header ${bgClass} text-white">
            <strong class="me-auto">ITSM Platform</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;

    toastContainer.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Format date
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Format time
function formatTime(dateString) {
    return new Date(dateString).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// API request helper
async function apiRequest(method, endpoint, data = null) {
    const url = `${API_BASE}${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        }
    };

    if (data && (method === 'POST' || method === 'PATCH' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);

        if (response.status === 401) {
            clearToken();
            window.location.href = '/login';
            return null;
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast(error.message, 'error');
        return null;
    }
}

// Setup stat card click handlers
function setupStatCardHandlers() {
    const assetCard = document.querySelector('.stat-assets');
    const licenseCard = document.querySelector('.stat-licenses');
    const problemCard = document.querySelector('.stat-problems');
    const changeCard = document.querySelector('.stat-changes');

    if (assetCard && !assetCard.hasClickHandler) {
        assetCard.addEventListener('click', () => window.location.href = '/assets');
        assetCard.hasClickHandler = true;
    }
    if (licenseCard && !licenseCard.hasClickHandler) {
        licenseCard.addEventListener('click', () => window.location.href = '/licenses');
        licenseCard.hasClickHandler = true;
    }
    if (problemCard && !problemCard.hasClickHandler) {
        problemCard.addEventListener('click', () => window.location.href = '/problems');
        problemCard.hasClickHandler = true;
    }
    if (changeCard && !changeCard.hasClickHandler) {
        changeCard.addEventListener('click', () => window.location.href = '/changes');
        changeCard.hasClickHandler = true;
    }
}

// Event handlers
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication on page load
    redirectIfNotAuthenticated();

    setupStatCardHandlers();

    // Load current user profile for navbar
    if (isLoggedIn()) {
        loadCurrentUser();
    }

    // Setup HTMX event handlers
    htmx.on('htmx:beforeRequest', function(event) {
        // Update authorization header
        event.detail.xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`);
    });

    htmx.on('htmx:responseError', function(event) {
        if (event.detail.xhr.status === 401) {
            clearToken();
            window.location.href = '/login';
        } else {
            showToast('An error occurred', 'error');
        }
    });
});

// Log out
function logout() {
    clearToken();
    window.location.href = '/login';
}

// Store current user globally
window.currentUser = null;

// Load current user for navbar and permissions
async function loadCurrentUser() {
    const user = await apiRequest('GET', '/auth/me');
    if (user) {
        window.currentUser = user;
        
        const nameEl = document.getElementById('navbarAccountName');
        const iconEl = document.getElementById('navbarAccountIcon');
        
        if (nameEl) nameEl.textContent = user.full_name || user.username;
        
        if (iconEl && user.profile_image) {
            iconEl.innerHTML = `<img src="${user.profile_image}" alt="User" class="rounded-circle me-1" style="width: 24px; height: 24px; object-fit: cover; border: 1px solid #dee2e6;">`;
        }
        
        // Dispatch event for components that need user permissions (like sidebar)
        document.dispatchEvent(new CustomEvent('userLoaded', { detail: user }));
    }
}

// Export functions for use in templates
window.itsm = {
    getToken,
    setToken,
    clearToken,
    isLoggedIn,
    showToast,
    formatDate,
    formatTime,
    apiRequest,
    logout
};
