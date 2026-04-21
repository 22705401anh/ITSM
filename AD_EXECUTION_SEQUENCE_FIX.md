# Execution Sequence Fix

I completely dropped the `DOMContentLoaded` event listener and moved to direct inline execution of the `loadADUsers()` function.

Because your application uses a dynamic page-loading framework (like HTMX) to load HTML content, the "DOM Loaded" event in the browser actually already occurred long ago when you first logged into the ITSM app. As a result, the `DOMContentLoaded` event listener never triggered because it was already too late!

### The Exact Fix
I replaced the event listener at the very bottom of the script with a direct synchronous Javascript function call inside the template:
```javascript
// BEFORE (Wait for a page load event that never comes)
document.addEventListener('DOMContentLoaded', loadADUsers);

// AFTER (Execute immediately when the template injection finishes)
loadADUsers();
```

**You DO NOT need to restart the server!**

Just perform a hard-refresh (`Ctrl + F5` or `Ctrl + Shift + R`) on **http://localhost:8000/admin/ad-users**. It will now forcefully trigger the loading command sequence without waiting for the browser's DOM event cycle.