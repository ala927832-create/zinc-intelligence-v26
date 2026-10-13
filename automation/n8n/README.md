# n8n research-agent deployment

Import the two JSON workflows into n8n. They are intentionally inactive.

## Required environment variables

- `GITHUB_TOKEN`: fine-grained token limited to Actions write on this repository.
- `OPENAI_API_KEY` and optional `OPENAI_MODEL`.
- `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_USER_ID`.

Set the n8n instance timezone to `Asia/Taipei`, use HTTPS, enable 2FA, set a fixed `N8N_ENCRYPTION_KEY`, back up the database, and run the built-in security audit before activation.

## Ownership boundary

- GitHub/Python is the only writer of market history, indicators, decision levels and Pages.
- n8n dispatches the pipeline, validates the committed snapshot, produces a bounded narrative and sends LINE.
- The LLM sees a compact fact object without chart history. It cannot replace nulls or calculate prices.
- The news workflow reads official RSS only. Review the three feed URLs after import because publishers may change endpoints.
- TradingView data is not ingested. Use TradingView manually for visual cross-checking only.

## Activation checklist

1. Import both workflows.
2. Configure environment variables without placing tokens inside node JSON.
3. Run each HTTP node manually and confirm redacted logs.
4. Confirm GitHub workflow finishes and `latest_snapshot.json` has a new `run_time`.
5. Send LINE to a private test user.
6. Force a stale snapshot and confirm the workflow stops before AI and LINE.
7. Activate the market workflow only after the failure tests pass.
