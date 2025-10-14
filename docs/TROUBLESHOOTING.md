# Troubleshooting

## 500: list index out of range (psycopg2)
This usually means the number of `%s` placeholders in SQL didn’t match the number of parameters passed to `cursor.execute`. Fix by ensuring the WHERE builder appends placeholders and parameters together, and don’t mutate the same list for both count and main queries.

## 500 from percent signs in SQL
Psycopg2 treats `%` as a formatting marker. For literal patterns in LIKE/ILIKE, use `%%` (e.g., `LIKE '%%youtube.com%%'`) and for prefixes like `reddit:%` use `reddit:%%`.

## Filters appear but counts look wrong
Ensure `/api/filters` is returning real counts and the UI isn’t overwriting them. The current UI trusts server counts and only augments missing slugs.

## Nothing shows when clearing filters
By design, the UI requires at least one selection for some groups (e.g., category/source/channel). Clearing all shows a helpful empty-state card.

