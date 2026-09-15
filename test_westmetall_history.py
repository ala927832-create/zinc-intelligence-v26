from datetime import datetime, timezone
from unittest.mock import patch

from zincintel.free_mirrors import fetch_westmetall


def html(year: int) -> str:
    return f"""<table><tr><th>date</th><th>LME Zinc Cash-Settlement</th><th>LME Zinc 3-month</th><th>LME Zinc stock</th></tr>
    <tr><td>02. January {year}</td><td>3,000.00</td><td>{year}.00</td><td>100,000</td></tr></table>"""


class Response:
    def __init__(self, text): self.text = text
    def raise_for_status(self): return None


def main() -> None:
    current = datetime.now(timezone.utc).year
    def get(url, **kwargs):
        year = int(url.rsplit("=", 1)[-1])
        return Response(html(year))
    with patch.dict("os.environ", {"WESTMETALL_HISTORY_START_YEAR":"2025"}), patch("zincintel.free_mirrors.requests.get", side_effect=get) as mocked:
        values, as_of, status, error, history = fetch_westmetall()
    assert mocked.call_count == current - 2024
    assert len(history) == current - 2024 and history.index.min().year == 2025
    assert as_of == f"{current}-01-02" and values["lme_3m"] == float(current)
    assert status in {"PUBLIC_REFERENCE_DAY_DELAYED", "STALE_PUBLIC_REFERENCE"} and error is None
    print("Westmetall multi-year history tests passed")


if __name__ == "__main__":
    main()
