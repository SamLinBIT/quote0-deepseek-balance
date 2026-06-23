# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

DeepSeek API balance dashboard for the MindReset Dot Quote/0 — a 296×152 pixel, 125 PPI e-ink display. The device renders content via a cloud Canvas API (JSON payloads with Tailwind-like `tw` classes). Three independent views are pushed separately: a balance dashboard, a 30-day spending heatmap, and a combined dashboard. A crontab rotates between them.

**Zero external dependencies** — everything uses only the Python standard library (Decimal for money, struct+zlib for PNG, urllib for HTTP, csv+zipfile for usage imports).

## Common commands

```bash
# Push views to device
./run_balance_check.sh                  # balance dashboard (default)
./run_balance_check.sh --heatmap        # 30-day heatmap
./run_balance_check.sh --dashboard      # combined (balance + 28-day heatmap)

# Preview without pushing
./run_balance_check.sh --dry-run
./run_balance_check.sh --dashboard --dry-run

# Import DeepSeek usage data
./run_balance_check.sh --import-usage usage_data_2026_6.zip

# Run directly (bypass shell wrapper, needs env vars)
python -m deepseek_balance.main --dashboard
```

The shell wrapper at `run_balance_check.sh` loads `.env` secrets, sets `TZ=Asia/Shanghai`, bootstraps `.venv` if needed, and logs non-interactive runs to `logs/balance_cron.log`.

## Architecture: data pipeline

```
DeepSeek API ──→ balance snapshot ──→ balance_history.json
                   │
                   └──→ daily delta (yesterday - today)
                            │
DeepSeek usage ZIP ──→ usage_history.json (imported_daily_costs)
                            │
                            └──→ 30-day cost dict ──→ heat levels (0-4) ──→ PNG pixels
                                                                              │
                                                                              └──→ Canvas JSON payload ──→ Dot API
```

**Cost data precedence** (in `gather_30day_costs()`): imported CSV daily costs take priority; balance-history deltas are the fallback. This means a fresh deployment without a ZIP import will only show costs for days where consecutive balance snapshots exist.

**Heat level thresholds** (`_compute_level_thresholds`): when ≥10 positive-cost days exist, uses quartile boundaries (P25/P50/P75) for even distribution across the 5 levels. Falls back to fixed ratios of the max cost (25%/50%/75%) for small samples.

## The Canvas element DSL

All three view modules (`layout.py`, `heatmap.py`, `dashboard.py`) define an identical `_element()` helper that builds dicts of the form `{"type": "...", "props": {"tw": "...", "children": ...}}`. This is a lightweight internal DSL for the Quote/0 Canvas JSON API — Tailwind-like utility classes on a restricted set of HTML element types. There is no shared module for this; each file has its own copy.

Key Canvas API constraints to be aware of:
- `link` field: max ~500 chars (used for NFC tap-to-view; `nfc_report.py` generates the text report that goes here)
- `img-dither-none img-levels-2` / `img-levels-4`: CSS classes that control the device's dithering. The e-ink display is effectively binary (black/white only despite nominal 4-level grayscale), so heatmap patterns must be pre-dithered
- Text sizing uses custom classes like `text-14-chillksans`, `text-pixel-10`

## PNG generation (heatmap.py)

The heatmap is rendered server-side as a single PNG with baked-in binary patterns, then delivered as a base64 data URI. Two functions handle this:

- `_render_grid_png(grid)` — 7-col × 7-row grid for the standalone heatmap view (36×13 px cells)
- `_render_4col_grid_png(grid)` — 4-col × 7-row grid for the combined dashboard (42×12 px cells)

Both use the same 5-level pattern set from `_cell_pattern(x, y, level)`:

| Level | Pattern | Density |
|-------|---------|---------|
| 0 | All white (hollow) | 0% |
| 1 | 5-dot plus shape | ~17% |
| 2 | Horizontal stripes every 3rd row | ~33% |
| 3 | 2×2 checkerboard | 50% |
| 4 | Solid black | 100% |

All cells have a uniform 1px black border (`BORDER_PX = 1`). There is no visual distinction for today's cell.

The PNG encoder (`_make_grayscale_png`, `_png_chunk`) is a minimal pure-Python implementation — no PIL/Pillow. It writes 8-bit grayscale with filter-byte-none on every scanline, using struct for chunk headers/CRCs and zlib for DEFLATE compression.

## Module responsibilities

| Module | Role |
|--------|------|
| `main.py` | Orchestrator — parses CLI args, fetches balance, saves history, dispatches to the correct payload builder, pushes to device |
| `balance_api.py` | DeepSeek `/user/balance` API client — 3-retry with exponential backoff (1s/2s), prefers CNY currency |
| `history.py` | On-disk balance snapshots (`data/balance_history.json`) — 90-day retention, same-date dedup, corruption auto-backup |
| `usage_data.py` | Monthly cost tracking (`data/usage_history.json`) — CSV import, daily cost lookup, monthly accumulation with dedup guard |
| `config.py` | Env-var loading (`DEEPSEEK_API_KEY`, `DOT_API_KEY`, `DOT_DEVICE_ID`, optional `INITIAL_RECHARGE` and `CURRENCY`) |
| `layout.py` | Balance dashboard Canvas payload — left icon column + right info column |
| `heatmap.py` | PNG heatmap generation + standalone heatmap Canvas payload |
| `dashboard.py` | Combined dashboard — left balance column (70px) + right 28-day heatmap |
| `dot_push.py` | Dot Canvas API push — POST to `dot.mindreset.tech`, typed error hierarchy |
| `nfc_report.py` | ASCII bar-chart text report for the Canvas `link` field (NFC tap-to-view) |

## Error handling pattern

When the DeepSeek API is unreachable, the system pushes an **error-state payload** rather than silently failing — the device shows the last known balance (from history), a dimmed icon, and the error reason. This guarantees the screen always displays something useful.

The error exception hierarchy:
- `DeepSeekAuthError` / `DotAuthError` — no retry, shown as "Invalid API key"
- `DeepSeekNetworkError` / `DotPushError` — retried (balance API), shown as "Service unavailable"
- `DeepSeekParseError` / `DotValidationError` — no retry, shown with details

## Data flow: dashboard handler (`_handle_dashboard`)

1. Load history + usage data (always, even for dry-run)
2. If dry-run: use placeholder balance
3. If live: fetch balance from DeepSeek API (with error fallback to last-known balance)
4. Save snapshot to `balance_history.json` (live only, before pushing)
5. Update monthly consumption from balance delta (live only, with dedup guard)
6. Gather 28-day costs (now includes the fresh snapshot just saved)
7. Build dashboard payload via `dashboard.py`
8. Push to device

## Working with the heatmap

When modifying heatmap layout or patterns:
- The grid is rendered as a **single** PNG image — individual cell divs aren't feasible due to the Canvas API's handling of small elements on e-ink
- All geometry constants (`CELL_W`, `CELL_H`, `GAP_X`, `GAP_Y`, `BORDER_PX`) are at the top of `heatmap.py`; there's a separate set (`D4_*`) for the 4-column dashboard variant
- The `_cell_pattern` function receives coordinates relative to the cell interior (after border subtraction)
- `_render_swatch_png` generates the small legend squares using the same pattern function
- Day labels are rendered as separate div elements alongside the PNG image, not baked into the PNG
