# Javascript Rendering Fix

I've fixed one final silent Javascript error. The frontend Javascript engine was crashing when it attempted to execute `.toUpperCase()` on an undefined string inside one of the records, because Javascript handles null values differently than Python.

I wrote a highly defensive rendering wrapper around the variables in `ITSM/app/web/templates/admin/ad_users.html`. It will now safely display all 254 active users.

Because this fix was purely in the HTML/Javascript template file, you **do not** need to restart your terminal! Just do a hard-refresh (`Ctrl + Shift + R`) on the web page: **http://localhost:8000/admin/ad-users**.