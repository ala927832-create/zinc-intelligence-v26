# Radar history, official events and daily briefing

- Rates preserve original percent units; DXY and the selected asset use a common
  first observation date as index 100. No common baseline means no indexed lines.
- Both panels share dates and cursor; tooltips report original values and units.
  Missing values are N/A; gaps beyond seven calendar days break the line.
- 60/120/all windows count dates in the union of published observations, not
  calendar-day horizons. Source dates and retrieval states remain in Radar.
- BLS iCalendar supplies CPI and Employment Situation with Eastern DST conversion.
  Fed and BoJ HTML calendars supply final meeting dates. Date-only events do not
  acquire an assumed announcement time. All events are scheduled, not actuals.
- Every run fetches the official sources anew; errors/parse failures are visible.
  There is no silent calendar carry-forward. Unscheduled news is explicitly
  not covered. NBS annual-calendar discovery covers economic
  performance and PMI; other China releases remain outside coverage. No forecasts,
  consensus or surprise are made up.
- Upcoming horizon is 45 days. Date-only meetings use the source's calendar date;
  exact timestamps are converted to Asia/Taipei. Source links remain authoritative.
- Today, Radar and the LINE daily message call the same three-point function.
  It describes latest valid price moves, gold/real-yield alignment, and the next
  verified scheduled event. No trading rules or notification cadence change.
- Production checks verify common briefing texts, event dates and Treasury rows.

Official sources:
https://www.bls.gov/schedule/news_release/bls.ics
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm
https://www.stats.gov.cn/english/PressRelease/ReleaseCalendar/

## Evidence-first reading order
Radar now reads: 30-second brief → evidence matrix → historical comparison → upcoming 7 calendar days → collapsed sources and limitations. The 7-day interval is [snapshot Taipei date, date + 7), not seven trading sessions. Later scheduled events remain in collapsed details and retain row-level production verification.

The shared brief labels are major change, important conflict, next checkpoint. Intraday/latest-session moves and medium-term direction are explicitly distinct; no display interpretation changes trade permission. Each asset has its own confirmation, counter-evidence and missing-data notes. Zinc spot/3M quotes, stocks and TC retain their individual dates and providers; levels alone never establish stock-flow or TC trends.

BLS ICS failure or empty parse now tries the official monthly HTML list for every month intersecting the 45-day horizon. Explicit Eastern Time, date and clock are required. Coverage is PARTIAL if any monthly request fails, even when some events are recovered. No date is inferred from the usual weekday pattern. Unavailable/partial coverage remains prominent. Event schedules are not released actuals, consensus forecasts or a complete news feed.
