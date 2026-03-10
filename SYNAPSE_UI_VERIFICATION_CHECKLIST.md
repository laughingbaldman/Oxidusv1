# Synapse UI Verification Checklist

Scope: UI-only visual enhancement for Synapse Console theme.

## Core Preservation Checks

- [ ] Conversation, Knowledge, Thoughts, and Admin top navigation routes work as before.
- [ ] Admin sub-tabs (Operations, Systems & Maintenance) switch correctly.
- [ ] Keyboard navigation order and focus-visible states still work.
- [ ] Existing click targets still trigger the same commands and handlers.
- [ ] Existing API calls and payloads remain unchanged.

## Main UI Checks

- [ ] Send Response submits message and updates dialogue stream.
- [ ] Clear Conversation clears current session view.
- [ ] Learning mode buttons (Human, AI, Hybrid) still switch mode.
- [ ] Guided Chat and User-led Chat still apply style changes.
- [ ] Ask Model (Learn), Preview Question, Learning Report still function.
- [ ] Operations mode controls (Chat/Study/Crawl, Start/Stop Crawl) still function.

## Admin UI Checks

- [ ] Admin token unlock works and status refresh updates values.
- [ ] Crawl controls (Start, Resume, Stop, Refresh, settings load/apply/reset) still function.
- [ ] Maintenance & QA actions still execute and return output.
- [ ] Conversation Log and Telemetry refresh/export still function.
- [ ] Systems tab actions (Integrity, Learning Trace, MemryX, Hybrid, reset/cleanup/server) still function.

## Accessibility & Motion Checks

- [ ] ARIA labels and existing semantics remain intact.
- [ ] Contrast remains readable for primary text and controls.
- [ ] prefers-reduced-motion disables decorative animations.
- [ ] No critical information is conveyed only by animation.
