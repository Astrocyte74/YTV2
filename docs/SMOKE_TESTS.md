# YTV2 Dashboard – Smoke Tests

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

// WWII top level category test (example)
await q('category=World%20War%20II%20(WWII)&size=1');                     // expect ~13

// Single subcategory + parent tests
await q('subcategory=Technology%20%26%20Weapons&parentCategory=World%20War%20II%20(WWII)&size=50');
await q('subcategory=European%20Theatre&parentCategory=World%20War%20II%20(WWII)&size=50');

// Multiple subcategories (OR logic) within same parent
await q('subcategory=European%20Theatre&subcategory=Home%20Front%20%26%20Society&parentCategory=World%20War%20II%20(WWII)&size=50');

// Subcategory without parent (legacy compatibility test)
await q('subcategory=Technology%20%26%20Weapons&size=50');
```

## Frontend Request Monitoring

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

## Expected Frontend Request Formats (subcategory)
Clicking a subcategory chip should produce:

```
/api/reports?subcategory=European+Theatre&parentCategory=World+War+II+%28WWII%29&page=1&size=12&sort=added_desc
```

