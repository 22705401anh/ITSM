# AD Page Fix

The API actually was working correctly and returning 254 active users. The reason the user interface was getting stuck was completely formatting-related from the data coming back from the AD server.

## What Was Fixed

1. Active Directory returns `[]` or `"None"` strings for empty fields when parsing natively. I've updated the backend in `ITSM/app/api/admin.py` to properly clean these fields up and return clean empty strings. 
2. Active Directory includes hidden "machine account" users (who end with `$`, like `KOSTALROOT$`). The javascript explicitly filters these un-needed machine profiles out so that you only see humans.
3. Updated the frontend template to properly respect these cleaned-up properties and fix the search function.

If you refresh the web page right now at **http://localhost:8000/admin/ad-users**, the active directory users list will perfectly display all the Kostal employees correctly!