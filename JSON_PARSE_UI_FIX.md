# The Front-End Code Was Attempting to "Double Parse" JSON

I found the issue. The browser was getting stuck on "Loading Active Directory..." because there was a JavaScript error silently failing in the background.

In the file `ad_users.html`, the frontend JavaScript was accidentally calling `.json()` on the response twice in the error checking block which JavaScript does not allow (the response stream gets consumed). 

## What I Changed
```javascript
// BEFORE (Buggy)
const error = await response.json(); // Consumes the stream
allUsers = await response.json(); // Crashes! Stream already consumed.

// AFTER (Fixed)
const rawData = await response.json();
allUsers = rawData.filter(u => u.username && u.name);
```

## What you need to do now
Your server crashed again a moment ago. Please go to your terminal and start the app one more time:

```powershell
python ITSM.py
```

Then go back to **http://localhost:8000/admin/ad-users** and **refresh**. It will load immediately!