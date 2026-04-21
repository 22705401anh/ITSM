# Quick Start: AD Users & Sidebar Toggle

## ?? What's New

### 1. AD Users Page
- **Location**: Sidebar ? Administration ? AD Users
- **URL**: `http://localhost:8000/admin/ad-users`
- **Shows**: Real-time Active Directory users from LDAP
- **Features**: Search, filter, refresh from AD

### 2. Sidebar Toggle
- **Expand/Collapse Button**: In the navbar (left side hamburger icon)
- **State Saved**: Your preference is remembered
- **Icons Only Mode**: Collapsed sidebar shows just icons
- **Smooth Animation**: 0.3s transition

## ?? Getting Started

### Step 1: Start Application
```powershell
cd ITSM
python ITSM.py
```

### Step 2: Access AD Users
Choose one of:
- **Via URL**: `http://localhost:8000/admin/ad-users`
- **Via Sidebar**: 
  1. Scroll down to "Administration" section
  2. Click "AD Users"
  3. See real-time list of Active Directory users

### Step 3: Toggle Sidebar (Optional)
- Click **hamburger icon** (?) in navbar to collapse/expand
- Preference is saved automatically
- Click again to toggle back

## ?? Responsive Design

### Desktop View
- Full sidebar visible by default
- Toggle button in navbar on the right
- Smooth transitions
- Optimized for large screens

### Mobile View
- Sidebar takes full width when expanded
- Hamburger icon on left for toggle
- Collapses to icons-only to save space
- Optimized for small screens

## ?? Features

### AD Users Page
- ? Real-time LDAP connection
- ? Filter by name, email, username, department
- ? Refresh button to get latest data
- ? Error handling with helpful messages
- ? Console logging for debugging

### Sidebar Toggle
- ? Persistent state (localStorage)
- ? Smooth CSS transitions
- ? Active link highlighting
- ? Mobile-friendly
- ? Keyboard accessible

## ?? Sidebar States

### Expanded (Default)
```
???????????????????????
? Dashboard           ?
? ?? Problems         ?
? ?? Changes          ?
? ?? Inventory        ?
? ?? AD Users    ?   ? ? NEW
? ?? Settings         ?
???????????????????????
```

### Collapsed
```
????
????
???
???
????
???? ? New icon
???
????
```

## ?? UI Components

### Toggle Buttons
1. **Hamburger Button** (always visible)
   - Location: Left side of navbar
   - Icon: `?` (hamburger)
   - Visible on all screen sizes

2. **Hide/Show Sidebar Button** (in navbar)
   - Location: Right side of navbar with text
   - Text: "Hide Sidebar" or "Show Sidebar"
   - Updates dynamically

### Sidebar Icons
- ?? Dashboard
- ? Problems
- ?? Changes
- ??? Inventory
- ?? Licenses
- ?? Problem Solutions
- ?? General Docs
- ?? Contracts
- ?? Reservations
- ?? Projects
- ?? Knowledge Base
- ?? Local Users
- ???? AD Users (NEW)
- ??? Entities
- ?? Settings

## ?? Keyboard Navigation

- `Tab` - Navigate through links
- `Enter` - Click link or button
- `Space` - Activate button

(Future: Consider adding Ctrl+B for sidebar toggle)

## ?? Sidebar Structure

```
Administration
??? Local Users (??)
??? AD Users (????) ? NEW
??? Entities (???)
??? Settings (??)
```

## ?? Troubleshooting

### AD Users Page Shows "Loading..." Forever
- Check browser console (F12)
- Verify LDAP server is accessible
- Check `.env` file has correct LDAP credentials
- Check error message for details

### Sidebar Won't Toggle
- Refresh the page
- Clear browser cache (Ctrl+Shift+Delete)
- Check browser console for errors
- Verify localStorage is enabled

### Icons Not Showing Correctly
- Verify Font Awesome is loaded (in navbar)
- Check browser console for missing assets
- Try clearing cache and refresh

## ?? Documentation

- Detailed implementation: `ITSM/SIDEBAR_TOGGLE_IMPLEMENTATION.md`
- Complete guide: `ITSM/SIDEBAR_TOGGLE_COMPLETE.md`
- AD Users setup: Previous documentation

## ?? Tips

1. **Save Bandwidth**: Use collapsed sidebar on mobile
2. **Better Focus**: Collapse sidebar when reading long content
3. **Quick Access**: Full sidebar for navigation-heavy tasks
4. **State Persistent**: Preference saved across sessions
5. **Always Accessible**: Both expanded and collapsed modes work great

## ? What's Next?

The sidebar toggle feature is production-ready! 

Optional future enhancements:
- Add more animation styles
- Add keyboard shortcuts
- Store preference in user profile
- Add customizable sidebar width
- Add sidebar themes

## ?? Support

If you encounter any issues:
1. Check browser console (F12 ? Console tab)
2. Look for error messages
3. Verify all files are created correctly
4. Check LDAP connectivity for AD Users issues
5. Clear cache and try again

---

**Last Updated**: 2024
**Status**: ? Production Ready
