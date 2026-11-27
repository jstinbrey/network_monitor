---
name: NetMonitor
description: A calm network check-up for Windows. Plain verdicts first, the numbers right behind them.
colors:
  bg-canvas: "#F1F2EE"
  bg-surface: "#FFFFFF"
  bg-subtle: "#F6F7F3"
  bg-inverse: "#16191B"
  bg-inverse-hover: "#2D3337"
  border-default: "#E3E5DF"
  border-strong: "#CBD0C7"
  border-control: "#828881"
  text-primary: "#16191B"
  text-secondary: "#555B62"
  text-muted: "#676D75"
  text-on-inverse: "#FFFFFF"
  text-on-inverse-muted: "#A3A9AE"
  accent-lime: "#C8F05A"
  accent-lime-hover: "#B8E24A"
  accent-lime-soft: "#EEF9CF"
  accent-on-lime: "#16191B"
  accent-on-lime-soft: "#16191B"
  accent-on-inverse: "#C8F05A"
  status-online: "#1A7A46"
  status-online-soft: "#E1F3E8"
  status-warn: "#9B5E0A"
  status-warn-soft: "#FCEFD8"
  status-bad: "#BB3636"
  status-bad-soft: "#FBE4E2"
  status-info: "#2B5FCC"
  status-info-soft: "#E3EBFA"
  chart-paper: "#16191B"
  chart-grid: "#2A3034"
  chart-trace: "#C8F05A"
  chart-text: "#FFFFFF"
  chart-text-muted: "#A3A9AE"
  chart-series-2: "#86AAF7"
typography:
  display:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  body:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  body-medium:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "Plus Jakarta Sans, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  mono-display:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.01em"
rounded:
  control: "12px"
  card: "20px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.bg-inverse}"
    textColor: "{colors.text-on-inverse}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.bg-inverse-hover}"
  button-secondary:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.bg-subtle}"
  button-accent:
    backgroundColor: "{colors.accent-lime}"
    textColor: "{colors.accent-on-lime}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "40px"
  button-locked:
    backgroundColor: "{colors.bg-subtle}"
    textColor: "{colors.text-muted}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "40px"
  button-disabled:
    backgroundColor: "{colors.bg-subtle}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.pill}"
    height: "40px"
  button-danger:
    backgroundColor: "{colors.status-bad}"
    textColor: "{colors.text-on-inverse}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "44px"
  input:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "40px"
  card:
    backgroundColor: "{colors.bg-surface}"
    rounded: "{rounded.card}"
    padding: "20px"
  nav-item:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-medium}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    height: "34px"
  nav-item-hover:
    backgroundColor: "{colors.bg-subtle}"
    textColor: "{colors.text-primary}"
  nav-item-active:
    backgroundColor: "{colors.bg-inverse}"
    textColor: "{colors.text-on-inverse}"
  chip-online:
    backgroundColor: "{colors.status-online-soft}"
    textColor: "{colors.status-online}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 12px 4px 8px"
  chip-degraded:
    backgroundColor: "{colors.status-warn-soft}"
    textColor: "{colors.status-warn}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 12px 4px 8px"
  chip-offline:
    backgroundColor: "{colors.status-bad-soft}"
    textColor: "{colors.status-bad}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 12px 4px 8px"
  tag-new:
    backgroundColor: "{colors.accent-lime-soft}"
    textColor: "{colors.accent-on-lime-soft}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  device-row-selected:
    backgroundColor: "{colors.accent-lime-soft}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.control}"
    height: "54px"
  device-row-open:
    backgroundColor: "{colors.bg-subtle}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.control}"
    height: "54px"
---

# Design System: NetMonitor

## Overview

**Creative North Star: "The Network Check-up"**

NetMonitor examines a home or campus network the way a good check-up examines a person: it takes the readings, says in one plain sentence whether things are healthy, and only then shows the charts. The health score, the heart-monitor ping chart and the layer-by-layer diagnosis are the same idea expressed three ways. Every screen leads with a verdict ("Your network is healthy", "Delay starts at hop 5, inside your provider's network", "Printer is the slowest device") and keeps the measurements one glance below it.

The voice is calm and plain, like a technician who has seen this before: it names the problem, then the fix, and never raises its voice until something is actually wrong. The look is soft and confident: a pale grey canvas, white rounded cards, pill buttons, one dark primary action per screen, and a single lime signal for what is live or selected. Density is a desktop tool's density (13px body, 34–54px rows), not a marketing page's.

The visual direction was pinned by the project's inspiration boards (light cards on grey, big numbers, one lime accent). It replaces the earlier default dark CustomTkinter look.

**Key Characteristics:**
- Verdict first, numbers second, raw output last.
- One accent (Signal Lime) for live and selected states only; status has its own colors and always carries a word.
- Light by default with a full dark mode; every color is a token, so dark mode is a value swap, not a redesign.
- Built for CustomTkinter: solid fills, rounded corners and matplotlib charts; nothing that needs blur or gradients.

## Colors

A quiet grey-and-ink neutral system with one bright signal color and four status hues that only ever appear next to words.

### Primary
- **Signal Lime** (accent-lime): the active-signal color. The logo tile, the live trace of the heart-monitor chart, the checked steps of a healthy diagnosis, the selected bar in a chart, and the primary action inside the selection bar. Text on it is always Instrument Ink.
- **Signal Lime Wash** (accent-lime-soft): rows and options that are selected or open, and the "New" tag.

### Neutral
- **Instrument Ink** (bg-inverse, chart-paper): primary buttons, the active nav item, the diagnosis card and the background of every live chart. It reads like the display of a measuring instrument.
- **Bench Grey** (bg-canvas): the window background behind all cards.
- **Paper White** (bg-surface): cards, inputs, menus, the device drawer.
- **Mist** (bg-subtle): table headers, stat tiles inside cards, icon badges, hover rows.
- **Ink, Slate, Pewter** (text-primary, text-secondary, text-muted): body text, supporting text, captions and metadata. Pewter is the floor: nothing lighter is used for text.
- **Hairline and Control Edge** (border-default, border-control): hairlines separate regions; Control Edge outlines every input, checkbox, switch and radio so their boundary clears 3:1.

### Status
- **Online Green, Amber, Alarm Red, Info Blue** (status-online, status-warn, status-bad, status-info), each with a pale wash (`-soft`) used as the chip background. Online/degraded/offline/no-ping-reply map to green/amber/red/amber; findings map Critical/Warning/Info to red/amber/blue.

### Dark mode
Dark mode swaps values, never structure. Canvas `#0F1113`, surface `#181B1E`, subtle `#22262A`; ink and paper trade places (bg-inverse becomes `#ECEDE8` with `#16191B` text), so primary buttons and the active nav item turn light, while live instruments (the diagnosis card, the ping and bandwidth charts) keep their dark Chart Paper (see The Live-on-Paper Rule). Status colors lighten (`#5FCF8E`, `#F0B455`, `#F28585`, `#86AAF7`) on dark washes. Charts keep their dark paper in both modes and use the fixed `chart-text` tokens. The full dark set lives in `.impeccable/design.json`.

### Named Rules
**The One Signal Rule.** Signal Lime means "live" or "selected" and nothing else. It is never a status color: a healthy device is Online Green, not lime.

**The Word-With-Color Rule.** Every status shows a dot or icon plus a word ("Offline", "Up, no ping reply"). Color alone never carries meaning.

**The Lime-on-Ink Rule.** Lime marks that sit on Instrument Ink use `accent-on-inverse`, which becomes dark olive in dark mode; lime is unreadable on the light inverse surface.

**The Live-on-Paper Rule.** Anything that updates while you watch (the ping trace, the bandwidth chart, the diagnosis) sits on Chart Paper in both modes. History, tables and settings sit on Paper White.

**The Red-Means-Loss Rule.** Alarm Red marks failures, critical findings and irreversible actions only. Routine controls such as Stop are Instrument Ink.

## Typography

**Display Font:** Plus Jakarta Sans (with Segoe UI)
**Body Font:** Plus Jakarta Sans (with Segoe UI)
**Label/Mono Font:** Cascadia Mono (with Consolas)

**Character:** A friendly geometric sans for everything a person reads, paired with Windows' own coding mono for everything a machine measured. Plus Jakarta Sans ships with the app; Cascadia Mono comes with Windows 11.

### Hierarchy
- **Display** (600, 32px, 1.1): the big number on stat cards.
- **Headline** (600, 24px, 1.2): page titles and the diagnosis verdict sentence.
- **Title** (600, 15px, 1.3): card and section titles.
- **Body** (400 and 500, 13px, 1.5): sentences, labels on buttons and nav, table text.
- **Label** (500, 12px, 1.4): captions, metadata, chip and tag text. Sentence case, never tracked uppercase.
- **Mono** (400, 12px) and **Mono Display** (600, 28px): IP and MAC addresses, latency, probe times, ping output, the live readout.

### Named Rules
**The Measured-Means-Mono Rule.** A value the network produced (address, time, count of replies) is set in Cascadia Mono; a word a person wrote is set in Plus Jakarta Sans. Mono is never decoration. The one exception is the big Display number on a stat card, which stays in Plus Jakarta Sans so it reads at a glance.

## Layout

The window defaults to 1180×720 and must work at its 1000×640 minimum. A 12px outer margin holds a fixed 212px sidebar card and a main column with 16px gaps between rows of cards.

The sidebar groups ten views under Monitor, Test, Analyze and (for administrators) Manage, with the optional "Admin sign in" button at the upper left under the logo and the current Wi-Fi network and live speeds pinned to the bottom. Each view opens with a title, a one-line subtitle and its actions on the right, then a filter or control bar, then content.

Content flexes rather than breaks: name and router columns grow and truncate with an ellipsis, inputs grow between a minimum and maximum width, charts stretch, side columns wrap below on narrow windows, and the main column scrolls when the window is short. The device drawer is 440px wide and overlays the right side of the current view.

## Elevation & Depth

Tonal first. Cards separate from the canvas by color (Paper White on Bench Grey), not by shadow, so the design holds up in CustomTkinter, which cannot draw shadows without images. The soft ambient shadow in the Figma file is optional polish. Chart Paper cards carry a 1px Strong Hairline edge so they still separate from the canvas in dark mode.

### Shadow Vocabulary
- **Card lift** (`box-shadow: 0 1px 2px rgba(23,26,20,0.04), 0 8px 24px -4px rgba(23,26,20,0.05)`): cards, when the platform can draw it.
- **Overlay** (`box-shadow: 0 24px 64px -8px rgba(13,15,13,0.18)`): dialogs, menus, the device drawer and the floating selection bar. These need it; fake it with a 1px Hairline edge where shadows are unavailable.

### Named Rules
**The Tonal-First Rule.** If removing every shadow makes any card disappear into the canvas, the colors are wrong, not the shadows.

## Shapes

Generous, consistent rounding: 20px on cards and the drawer, 12px on controls, table rows, tiles and menu items, full pills on buttons, chips, tags, filters and the search field. Avatars, icon badges and chart heads are circles. Icons are Lucide outlines at 1.8 stroke, 14–22px.

## Components

### Buttons
- **Shape:** full pill (999px), 40px tall (44px for dialog and form actions).
- **Primary:** Instrument Ink with white text and icon; one per screen.
- **Secondary:** Paper White with an Instrument Ink label; Mist on hover.
- **Locked:** Mist with Pewter text and a lock icon. Shown to guests for admin-only actions so they can see what signing in unlocks. Clicking one opens the sign-in dialog titled with that action ("Sign in to scan the network") and runs the action right after sign-in; Cancel leaves the guest where they were.
- **Hover / Focus / Disabled:** hover darkens one step (`bg-inverse-hover`, Mist); focus adds a 2px Paper White gap and a 2px Instrument Ink ring; disabled is Mist with Pewter text and no outline.
- **Destructive entry point:** Paper White with an Alarm Red outline, icon and label ("Clear history…"). It opens a confirmation; it never deletes on its own.
- **Danger (44px):** Alarm Red with a white label. It appears only inside the confirmation, which names what will be lost, and its label repeats the action ("Delete account", "Clear history"). Easy-to-reverse actions ("Mark as known") skip the dialog and show an Undo toast instead.
- **Icon buttons:** 32px circles in Mist. Every icon-only button carries a tooltip that names the action ("Rename device", "Zoom in · Ctrl +").

### Chips
- **Status chip:** pale wash, colored dot and word. Online, Degraded, Up (no ping reply), Offline, No data.
- **Tag:** small pill next to a name: New (lime wash), Gateway (info wash), This PC (Mist).
- **Filter chips:** pill with a count; the selected one is Instrument Ink with a lime count.

### Cards / Containers
- **Corner Style:** 20px.
- **Background:** Paper White; inner tiles and table headers in Mist.
- **Shadow Strategy:** tonal first (see Elevation & Depth).
- **Internal Padding:** 20px (16px for compact cards, 8px for tables).

### Inputs / Fields
- **Style:** Paper White, 1px Control Edge outline, 12px radius (pill for search and the device picker), 40–44px tall, label above in Label style.
- **Focus:** 2px Instrument Ink outline.
- **Error:** 2px Alarm Red outline and a red message with an alert icon directly under the field, naming the problem and the fix.
- **Device picker:** a pill in Mist with a Control Edge outline: the device's icon in a white circle, its name, its address in mono and a chevron. Type an address or pick a scanned device; free-text targets (Traceroute) drop the chevron.

### Table rows
- **Selected** (ticked for a bulk action): Signal Lime Wash with a checked box.
- **Open** (shown in the device drawer): Mist with a 1.5px Instrument Ink outline and an ink icon badge, so it never looks ticked.
- **Hover:** Mist. **Focus:** 2px Instrument Ink outline.

### Navigation
- **Sidebar items:** 34px rows, icon plus label, Slate text. Hover is Mist; active is Instrument Ink with white text and a lime icon (olive in dark mode); focus is a 2px ink outline.
- **Account area:** guests see "Admin sign in" at the top; administrators see their name, role and a sign-out button in the same place.

### Diagnosis card (signature)
A Chart Paper card with the verdict as a headline, one plain sentence, and four steps (This PC → Router → Internet → DNS) as lime check circles joined by lines. A failed step turns Alarm Red with an ×; untested later steps are dashed and muted, never green. Each step is a Diagnosis Step (Pass, Fail or Not tested). The headline names the worst open finding even when every step connected ("2 security problems found"). The health score sits beside it as a small pill ("Health 58 / 100"), capped while anything critical is open, so the sentence always leads.

### Heart monitor (signature)
The continuous-ping chart: Instrument Ink paper, Signal Lime trace, amber dots for slower-than-usual replies, red × for lost ones, a 5 ms top that grows when a reply exceeds it, and the latest reply as a large mono readout.

### Device drawer (signature)
A 440px panel over the right of the current view: name with a rename pencil, address line, status chip and one-line summary, four stat tiles, the last 10 tests against the device's usual time, a 24-hour uptime strip, open ports with "Check again", and Ping, Continuous ping and Traceroute pinned at the bottom.

## Do's and Don'ts

### Do:
- **Do** open every view with a one-sentence verdict before any table or chart.
- **Do** pair every status color with a word, and keep Signal Lime for live and selected states only.
- **Do** outline inputs, checkboxes, switches and radios in Control Edge (`border-control`) so they clear 3:1 on every surface.
- **Do** show admin-only actions to guests as Locked buttons, not hide them.
- **Do** put the result next to its action: port warnings beside "Check ports", errors under the field that caused them.
- **Do** test every screen at 1000×640 and in dark mode.
- **Do** let the Dashboard verdict and health score follow the worst open finding; never call a network healthy while a critical problem is open.
- **Do** use one verb per action: Scan network (find devices), Re-test devices (ping known devices), Diagnose network (run the chain), Trace, Check ports.

### Don't:
- **Don't** use lime as a status color or as text on a light surface.
- **Don't** put a small label or "eyebrow" above a heading; the heading carries its own weight.
- **Don't** mark severity with a colored strip down the edge of a card; use the icon badge and severity chip.
- **Don't** repeat the same number in two places on one screen.
- **Don't** rely on a shadow to separate a card from the canvas.
- **Don't** use emoji or Unicode glyphs as icons; use the Lucide set.
- **Don't** use Alarm Red for routine controls such as Stop.
