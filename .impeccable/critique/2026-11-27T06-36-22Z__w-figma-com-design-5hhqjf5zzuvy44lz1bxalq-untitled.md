---
target: NetMonitor Figma redesign
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-11-27T06-36-22Z
slug: w-figma-com-design-5hhqjf5zzuvy44lz1bxalq-untitled
---
Method: dual-agent (A: design-review agent · B: deterministic Figma-checks agent)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Dashboard says "healthy" while Security lists 2 critical findings; no sign that watch mode is running. |
| 2 | Match System / Real World | 3 | Verdict copy is excellent; ".1 .5 .8" chart labels, "TTL=64" and "0 means no limit" leak jargon. |
| 3 | User Control and Freedom | 2 | No confirmation or undo for deleting an account, "Clear history…" or "Mark as known". |
| 4 | Consistency and Standards | 2 | Lime means checked, opened, live, primary and highlighted; Map legend wording differs from the table; 29 hand-built pills duplicate the Tag component. |
| 5 | Error Prevention | 3 | IPv4 check, password rules, lockout notice, admin can't delete self. |
| 6 | Recognition Rather Than Recall | 3 | Device picker and quick targets help; Admin row actions are icon-only. |
| 7 | Flexibility and Efficiency | 2 | No shortcuts, Devices can't be sorted, bulk bar only offers Ping and Traceroute. |
| 8 | Aesthetic and Minimalist Design | 3 | Calm and disciplined; "TV offline" appears 4 times on the Dashboard. |
| 9 | Error Recovery | 3 | Diagnosis and IPv4 errors are excellent; wrong password, port-check failure and report-save failure aren't designed. |
| 10 | Help and Documentation | 2 | Good inline explainers; no tooltips, glossary or first-run guide. |
| Total | | 26/40 | Acceptable |

## Design Specificity Verdict

LLM assessment: about half product-specific. The frame is a stock SaaS dashboard (sidebar, hero card, gauge, four stat cards, chart, list); the 92/100 gauge is the most generic and least informative element. Product-specific and strong: the This PC → Router → Internet → DNS diagnosis path with honest failure states, the heart-monitor ping chart, Traceroute's "Your network / Provider / Internet" split, the Wi-Fi channel chart, the router-centred Map. Inconsistency: live data on dark instrument paper (Ping) vs white (Connection). In dark mode the diagnosis card turns near-white and loses the instrument character.

Deterministic scan: detect.mjs not applicable (reads HTML/CSS/JSX or URLs; target is a Figma file; --help exit 0; no substitute files scanned). Figma checks: text contrast 0 failures across 1,340 layers in light and dark (lowest 4.55:1; 73 within 0.3 of the minimum); control-edge contrast 0 failures (lowest 3.23:1, Search); 0 targets under 24px (checkboxes exactly 24); 6 unbound colors (section strokes only); 0 texts without styles; 514 radii not bound to tokens (265 circles/pills, 102 at 2px); 11 text layers clipped 2-3px (drawer "Last 10 tests" time labels light and dark, Tag labels); hand-built copies: 29 pills, 9 badges, 9 inputs, 2 search fields, 2 switches, 3 radios. False positives: 4 "92/100" overlaps with the gauge ring. Disagreement: A's "no focus states" is partly wrong; Button and Nav Item have Focus variants, but chips, filter chips, rows, map nodes and icon buttons do not.

Visual overlays: not available (no web page).

## Priority Issues

1. [P1] "Your network is healthy" while Security has 2 critical findings (ARP spoofing, open Telnet); Needs attention omits the spoofing. Fix: verdict follows the worst severity, score capped when anything is critical, Needs attention sorted critical first. Command: /impeccable harden.
2. [P1] Status by color alone (WCAG 1.4.1): Map node rings and link colors, the drawer's uptime strip, Map legend. Fix: glyph badges on nodes, dash pattern for slow links, hollow/shorter down segments. Command: /impeccable polish.
3. [P1] Focus states only on Button and Nav Item; unlabeled icon buttons (bell, hero ↗, Admin key/people/trash, rename pencil, Map zoom, row ⋯). Fix: Focus variant on every interactive component, tooltips, Admin row actions in a "⋯" menu with text. Command: /impeccable polish.
4. [P2] Destructive and confirm flows not designed: delete account, "Clear history…", "Mark as known" undo, wrong-password and lockout states. Fix: confirmation naming target and consequence with a verb button, Undo toast, two sign-in error states. Command: /impeccable harden.
5. [P2] Lime and red overloaded: Device Row Selected and Open share the lime wash; lime also marks live, primary and highlight; red covers Stop as well as Offline/Critical/Delete. Fix: Open = Mist + ink outline, Stop = ink, red only for failure and destruction. Command: /impeccable colorize.

## Persona Red Flags

Alex: no shortcut hints; Devices unsortable; bulk bar only Ping/Traceroute; Map actions need right-click; drawer hides Latency and Status columns.
Sam: no focus ring on chips, rows, map nodes, icon buttons; canvas Map unreachable by keyboard/screen reader; color-only Map rings and uptime strip; values only on hover; 73 texts near the 4.5:1 line.
Rina (guest classmate at the defense): "Admin sign in" looks mandatory; ".1 .5 .8" and "TTL=64" mean nothing; unlabeled hero ↗; locked Scan does nothing visible (should open sign-in); no guest Security view or pre-scan Dashboard.

## Minor Observations

Components section overlap fixed during the critique; Devices says 12 devices but shows 8 rows with no scroll cue; lost-packet × on the Ping chart sits at ~4.6 ms; Dashboard bars under 10 ms look identical; Connection limit line always red-dashed; Reports has two ways to open the same file; 11 clipped labels (2-3px); hand-built pills/badges/inputs/search/switch/radio not componentized.

## Questions to Consider

- What decision does "92/100" help anyone make that the four-step diagnosis path doesn't already answer?
- Is "healthy" about the connection or about safety? Should the app ever say it while it suspects ARP spoofing?
- What if every live instrument used dark chart paper and everything historical used white?
