# Filter Bar Redesign Mockup

## Current State (with sidebar)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 🎧 Summarizernator                                          [☰] [⚙️]     │
│     AI-powered summaries                     [Filters]                      │
├──────────────────────┬─────────────────────────────────────────────────────┤
│                      │                                                     │
│  SORT BY             │                                                     │
│  ○ Recently Added    │                                                     │
│  ○ Video Newest      │       [Content Cards - constrained width]           │
│  ○ Show more...      │                                                     │
│                      │                                                     │
│  SOURCE              │                                                     │
│  ☑ Telegram          │                                                     │
│  ☑ YouTube           │                                                     │
│                      │                                                     │
│  CATEGORIES          │                                                     │
│  ☑ AI                │                                                     │
│  ☐ Science           │                                                     │
│  ☐ Tech              │                                                     │
│  ...                 │                                                     │
│                      │                                                     │
│  (scrolling...)      │                                                     │
│                      │                                                     │
│  320px sidebar       │                                                     │
│                      │                                                     │
└──────────────────────┴─────────────────────────────────────────────────────┘
```

## Proposed: Horizontal Filter Bar

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 🎧 Summarizernator                                          [☰] [⚙️]     │
│     AI-powered summaries                                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐ │
│  │ Sort ▾          │ │ Filter ▾   │ │ Source ▾   │ │ × AI  × Science    │ │
│  │ Recently Added  │ │ 2 active   │ │ All        │ │ Clear all          │ │
│  └─────────────────┘ └────────────┘ └────────────┘ └────────────────────┘ │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                                                                            │
│                     [Content Cards - FULL WIDTH]                           │
│                                                                            │
│                     (320px more horizontal space!)                         │
│                                                                            │
│                                                                            │
│                                                                            │
│                                                                            │
│                                                                            │
│                                                                            │
│                                                                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Dropdown Details

### Sort Dropdown (simple list)
```
┌─────────────────┐
│ Sort ▾          │
├─────────────────┤      Click to open:
│ Recently Added  │      ┌─────────────────┐
│ Video Newest    │  →   │ ✓ Recently Added│
│ Video Oldest    │      │   Video Newest  │
│ Title A→Z       │      │   Video Oldest  │
│ Title Z→A       │      │   Title A→Z     │
│ Longest First   │      │   Title Z→A     │
│ Shortest First  │      │   Longest First │
└─────────────────┘      │   Shortest First│
                         └─────────────────┘
```

### Filter Dropdown (grouped sections)
```
┌────────────────────────────────────────────────────────────┐
│ Filter                                      2 active   ▾   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Click to open a wide popover:                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Categories            Channels         Content Type   │ │
│  │ ☑ AI                  ☐ All            ☑ All         │ │
│  │ ☑ Science             ☐ 3Blue1Brown    ☐ Video       │ │
│  │ ☐ Tech                ☐ Veritasium     ☐ Podcast     │ │
│  │ ☐ Philosophy          ☐ Lex Fridman    ☐ Article     │ │
│  │ ☐ Math                [Show more...]                  │ │
│  │ [Show more...]                                        │ │
│  │                                                       │ │
│  │ Complexity            Language         Summary Type   │ │
│  │ ○ All                 ☑ All            ☑ All         │ │
│  │ ○ Beginner            ☐ English        ◐ Key Points  │ │
│  │ ○ Intermediate        ☐ Spanish        ◐ Full        │ │
│  │ ○ Advanced            ☐ German         ◐ Brief       │ │
│  │                                                       │ │
│  │ ┌─────────────────────────────────────────────────┐  │ │
│  │ │  [Clear all]              [Apply filters]       │  │ │
│  │ └─────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Source Dropdown (quick access)
```
┌────────────┐
│ Source ▾   │
├────────────┤      Click to open:
│ All        │      ┌────────────┐
└────────────┘  →   │ ✓ All      │
                   │   Telegram │
                   │   YouTube  │
                   │   Podcast  │
                   └────────────┘
```

### Active Filter Chips (always visible)
```
┌────────────────────────────────────────────────────────────┐
│  × AI    × Science    × Key Points    [Clear all]          │
│                                                            │
│  Click × to remove that filter                             │
│  Click "Clear all" to reset                                │
└────────────────────────────────────────────────────────────┘
```

## Mobile Responsive

### Mobile - Collapsed
```
┌────────────────────────────┐
│ 🎧 Summarizernator    [☰]  │
│     AI-powered summaries   │
├────────────────────────────┤
│ [Sort ▾] [Filter (2)] [×2] │  ← Horizontal scroll or wrap
├────────────────────────────┤
│                            │
│   [Content Cards]          │
│                            │
└────────────────────────────┘
```

### Mobile - Filter Sheet (bottom sheet)
```
┌────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← Drag handle
├────────────────────────────┤
│ Filters                [×] │
├────────────────────────────┤
│ Sort                       │
│ ○ Recently Added           │
│ ○ Video Newest             │
│                            │
│ Categories                 │
│ ☑ AI                       │
│ ☑ Science                  │
│                            │
│ ...                        │
│                            │
├────────────────────────────┤
│ [Clear]      [Apply (2)]   │
└────────────────────────────┘
```

## Alternative: Pill-Based Filter Bar (Even Cleaner)

Instead of a big Filter dropdown, show common filters as pills:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 🎧 Summarizernator                                          [☰] [⚙️]     │
│     AI-powered summaries                                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Sort: [Recently Added ▾]                                                  │
│                                                                            │
│  [All ▾] [AI ▾] [Science ▾] [Tech ▾] [+ Add filter]                        │
│                                                                            │
│  Active: × AI  × Science                              [Clear all]          │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                     [Content Cards - FULL WIDTH]                           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Benefits of This Approach

1. **More content space** - Gain 320px horizontal for cards
2. **Cleaner UI** - No persistent sidebar eating visual attention
3. **Mobile-friendly** - Horizontal bar adapts well, bottom sheet for mobile
4. **Progressive disclosure** - Simple by default, powerful when needed
5. **Visible state** - Active filters always visible as chips
6. **Familiar pattern** - Used by Gmail, Notion, Linear, etc.

## Implementation Notes

1. **Filter bar component** - New horizontal bar below header
2. **Dropdown/popover components** - For sort and filter selections
3. **Filter chips** - Show active filters as removable pills
4. **Mobile sheet** - Bottom sheet for filters on mobile
5. **State management** - Keep existing `currentFilters` logic
6. **Animation** - Smooth transitions for dropdowns and chips

## Questions to Decide

1. **Apply vs Instant?** - Should filters apply instantly or require "Apply" button?
   - Recommendation: Instant (like current behavior)

2. **Which filters are "quick access"?** - Source as a separate dropdown, or inside Filter?
   - Recommendation: Source as quick dropdown, others in Filter popover

3. **Show count badges?** - E.g., "Filter (2)" to show active count?
   - Recommendation: Yes, helpful feedback

4. **Collapse on mobile?** - Horizontal scroll or wrap pills?
   - Recommendation: Wrap with overflow scroll
