/**
 * Sidebar Toggle Functionality
 * Allows users to expand/collapse the sidebar
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Sidebar toggle script loaded');

    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');

    console.log('Sidebar element:', sidebar);
    console.log('Toggle button element:', sidebarToggle);

    if (!sidebar) {
        console.error('Sidebar element not found!');
        return;
    }

    if (!sidebarToggle) {
        console.error('Sidebar toggle button not found!');
        return;
    }

    // Get stored preference from localStorage
    const isSidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    console.log('Sidebar collapsed preference:', isSidebarCollapsed);

    // Initialize sidebar state on page load
    if (isSidebarCollapsed) {
        collapseSidebar();
    } else {
        expandSidebar();
    }

    // Toggle functionality for button
    sidebarToggle.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('Toggle button clicked');
        console.log('Current state - collapsed:', sidebar.classList.contains('sidebar-collapsed'));

        if (sidebar.classList.contains('sidebar-collapsed')) {
            expandSidebar();
        } else {
            collapseSidebar();
        }
    });

    function collapseSidebar() {
        console.log('Collapsing sidebar');
        sidebar.classList.remove('sidebar-expanded');
        sidebar.classList.add('sidebar-collapsed');
        document.body.classList.add('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'true');
    }

    function expandSidebar() {
        console.log('Expanding sidebar');
        sidebar.classList.remove('sidebar-collapsed');
        sidebar.classList.add('sidebar-expanded');
        document.body.classList.remove('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'false');
    }

    // Update active nav link based on current URL
    updateActiveNavLink();

    function updateActiveNavLink() {
        const currentUrl = window.location.pathname;
        const navLinks = document.querySelectorAll('.sidebar .nav-link');

        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentUrl || (href !== '/' && currentUrl.startsWith(href))) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }
});

