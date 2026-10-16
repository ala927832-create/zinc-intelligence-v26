# LINE daily digest — version B

The daily-mode sender uses one Flex message with a single vertical bubble: concise three-point briefing, Gold, LME Cash with separate 3M reference, USD/JPY, DXY, SHFE, Treasury context, and Today/Markets/Radar links. Neutral missing values never borrow another series' change. Each asset retains its own date, source, grade and retrieval status. Gold's GC=F is explicitly a continuous reference, not a dated executable contract. A USD basket or spot gold is not silently relabelled DXY/COMEX.

Prices use a navy band, teal signed up changes and red signed down changes, with gray N/A. Icons are PNG exports of the existing native SVG asset family; zinc remains silver-gray. All text is live Flex text, not a raster screenshot, with wrap enabled and metadata on independent rows. Native rendering varies by device and LINE version. `public/line-preview.html` is an approximate browser view of the actual payload, capped at 430px and usable at 360/390/430px; it is not proof of native LINE rendering.

`validate_line_flex.py` checks the latest frozen payload and calls LINE's `/v2/bot/message/validate/push` when the access-token Secret is configured; this endpoint does not deliver messages and receives no user ID. The daily sender also validates before pushing. A validation failure never falls through to a push. Payload size is checked against 30KB per bubble, with nonempty text and project-only navigation URLs. No credentials, account parameters or private execution records are included in the public preview.

The existing weekday 10:30 daily and 17:30 conditional schedule, unchanged-session suppression and alert-text sender are unchanged. Code pushes do not send LINE messages. No new manual test delivery is introduced.
