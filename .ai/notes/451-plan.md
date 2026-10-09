## Plan

**Approach:**
Extract duplicate handle rendering, label rendering, and style constants into shared modules under `src/lib/components/charts/plugins/helpers/renderer/`, and extract line-segment distance calculation into `src/lib/components/charts/plugins/helpers/mouse/geometry.ts`. Both renderers use `positionsLine` and `positionsBox` from `helpers/dimensions/positions.ts` to ensure crisp pixel-aligned rendering across standard and high-DPI (Retina) displays. Then refactor `free-form-line`, `horizontal-line`, `measure`, and `fibonacci` renderers and mouse handlers to consume these shared primitives, removing duplicated constants while maintaining backwards-compatible exports in plugin index barrels. Alternative rejected: placing handle visual constants in `helpers/dimensions/` was rejected in favor of `helpers/renderer/constants.ts` because `dimensions/` contains pure coordinate/geometry math (`positionsLine`, `positionsBox`), whereas visual colors and font styles belong to the renderer domain.

**Files:**
- `frontend/src/lib/components/charts/plugins/helpers/renderer/constants.ts` — create: Centralized drawing handle visual constants (`DEFAULT_HANDLE_COLOR`, `DEFAULT_HANDLE_BORDER_COLOR`, `DEFAULT_HOVER_RING_COLOR`, `DEFAULT_DRAG_RING_COLOR`, `DEFAULT_SELECTED_RING_COLOR`, `HANDLE_RADIUS`) and default label visual constants (`DEFAULT_LABEL_BG_COLOR`, `DEFAULT_LABEL_TEXT_COLOR`, etc.).
- `frontend/src/lib/components/charts/plugins/helpers/renderer/handle-renderer.ts` — create: Shared `drawAnchorHandle` canvas helper supporting DPR scaling, hover/drag highlight rings, ghost preview handles, and crisp 1px borders via `positionsLine`.
- `frontend/src/lib/components/charts/plugins/helpers/renderer/handle-renderer.test.ts` — create: Colocated unit tests for `drawAnchorHandle` covering resting dot, hover ring, drag ring, custom styling overrides, and standard (1x) vs Retina (2x) high-DPI scaling.
- `frontend/src/lib/components/charts/plugins/helpers/renderer/label-renderer.ts` — create: Shared `drawChartLabel` canvas helper supporting background box, accent bar, typography, and center/right/left alignments via `positionsBox` and `positionsLine`.
- `frontend/src/lib/components/charts/plugins/helpers/renderer/label-renderer.test.ts` — create: Colocated unit tests for `drawChartLabel` covering center alignment, right alignment, accent bar, typography, and high-DPI scaling.
- `frontend/src/lib/components/charts/plugins/helpers/renderer/index.ts` — create: Barrel export for shared rendering helpers, constants, and types.
- `frontend/src/lib/components/charts/plugins/helpers/mouse/geometry.ts` — create: Shared Euclidean line segment distance helper `pointToSegmentDistance`.
- `frontend/src/lib/components/charts/plugins/helpers/mouse/geometry.test.ts` — create: Colocated unit tests for `pointToSegmentDistance` covering interior projections, clamped endpoints, collinear points, and degenerate segments.
- `frontend/src/lib/components/charts/plugins/free-form-line/constants.ts` — modify: Remove duplicated handle styling constants.
- `frontend/src/lib/components/charts/plugins/free-form-line/index.ts` — modify: Re-export handle constants from `../helpers/renderer` for backwards compatibility.
- `frontend/src/lib/components/charts/plugins/free-form-line/pane-renderer.ts` — modify: Replace `_drawHandle` and preview cursor ghost handle with `drawAnchorHandle`.
- `frontend/src/lib/components/charts/plugins/free-form-line/mouse.ts` — modify: Replace local `pointToSegmentDistance` with import from `../helpers/mouse/geometry`.
- `frontend/src/lib/components/charts/plugins/horizontal-line/constants.ts` — modify: Remove duplicated handle styling constants.
- `frontend/src/lib/components/charts/plugins/horizontal-line/index.ts` — modify: Re-export handle constants from `../helpers/renderer`.
- `frontend/src/lib/components/charts/plugins/horizontal-line/pane-renderer.ts` — modify: Replace `_drawHandle` and preview ghost handle with `drawAnchorHandle`, and replace `_drawLabel` with `drawChartLabel`.
- `frontend/src/lib/components/charts/plugins/measure/constants.ts` — modify: Remove duplicated handle styling constants.
- `frontend/src/lib/components/charts/plugins/measure/index.ts` — modify: Re-export handle constants from `../helpers/renderer`.
- `frontend/src/lib/components/charts/plugins/measure/pane-renderer.ts` — modify: Replace `_drawAnchorHandle` and preview ghost handle with `drawAnchorHandle`, and replace `_drawLabel` with `drawChartLabel`.
- `frontend/src/lib/components/charts/plugins/measure/mouse.ts` — modify: Replace local `pointToSegmentDistance` with import from `../helpers/mouse/geometry`.
- `frontend/src/lib/components/charts/plugins/fibonacci/constants.ts` — modify: Remove duplicated handle styling constants.
- `frontend/src/lib/components/charts/plugins/fibonacci/index.ts` — modify: Re-export handle constants from `../helpers/renderer`.
- `frontend/src/lib/components/charts/plugins/fibonacci/pane-renderer.ts` — modify: Replace `_drawAnchorHandle` and preview ghost handle with `drawAnchorHandle`.

**Steps:**
1. Create `frontend/src/lib/components/charts/plugins/helpers/renderer/constants.ts`:
   - Export handle visual constants: `DEFAULT_HANDLE_COLOR = '#2962FF'`, `DEFAULT_HANDLE_BORDER_COLOR = '#ffffff'`, `DEFAULT_HOVER_RING_COLOR = 'rgba(41, 98, 255, 0.35)'`, `DEFAULT_DRAG_RING_COLOR = 'rgba(41, 98, 255, 0.6)'`, `DEFAULT_SELECTED_RING_COLOR = 'rgba(41, 98, 255, 0.6)'`, `HANDLE_RADIUS = 5`.
   - Export label visual defaults: `DEFAULT_LABEL_BG_COLOR = '#131722'`, `DEFAULT_LABEL_TEXT_COLOR = '#ffffff'`, `DEFAULT_LABEL_HEIGHT = 18`, `DEFAULT_LABEL_FONT_SIZE = 11`, `DEFAULT_LABEL_PADDING_X = 6`, `DEFAULT_LABEL_CHAR_WIDTH = 6.2`, `DEFAULT_LABEL_MARGIN_X = 8`.
2. Create `frontend/src/lib/components/charts/plugins/helpers/renderer/handle-renderer.ts`:
   - Define interfaces `AnchorHandlePoint` (`{ x: number; y: number; isHovered?: boolean; isDragging?: boolean; isSelected?: boolean }`) and `DrawAnchorHandleOptions` (`{ radius?: number; color?: string; borderColor?: string; borderWidth?: number; hoverRingColor?: string; dragRingColor?: string; ringRadiusOffset?: number; ringLineWidth?: number; alpha?: number }`).
   - Implement `drawAnchorHandle(ctx: CanvasRenderingContext2D, point: AnchorHandlePoint, hpr: number, vpr: number, options?: DrawAnchorHandleOptions): void`:
     - Pixel-align center coordinates using `positionsLine(point.x, hpr, 1).position` and `positionsLine(point.y, vpr, 1).position`.
     - When `point.isHovered` or `point.isDragging`, draw highlight ring circle with `radius + (options?.ringRadiusOffset ?? 4) * hpr` filled with drag/hover ring color and stroked with handle color.
     - Draw inner handle circle with `radius = (options?.radius ?? HANDLE_RADIUS) * hpr`, filled with handle color, bordered with 1.5 * hpr stroke in border color.
     - Respect `options.alpha` if provided (for ghost preview handles).
3. Create colocated test `frontend/src/lib/components/charts/plugins/helpers/renderer/handle-renderer.test.ts`:
   - Unit test resting handle: verifies 1 arc drawn at pixel-aligned position with `DEFAULT_HANDLE_COLOR` and `DEFAULT_HANDLE_BORDER_COLOR`.
   - Unit test hover state: verifies 2 arcs drawn (ring with `DEFAULT_HOVER_RING_COLOR` followed by handle circle).
   - Unit test drag state: verifies 2 arcs drawn (ring with `DEFAULT_DRAG_RING_COLOR`).
   - Unit test custom options: verifies custom radius, colors, and alpha.
   - Unit test high-DPI scaling: compares 1x (`hpr: 1, vpr: 1`) and 2x (`hpr: 2, vpr: 2`) calls, asserting radius scales by `hpr` (5 vs 10) and line width scales by `hpr` (1.5 vs 3).
4. Create `frontend/src/lib/components/charts/plugins/helpers/renderer/label-renderer.ts`:
   - Define interface `ChartLabelConfig` (`{ text: string; x: number; y: number; align?: 'center' | 'right' | 'left'; accentColor?: string; bgColor?: string; textColor?: string; height?: number; fontSize?: number; paddingX?: number; charWidth?: number }`).
   - Implement `drawChartLabel(ctx: CanvasRenderingContext2D, config: ChartLabelConfig, hpr: number, vpr: number): void`:
     - Calculate text width based on `text.length * charWidth + paddingX * 2`.
     - Align x coordinate: if `'right'`, use `positionsBox(config.x - textWidth, config.x, hpr)`; if `'left'`, use `positionsBox(config.x, config.x + textWidth, hpr)`; if `'center'`, use `positionsLine(config.x, hpr, textWidth)`.
     - Compute yBox with `positionsLine(config.y, vpr, height)`.
     - Fill background rect (`bgColor`).
     - If `accentColor` is set, draw accent bar along bottom edge with height `Math.max(1, Math.round(hpr))` and fill `accentColor`.
     - Render text centered in box using `ctx.font = 'bold ' + Math.round(fontSize * vpr) + 'px sans-serif'`, `textAlign = 'center'`, `textBaseline = 'middle'`, fill with `textColor`.
5. Create colocated test `frontend/src/lib/components/charts/plugins/helpers/renderer/label-renderer.test.ts`:
   - Unit test centered label: verifies background `fillRect` dimensions centered on `(x, y)` and `fillText` centered.
   - Unit test right-aligned label: verifies `positionsBox` right edge matches `x`.
   - Unit test accent bar: verifies accent `fillRect` rendered at bottom of box with `accentColor`.
   - Unit test high-DPI scaling: verifies font size and border scaling at 1x vs 2x.
6. Create `frontend/src/lib/components/charts/plugins/helpers/renderer/index.ts`:
   - Re-export `drawAnchorHandle`, `AnchorHandlePoint`, `DrawAnchorHandleOptions` from `./handle-renderer`.
   - Re-export `drawChartLabel`, `ChartLabelConfig` from `./label-renderer`.
   - Re-export all constants from `./constants`.
7. Create `frontend/src/lib/components/charts/plugins/helpers/mouse/geometry.ts` and test `geometry.test.ts`:
   - Export `pointToSegmentDistance(px, py, x1, y1, x2, y2): number`.
   - Test projection on interior, projection before p1, projection after p2, exact point on segment, and zero-length segment.
8. Refactor `free-form-line`:
   - Remove `HANDLE_RADIUS`, `DEFAULT_HANDLE_COLOR`, `DEFAULT_HANDLE_BORDER_COLOR`, `DEFAULT_HOVER_RING_COLOR`, `DEFAULT_DRAG_RING_COLOR`, `DEFAULT_SELECTED_RING_COLOR` from `free-form-line/constants.ts`.
   - Re-export them from `../helpers/renderer` in `free-form-line/index.ts`.
   - In `free-form-line/pane-renderer.ts`, replace `_drawHandle` body with `drawAnchorHandle(ctx, point, hpr, vpr)` and replace preview ghost handle with `drawAnchorHandle(ctx, mouse, hpr, vpr, { alpha: PREVIEW_ALPHA })`.
   - In `free-form-line/mouse.ts`, remove local `pointToSegmentDistance` and import from `../helpers/mouse/geometry`.
9. Refactor `horizontal-line`:
   - Remove duplicated handle styling constants from `horizontal-line/constants.ts`.
   - Re-export handle constants from `../helpers/renderer` in `horizontal-line/index.ts`.
   - In `horizontal-line/pane-renderer.ts`, replace `_drawHandle` and preview ghost handle with `drawAnchorHandle`.
   - Replace `_drawLabel` with `drawChartLabel(ctx, { text: item.label, x: scope.mediaSize.width - HORIZONTAL_LABEL_MARGIN_X, y: item.p1.y, align: 'right', accentColor: HORIZONTAL_LINE_COLOR }, hpr, vpr)`.
10. Refactor `measure`:
   - Remove duplicated handle styling constants from `measure/constants.ts`.
   - Re-export handle constants from `../helpers/renderer` in `measure/index.ts`.
   - In `measure/pane-renderer.ts`, replace `_drawAnchorHandle` and preview ghost handle with `drawAnchorHandle`.
   - Replace `_drawLabel` with `drawChartLabel(ctx, { text: item.label, x: (item.p1.x + item.p2.x) / 2, y: (item.p1.y + item.p2.y) / 2, align: 'center', accentColor: color }, hpr, vpr)`.
   - In `measure/mouse.ts`, remove local `pointToSegmentDistance` and import from `../helpers/mouse/geometry`.
11. Refactor `fibonacci`:
   - Remove duplicated handle styling constants from `fibonacci/constants.ts`.
   - Re-export handle constants from `../helpers/renderer` in `fibonacci/index.ts`.
   - In `fibonacci/pane-renderer.ts`, replace `_drawAnchorHandle` and preview ghost handle with `drawAnchorHandle`.
12. Run the test and lint suites (`./scripts/agent-test frontend`) to ensure all unit tests pass, type checking passes, and linting passes without regressions.

**Verification:**
- AC 1 (Shared `drawAnchorHandle` & unit tests): `npx vitest run frontend/src/lib/components/charts/plugins/helpers/renderer/handle-renderer.test.ts` passes with full coverage of resting, hover, drag, and high-DPI scaling.
- AC 2 (Shared `drawChartLabel` & unit tests): `npx vitest run frontend/src/lib/components/charts/plugins/helpers/renderer/label-renderer.test.ts` passes with full coverage of alignments, accent bar, and typography.
- AC 3 (Shared `pointToSegmentDistance` & unit tests): `npx vitest run frontend/src/lib/components/charts/plugins/helpers/mouse/geometry.test.ts` passes for all projection and edge cases.
- AC 4 (Renderer refactor): `npx vitest run frontend/src/lib/components/charts/plugins/free-form-line/free-form-line.test.ts`, `frontend/src/lib/components/charts/plugins/horizontal-line/horizontal-line.test.ts`, `frontend/src/lib/components/charts/plugins/measure/measure.test.ts`, and `frontend/src/lib/components/charts/plugins/fibonacci/fibonacci.test.ts` all pass cleanly with zero regression.
- AC 5 (Constant deduplication): Verify with `git diff` that handle styling constants are removed from plugin `constants.ts` and centralized in `helpers/renderer/constants.ts`.
- AC 6 (High-DPI rendering): Unit tests in `handle-renderer.test.ts` verify pixel-alignment via `positionsLine` and proportional coordinate/radius scaling at `hpr=1` vs `hpr=2`.
- AC 7 (Quality check): `./scripts/agent-test frontend` passes Gate 0 (svelte-check, eslint, prettier) and Gate 1 tests cleanly.

**Risks / watch-outs:**
- Backwards compatibility of plugin index exports: Tests and downstream modules import `HANDLE_RADIUS`, `DEFAULT_HANDLE_COLOR`, etc. from plugin `index.ts` files. Re-exporting these from `helpers/renderer` in each plugin's `index.ts` preserves external contracts.
- Ghost preview handles: Ghost handles at the cursor during drawing preview share the same dot radius, fill, and border as placed handles, but with `PREVIEW_ALPHA` applied and no hover/drag rings. `drawAnchorHandle` supports `options.alpha` cleanly.
- `positionsLine` centering vs raw scaling: `free-form-line` and `horizontal-line` previously used `positionsLine(coord, ratio, 1).position`, whereas `measure` and `fibonacci` used raw `coord * ratio`. Unifying on `positionsLine` provides crisp 1px borders consistently across all plugins.
- Elliott Wave plugin: Finding 5 in the architecture review specifically targets the 4 active drawing plugins (`free-form-line`, `measure`, `horizontal-line`, `fibonacci`). `elliott-wave` uses slightly different ring opacities and is out of scope for this ticket, but can adopt `drawAnchorHandle` in future tickets.
