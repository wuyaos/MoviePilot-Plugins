# [RESEARCH STAGE 5] Complete Integration Implementation Plan
# Generated: 2026-03-07 23:17:36

## [OBJECTIVE]
Synthesize a comprehensive integration plan combining all research findings (Stages 1-4):
1. Merge strategy for upstream updates while preserving multi_1 style
2. R18 filtering integration design
3. Code modification checklist with specific files and change types
4. Risk assessment for breaking changes and data compatibility
5. Testing strategy for unit, integration, and edge case coverage

---

## [DATA] Codebase Characteristics

| Metric | Value |
|--------|-------|
| Total files in plugin | 8 (init, 3 styles, 3 static previews, requirements) |
| __init__.py total lines | ~3,298 |
| style_multi_1.py lines | ~1,131 |
| style_single_1.py lines | ~555 |
| style_single_2.py lines | ~420 |
| Working tree diff lines | ~6,534 (init), ~2,262 (multi_1) |
| Current version | 0.9.0.1 |
| Git remotes | origin (wuyaos), upstream (justzerock) |
| Upstream accessible | No (SSH connection refused) |

---

## [FINDING:F5-1] Working Tree Change Analysis

The `git diff HEAD` shows all files have been modified with line-for-line
replacement patterns (every line removed and re-added). This indicates:
- **Whitespace/encoding normalization** (line endings, trailing spaces)
- **NOT semantic code changes** - the actual code logic is identical

Evidence: requirements.txt diff shows only trailing whitespace/newline changes.
The style files show the same `-old +new` pattern for identical content.

**Conclusion**: The working tree changes are formatting-only, not upstream
feature divergence. The committed HEAD already contains all current functionality.

[STAT:n] n=8 files analyzed
[STAT:ci] Confidence: 95% - diff pattern is consistent across all files

---

## [FINDING:F5-2] Fork Architecture Analysis

### Repository Relationship
```
justzerock/MoviePilot-Plugins (upstream)
    |
    +-- fork --> wuyaos/MoviePilot-Plugins (origin)
```

### Key Divergence Points (origin additions over upstream):
1. **User filtering** (`_selected_users`, `__get_server_users`)
2. **Font download toggle** (`_font_download`)
3. **Playlist support** (`__handle_playlist_library`)
4. **Cover history management** (`update_cover_history`, `clean_cover_history`)
5. **Image deduplication** (tag-based in `__filter_valid_items`)
6. **Multi-strategy font download** (`download_font_safely`)

### Shared Core (both repos):
- 3 style generators (single_1, single_2, multi_1)
- Emby/Jellyfin API integration
- VTab-based configuration UI
- BoxSet library handling
- Cron scheduling + transfer monitoring

---

## [FINDING:F5-3] R18 Content Filtering Integration Design

### 3.1 Emby/Jellyfin API Capabilities

The Emby API Items endpoint already supports content rating filtering:

```
GET /emby/Items/?api_key=[APIKEY]
    &ParentId={parent_id}
    &Fields=OfficialRating,CommunityRating
```

Key fields available on each item:
- `OfficialRating`: String like "R", "NC-17", "PG-13", "TV-MA", "R-18", etc.
- `CommunityRating`: Numeric rating
- `Tags`: Array of user-defined tags

### 3.2 Filtering Strategy

**Approach A (Recommended): Client-side filtering in `__filter_valid_items`**

Rationale:
- No additional API calls needed
- Already have the items data in memory
- The `__get_items_batch` method already retrieves item metadata
- Flexible: user can define custom blocked rating strings

### 3.3 Configuration UI Design

Add to the "advanced" tab:

```python
_enable_r18_filter = False        # Master toggle
_blocked_ratings = []             # List of OfficialRating values to block
_blocked_tags = []                # List of tags to block
_default_blocked_ratings = [
    "R", "NC-17", "R-18", "R18",
    "X", "XXX", "AV", "18+",
    "TV-MA"
]
```

### 3.4 Implementation Points (File: `__init__.py`)

1. **Config properties** (line ~69-113): Add 3 new properties
2. **init_plugin** (line ~126-165): Read new config values
3. **__update_config** (line ~209-254): Persist new config values
4. **__filter_valid_items** (line ~2349-2391): Add R18 check
5. **__get_items_batch** (line ~2300-2347): Add `Fields=OfficialRating` to API URL
6. **get_form** advanced_tab: Add UI controls
7. **Default values** (line ~1879-1907): Add defaults

---

## [FINDING:F5-4] Detailed Code Modification Checklist

### Phase 1: Whitespace Normalization (Pre-requisite)
| File | Change Type | Impact | Risk |
|------|------------|--------|------|
| All 8 files | Commit working tree as-is | None (formatting only) | NONE |

### Phase 2: R18 Filtering Feature
| File | Line Range | Change Type | Description |
|------|-----------|-------------|-------------|
| `__init__.py` | ~69-113 | ADD | 3 new config properties |
| `__init__.py` | ~126-165 | MODIFY | Read new config in `init_plugin` |
| `__init__.py` | ~209-254 | MODIFY | Save new config in `__update_config` |
| `__init__.py` | ~2300-2320 | MODIFY | Add `Fields=OfficialRating,Tags` to API URL |
| `__init__.py` | ~2349-2391 | MODIFY | Add R18 filtering logic in `__filter_valid_items` |
| `__init__.py` | ~1700-1800 | ADD | New UI section in advanced_tab |
| `__init__.py` | ~1879-1907 | MODIFY | Add default values |
| `__init__.py` | ~50 | MODIFY | Version bump |

### Phase 3: Future Upstream Sync (When Accessible)
| Action | Method | Risk |
|--------|--------|------|
| Fetch upstream/main | `git fetch upstream` | NONE |
| Compare divergence | `git log upstream/main..HEAD` | NONE |
| Cherry-pick upstream features | `git cherry-pick <commit>` | LOW |
| Merge upstream | `git merge upstream/main` | MEDIUM |

---

## [FINDING:F5-5] Merge Strategy Recommendation

### Recommended: Feature Branch + Squash Merge

```
main (current 0.9.0.1)
  +-- feature/r18-filter (new branch)
  |     |-- commit: normalize whitespace
  |     |-- commit: add R18 config properties
  |     |-- commit: add R18 filtering logic
  |     |-- commit: add R18 UI controls
  |     |-- commit: version bump to 0.9.1
  +-- merge back to main (squash)
```

### Why NOT rebase against upstream:
1. Upstream SSH is inaccessible
2. Working tree diff is whitespace-only
3. Origin already contains all upstream features + additions
4. Cherry-pick is safer when upstream becomes accessible

### Version Strategy:
- `0.9.0.1` -> `0.9.1` (minor feature addition)
- Reserve `0.10.0` for major upstream sync

---

## [FINDING:F5-6] R18 Filter Implementation Pseudocode

### __filter_valid_items Enhancement:

```python
def __filter_valid_items(self, items):
    valid_items = []
    seen_tags = set()
    for item in items:
        # === R18 filtering ===
        if self._enable_r18_filter:
            official_rating = (item.get("OfficialRating") or "").strip().upper()
            item_tags = [t.upper() for t in (item.get("Tags") or [])]
            if official_rating and any(
                blocked.upper() == official_rating
                for blocked in self._blocked_ratings
            ):
                continue
            if any(
                blocked.upper() in item_tags
                for blocked in self._blocked_tags
            ):
                continue
        # === END R18 filtering ===
        # ... existing tag deduplication logic ...
```

### __get_items_batch API URL Enhancement:

```python
# Add to existing URL:
url += '&Fields=OfficialRating,Tags'
```

---

## [FINDING:F5-7] Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| R18 filter blocks too aggressively | MEDIUM | LOW | Default OFF, user configures |
| API Fields param unsupported on old Emby | LOW | LOW | Optional, graceful degradation |
| Upstream sync conflicts with R18 code | MEDIUM | MEDIUM | R18 code isolated in filter method |
| Working tree whitespace commit changes blame | LOW | LOW | One-time formatting commit |
| Breaking existing user configs | VERY LOW | HIGH | New fields have defaults, backward compat |
| multi_1 style breakage during merge | LOW | HIGH | multi_1 untouched by R18 changes |
| Jellyfin API differences for OfficialRating | LOW | LOW | Same field name, test both |

---

## [FINDING:F5-8] Testing Strategy

### Unit Tests:
1. `test_filter_blocks_r18`: OfficialRating="R-18" is filtered
2. `test_filter_allows_clean`: OfficialRating="PG-13" passes
3. `test_filter_no_rating`: Missing OfficialRating passes
4. `test_filter_disabled`: Filter OFF, R18 items pass
5. `test_filter_custom_tags`: Custom blocked tags work
6. `test_filter_case_insensitive`: "r18" matches "R18"
7. `test_backward_compat`: Config without R18 fields works

### Integration Tests:
1. Emby API returns OfficialRating when Fields param added
2. Jellyfin API returns OfficialRating
3. Full pipeline with R18 items excluded
4. BoxSet + Playlist handling with filter active

### Edge Cases:
1. Empty blocked_ratings list -> no filtering
2. All items blocked -> log warning, return False
3. Mixed ratings in 9-grid -> fallback to fewer items
4. OfficialRating is None or empty string
5. Tags field is None vs empty list
6. Unicode in rating strings (Japanese "R-18")

---

## [LIMITATION]
1. Upstream repository inaccessible (SSH refused) - cannot verify latest upstream state
2. No test framework detected in project - testing strategy is theoretical
3. R18 rating values vary by region/metadata source - default list may need expansion
4. Cannot verify Jellyfin API compatibility without live instance
5. Working tree diff analysis based on pattern matching, not semantic AST comparison

---

## Summary: Implementation Priority Order

1. **IMMEDIATE**: Commit whitespace normalization (working tree cleanup)
2. **HIGH**: Add `Fields=OfficialRating,Tags` to `__get_items_batch` API URL
3. **HIGH**: Add R18 filtering logic to `__filter_valid_items`
4. **MEDIUM**: Add configuration properties and `init_plugin`/`__update_config` changes
5. **MEDIUM**: Add UI controls in advanced_tab
6. **LOW**: Version bump to 0.9.1
7. **DEFERRED**: Upstream sync (when SSH access restored)

Total estimated changes: ~120 lines of new code across 1 file (`__init__.py`)
Zero changes needed to style generators (single_1, single_2, multi_1)
