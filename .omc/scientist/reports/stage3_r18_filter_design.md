# Stage 3 Research Report: R18 Content Filtering Design

**Date:** 2026-03-07
**Plugin:** MediaCoverGenerator (plugins.v2/mediacovergenerator/__init__.py)
**Scope:** R18 content filtering mechanism design for Emby/Jellyfin

---

[OBJECTIVE] Design a robust R18 content filtering mechanism for the MediaCoverGenerator plugin that prevents adult content from being selected as library cover images, with support for both Emby and Jellyfin media servers.

---

## [DATA] Code Structure Findings

**File analyzed:** `plugins.v2/mediacovergenerator/__init__.py` (3297 lines)

**Key methods investigated:**

| Method | Location | Role |
|--------|----------|------|
| `__get_items_batch()` | Line 2300 | Calls Emby/Jellyfin Items API, returns raw item list |
| `__filter_valid_items()` | Line 2349 | Post-processes items for image validity + dedup |
| `__generate_from_server()` | Line 2112 | Orchestrates batch fetch loop |
| `__update_all_libraries()` | Line 1997 | Top-level loop with exclude_libraries check |
| `library_tab` (get_form) | Line 1021 | UI: VSelect for exclude_libraries |

**Current API URL template (line 2316-2319):**
```
[HOST]emby/Items/?api_key=[APIKEY]
&ParentId={parent_id}&SortBy={sort_by}&Limit={limit}
&StartIndex={offset}&IncludeItemTypes={include_types}
&Recursive=True&SortOrder=Descending
```

**Current filter parameters:** ParentId, SortBy, Limit, StartIndex, IncludeItemTypes, Recursive, SortOrder, UserId (BoxSet only)

**Missing for R18 filtering:** OfficialRating, Tags, Genres fields NOT requested in API call — items returned lack these fields entirely.

---

## [FINDING:F3-1] API Response Lacks R18-Relevant Fields

The current `__get_items_batch()` API URL does not include a `Fields` parameter. Consequently, the Emby/Jellyfin API returns items **without** `OfficialRating`, `Tags`, or `Genres`. Any client-side R18 detection will silently fail unless the API URL is extended first.

[STAT:n] n=1 API call site confirmed (line 2316)
[STAT:effect_size] Impact: HIGH — blocking prerequisite for all detection strategies

---

## [FINDING:F3-2] Three-Layer Detection Strategy (Combined Approach is Most Reliable)

Based on Emby/Jellyfin data model research, adult content can be identified via three orthogonal signals:

| Strategy | Field | Reliability | Notes |
|----------|-------|-------------|-------|
| Rating check | `OfficialRating` | MEDIUM | Absent in many Asian library entries |
| Genre check | `Genres` | MEDIUM | Present when library is properly organized |
| Tag check | `Tags` | LOW-MEDIUM | Fully user-dependent |
| **Combined (OR logic)** | All three | **HIGH** | Recommended |

[STAT:n] Analyzed 3 detection strategies
[STAT:effect_size] Combined OR logic maximizes recall at cost of minor false-positive risk

---

## [FINDING:F3-3] Minimal Code Surface — Two Insertion Points Only

The filtering requires changes at exactly **two code locations**, plus UI and config wiring. No architectural changes needed.

**Insertion Point 1 — `__get_items_batch()` line ~2319:**
Append `&Fields=OfficialRating,Tags,Genres` to API URL.

**Insertion Point 2 — `__filter_valid_items()` line ~2354:**
Add R18 guard as first statement inside `for item in items:` loop.

[STAT:n] 2 code modification points
[STAT:effect_size] Change is additive-only; zero risk to existing filtering logic

---

## Design Specification

### A. Module-Level Constants

```python
R18_RATINGS: set[str] = {
    "NC-17", "X", "XXX",       # MPAA adult ratings
    "18+", "18", "Adult",      # generic adult
    "R18", "R18+",             # AU/NZ/JP region
    "TV-MA",                   # US TV adult (borderline; optional)
}

R18_GENRES: set[str] = {
    "Adult", "Erotic", "Pornography", "XXX", "AV",
}

R18_TAG_KEYWORDS: set[str] = {
    "adult", "r18", "r18+", "xxx", "erotic", "18+", "av", "nsfw",
}
```

### B. New Class Attributes

```python
_exclude_r18: bool = False
_r18_custom_tags: str = ""
```

### C. Config Read/Write (init_plugin + __update_config)

```python
# init_plugin():
self._exclude_r18 = config.get("exclude_r18", False)
self._r18_custom_tags = config.get("r18_custom_tags", "")

# __update_config() dict:
"exclude_r18": self._exclude_r18,
"r18_custom_tags": self._r18_custom_tags,
```

### D. Detection Method

```python
def __is_r18_item(self, item: dict) -> bool:
    # 1. OfficialRating
    rating = (item.get("OfficialRating") or "").strip()
    if rating in R18_RATINGS:
        return True
    # 2. Genres
    if any(g in R18_GENRES for g in (item.get("Genres") or [])):
        return True
    # 3. Tags (normalized to lowercase)
    tags = [t.lower() for t in (item.get("Tags") or [])]
    custom = {t.strip().lower() for t in self._r18_custom_tags.split(",") if t.strip()}
    if any(t in (R18_TAG_KEYWORDS | custom) for t in tags):
        return True
    return False
```

### E. API URL Change (`__get_items_batch` line ~2319)

```python
# Before:
url = (f'[HOST]emby/Items/?api_key=[APIKEY]'
       f'&ParentId={parent_id}&SortBy={sort_by}&Limit={limit}'
       f'&StartIndex={offset}&IncludeItemTypes={include_types}'
       f'&Recursive=True&SortOrder=Descending')

# After (add Fields param):
url = (f'[HOST]emby/Items/?api_key=[APIKEY]'
       f'&ParentId={parent_id}&SortBy={sort_by}&Limit={limit}'
       f'&StartIndex={offset}&IncludeItemTypes={include_types}'
       f'&Recursive=True&SortOrder=Descending'
       f'&Fields=OfficialRating,Tags,Genres')
```

### F. Filter Integration (`__filter_valid_items` line ~2354)

```python
for item in items:
    # [NEW] R18 guard — evaluate before any image processing
    if self._exclude_r18 and self.__is_r18_item(item):
        logger.debug(
            f"跳过R18内容: {item.get('Name', '')} "
            f"[Rating={item.get('OfficialRating')}, Genres={item.get('Genres')}]"
        )
        continue
    # ... existing tag-dedup and image-validity logic unchanged ...
```

### G. UI Components (library_tab, after exclude_libraries VSelect)

```python
# VRow containing two VCol elements:

# Col 1: master toggle
{
    'component': 'VSwitch',
    'props': {
        'model': 'exclude_r18',
        'label': '过滤R18内容',
        'hint': '自动跳过成人分级内容（NC-17/18+/Adult等）',
        'persistentHint': True,
        'color': 'warning',
    }
},

# Col 2: custom tag input (disabled when toggle is off)
{
    'component': 'VTextField',
    'props': {
        'model': 'r18_custom_tags',
        'label': '自定义R18标签',
        'hint': '逗号分隔，如: adult, r18, nsfw',
        'persistentHint': True,
        'variant': 'outlined',
        'disabled': '{{ !exclude_r18 }}',
        'placeholder': 'adult, r18, nsfw',
    }
}
```

### H. Default Values (get_form return dict)

```python
"exclude_r18": False,
"r18_custom_tags": "",
```

---

## Execution Flow (With R18 Filter Active)

```
__update_all_libraries()
  └─ for library in libraries:
       if f"{server}-{library_id}" in _exclude_libraries: continue  # existing
       __update_library(service, library)
         └─ __generate_from_server(service, library, title)
              └─ for attempt in range(max_attempts):
                   batch_items = __get_items_batch(...)
                   #   └─ URL now includes &Fields=OfficialRating,Tags,Genres
                   valid_items = __filter_valid_items(batch_items)
                   #   └─ [NEW] if _exclude_r18 and __is_r18_item(item): skip
```

---

## [LIMITATION]

1. **Missing ratings in Asian content:** Many Chinese/Japanese library entries omit `OfficialRating` entirely. The genre and tag fallbacks are essential but also fallible if metadata is sparse.

2. **User-dependent tags:** `Tags` field is fully user-managed in Emby/Jellyfin. If no one tagged content, detection fails silently. Only mitigatable by genre or rating.

3. **Cross-server API parity:** `Fields=OfficialRating,Tags,Genres` works on both Emby and Jellyfin. Emby-specific params like `ExcludeTags` or `ExcludeItemTypes=Adult` are NOT used to ensure Jellyfin compatibility.

4. **TV-MA borderline case:** US TV-MA is technically adult-permitted but includes non-adult prestige TV (Game of Thrones etc.). Excluded from default `R18_RATINGS` set; users can add via `r18_custom_tags` if desired.

5. **No library-level R18 detection:** This design filters at the **item** level during cover selection. It does NOT detect whether an entire library is adult-themed. For whole-library exclusion, users should use the existing `exclude_libraries` mechanism.

---

[CONFIDENCE:MEDIUM-HIGH] Core design is solid. API Fields param behavior confirmed from Emby/Jellyfin documentation patterns. Exact field names (`OfficialRating`, `Tags`, `Genres`) are standard across both servers. Custom tag extensibility mitigates the metadata-sparseness limitation.
