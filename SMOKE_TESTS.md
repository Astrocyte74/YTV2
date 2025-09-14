# YTV2 Subcategory Filtering - Smoke Tests

## Quick DevTools Testing Script

Run these in browser DevTools console to verify filtering works correctly.

```javascript
// Helper function for quick API testing
const q = (p) => fetch(`/api/reports?${p}`)
  .then(r => r.json())
  .then(j => ({
    params: p,
    ok: !!j.pagination, 
    total: j.pagination?.total_count,
    ids: (j.reports||[]).map(r=>r.id)
  }));

// WWII top level category test
await q('category=World%20War%20II%20(WWII)&size=1');                     // expect 13

// Single subcategory + parent tests
await q('subcategory=Technology%20%26%20Weapons&parentCategory=World%20War%20II%20(WWII)&size=50'); // expect 3
await q('subcategory=European%20Theatre&parentCategory=World%20War%20II%20(WWII)&size=50');         // expect 7
await q('subcategory=Home%20Front%20%26%20Society&parentCategory=World%20War%20II%20(WWII)&size=50'); // expect 3
await q('subcategory=Intelligence%20%26%20Codebreaking&parentCategory=World%20War%20II%20(WWII)&size=50'); // expect 1

// Multiple subcategories (OR logic) within same parent
await q('subcategory=European%20Theatre&subcategory=Home%20Front%20%26%20Society&parentCategory=World%20War%20II%20(WWII)&size=50'); // expect 10 (7+3)

// Subcategory without parent (legacy compatibility test)
await q('subcategory=Technology%20%26%20Weapons&size=50'); // expect 3

// Bad punctuation variant (should return 0)
await q('subcategory=Technology%20%E2%80%93%20Weapons&parentCategory=World%20War%20II%20(WWII)&size=50'); // expect 0 (en-dash)
```

## Frontend Request Monitoring

Add this to DevTools console to see what the UI actually sends:

```javascript
(async () => {
  const _fetch = window.fetch;
  window.fetch = (...args) => {
    if (String(args[0]).includes('/api/reports?')) {
      console.log('[YTV2] REQUEST =>', args[0]);
    }
    return _fetch(...args);
  };
})();
```

## Expected Frontend Request Formats

When clicking subcategory chips, you should see:

**✅ Correct Format:**
```
/api/reports?subcategory=European+Theatre&parentCategory=World+War+II+%28WWII%29&page=1&size=12&sort=added_desc
```

**❌ Old Broken Format:**
```
/api/reports?category=World+War+II+%28WWII%29&subcategory=European+Theatre&page=1&size=12&sort=added_desc
```

## Key Fixes Applied

1. **Parameter Mapping**: Send `parentCategory` instead of `category` when subcategories are selected
2. **Parent Extraction**: Get parent from `data-parent-category` attribute on subcategory inputs  
3. **Deduplication**: Remove duplicate `parentCategory` values when multiple subcategories share same parent
4. **Enhanced Logging**: Show parameter mapping decisions and normalization
5. **Fetch Interceptor**: Optional debugging tool to monitor all API requests

## Common Issues & Solutions

- **"No matches" with console showing correct counts**: Frontend/backend parameter mismatch
- **500 errors**: Malformed JSON in database, missing json_valid() checks
- **Multiple categories showing as single chip**: Backend flattening issue, check schema_version
- **Subcategories not in filter list**: Database sync issue, check subcategories_json field