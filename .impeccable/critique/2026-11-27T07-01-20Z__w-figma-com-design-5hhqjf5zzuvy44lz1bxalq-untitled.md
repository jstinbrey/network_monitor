---
target: NetMonitor Figma redesign
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-11-27T07-01-20Z
slug: w-figma-com-design-5hhqjf5zzuvy44lz1bxalq-untitled
---
Method: dual-agent (A: design-review agent · B: deterministic Figma-checks agent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | No in-progress state for Diagnose, Traceroute, Check ports, report generation. |
| 2 | Match System / Real World | 3 | ".1 .5 .8", "/24", "TTL", "Packets", "0 means no limit" leak jargon. |
| 3 | User Control and Freedom | 3 | Undo, Cancel, Stop exist; findings can't be dismissed. |
| 4 | Consistency and Standards | 2 | Sample numbers disagree across screens; seven re-check verbs; chip order differs. |
| 5 | Error Prevention | 3 | Confirmations name counts; no last-admin guard shown. |
| 6 | Recognition Rather Than Recall | 3 | Dashboard chart labels devices by last octet. |
| 7 | Flexibility and Efficiency | 2 | No ping count/interval, no Statistics range, no copy/export of ping output. |
| 8 | Aesthetic and Minimalist Design | 3 | Headline and 58/100 gauge compete; a designer note leaked into the UI. |
| 9 | Error Recovery | 3 | Nothing explains how to disconnect 192.168.1.66; no port-check failure state. |
| 10 | Help and Documentation | 2 | No "what's this" for ARP, Telnet, dBm. |
| Total | | 27/40 | Acceptable |

## Design Specificity Verdict

Content product-specific, structure template-like (sidebar, four stat tiles, gauge, chart, list; only Map differs). The This PC → Router → Internet chain should run through the app. Drift from DESIGN.md: green "Live" chips (One Signal Rule), sans measured values in stat tiles, repeated numbers, three primaries on Admin, DESIGN.md dark-mode paragraph contradicts Live-on-Paper.

Deterministic: detect.mjs not applicable (Figma target; --help exit 0). Figma checks: 0 text contrast failures across 1,377 texts (lowest 4.62 light, 4.55 dark; 74 within 0.3); 0 control-edge failures except Icon Button containers at 1.08 (likely false positive: glyph 6.4:1 identifies the control); 0 unbound colors; 0 unstyled texts; 0 dark-mode breaks; 530 unbound radii; 1 clipped text (drawer uptime caption, 38px, light and dark); leftover hand-built copies (3 tooltips, ~9 close buttons, 3 target pickers, Traceroute input, count badge, icon circles); toast × 16px without hit area.

## Priority Issues

1. [P1] Sample data contradicts itself across screens (Printer <1 ms on Ping vs 64 ms elsewhere; "Needs attention 4" lists 3 and links to Security's 9/2/3; TV offline not a Security finding). Fix: one dataset; Needs attention = critical + warning with matching count; slow replies on the Printer ping. /impeccable clarify
2. [P1] Guest path half-designed: no guest Security view, no locked-click flow, User role without purpose. Fix: guest Security, locked click opens sign-in naming the action then runs it, drop or define User. /impeccable shape
3. [P2] Spec defects: blank-disc badge in the open row, clipped uptime caption, tooltips/menus covering content (Rename, Map menu, zoom, Admin menu), toast × without hit area. /impeccable polish
4. [P2] No verdict line on Ping, Map, Devices; seven re-check verbs; three primaries on Admin. /impeccable clarify
5. [P2] Drift from DESIGN.md and leftover hand-built copies; dark instrument cards barely separate in dark mode. /impeccable polish

## Persona Red Flags

Alex: shortcuts only on Map zoom; no ping count/interval/timeout; no Statistics range; bulk bar limited; no copy/export of ping output.
Sam: mouse-only "click a column"; 6 s Undo toast (WCAG 2.2.1); bell dot color-only; Map legend Slow vs No data by color; no status word on online nodes; no focus ring in any screen frame.
Rina: red "At risk" first; jargon; empty Devices doesn't say she can ping now; sign-in prefilled with "admin".

## Minor Observations

"Packets" vs "Continuous" unclear; six Open buttons plus "click one to open it"; lost-reply × reads like a slow reply; "Upload limit 0" vs "No limit set"; Locked vs Disabled differ only by the lock; paused sign-in repeats the rule; 91 unbound radii equal a token value.

## Questions to Consider

- If the headline and the health score can disagree in tone, which is the product's voice?
- What does a guest at the defense do in the first 30 seconds, and which frame shows it?
- Should the This PC → Router → Internet chain become the navigation backbone?
