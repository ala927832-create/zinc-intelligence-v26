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
  There is no silent calendar carry-forward. China calendars and unscheduled
  news are explicitly not covered. No forecasts, consensus or surprise are made up.
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
