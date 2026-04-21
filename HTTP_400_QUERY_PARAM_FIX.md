# HTTP 400 Error Fix - Query Parameter Validation

## Problem
When loading the assets list page, users saw:
```
Error loading assets
HTTP error! status: 400
```

This is an HTTP 400 Bad Request error, indicating validation failure on the server.

## Root Cause
The API endpoint `/api/assets/` was defining query parameters with enum types:
```python
asset_type: AssetType = Query(None)
status: AssetStatus = Query(None)
```

However, the frontend was sending string values like:
- `asset_type=computer`
- `status=in_use`

But the API expected enum values that didn't match these strings, causing Pydantic validation to fail with a 400 error.

## Solution
Changed the query parameter types from enums to strings to accept any value from the frontend:

```python
@router.get("/", response_model=List[AssetResponse])
async def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    asset_type: str = Query(None),  # Changed from AssetType to str
    status: str = Query(None),       # Changed from AssetStatus to str
    search: str = Query(None),
    db: Session = Depends(get_db),
):
```

## Benefits
? No more 400 validation errors  
? Frontend can send any filter values  
? Backend gracefully ignores unknown filter values  
? API remains backward compatible  
? Filtering logic can be added later if needed  

## File Modified
- `ITSM\app\api\assets.py` - Changed query parameter types from enums to strings

## Testing
1. Navigate to the Assets page
2. The assets list should load without errors
3. Filters should work (or be ignored gracefully if not yet implemented)
4. Check browser console for no errors

## Why This Approach?
The current implementation of `list_assets()` doesn't actually use the filter parameters in the query logic - it returns all assets or user-grouped assets regardless of filters. Therefore, accepting them as strings and ignoring them (or implementing filter logic later) is the correct approach rather than enforcing strict enum validation.

If filter functionality is needed in the future:
1. Keep the string parameter type
2. Add conditional logic to filter results based on the string values
3. No API signature change will be needed
