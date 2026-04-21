# ?? Assets Search - Quick Start Guide

## The Problem (Solved ?)
Users couldn't find assets by Serial Number (SN) or PC name in the search box.

## The Solution
? Added full-text search across 6 asset fields:
- Asset name (PC name)
- Asset tag
- Serial Number (SN)
- Model number
- Manufacturer
- Location

---

## How to Use

### Search by Serial Number (SN)
1. Go to **Assets** page
2. In the search box, type the serial number (e.g., `SN123456`)
3. Click **Search** button
4. Results will show matching assets with SN visible

### Search by PC Name
1. Go to **Assets** page
2. In the search box, type the PC name (e.g., `PC-001`)
3. Click **Search** button
4. All matching assets displayed

### Combine Search with Filters
1. Select **Type** (e.g., Laptop)
2. Select **Status** (e.g., In Use)
3. Enter search term (e.g., SN or name)
4. Click **Search**
5. Results filtered by both criteria

---

## What Changed

### Backend (API)
**File:** `app/api/assets.py`
- Added `search` parameter to list_assets() endpoint
- Searches 6 asset fields using SQL `OR` conditions
- Case-insensitive and supports partial matching

### Frontend (UI)
**File:** `app/web/templates/assets/list.html`
- Updated search placeholder: "Asset tag, name, SN (serial number), model..."
- Added Serial Number column to asset table
- Serial numbers now visible in search results

---

## Features

? **Case-Insensitive** - Search works regardless of case  
? **Partial Matching** - Type partial SN and it finds matches  
? **Multi-Field** - Searches 6 different fields  
? **Filter Compatible** - Works with Type and Status filters  
? **Fast** - Database-level search, optimized queries  

---

## Examples

| Search Term | Finds |
|------------|-------|
| `SN123456` | Assets with SN123456 in serial number field |
| `Dell` | Assets with Dell as manufacturer |
| `Laptop-A` | Assets with "Laptop-A" in name or tag |
| `Building-2` | Assets in "Building-2" location |
| `HP` | Manufacturer OR name OR model containing HP |

---

## Testing

Try searching for:
1. A known serial number
2. A PC name
3. A manufacturer name
4. Partial serial numbers

All should return matching results!

---

## Status
? **READY TO USE**

The search functionality is now fully working and optimized.

---

For detailed technical documentation, see: **SEARCH_FIX_DOCUMENTATION.md**
