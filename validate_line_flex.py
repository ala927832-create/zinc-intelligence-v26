"""Validate the generated Flex payload without sending to any recipient."""
import json,os
from pathlib import Path
from zincintel.line_flex import build_daily_flex,validate_structure
from zincintel.line_notify import validate_line_message

def main():
    snapshot=json.loads(Path('data/latest_snapshot.json').read_text())
    message=build_daily_flex(snapshot)
    print(f'LINE Flex local validation: PASS ({validate_structure(message)} bytes)')
    token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN','').strip()
    if token:
        validate_line_message(message,token)
        print('LINE Flex API validation: PASS (no message sent)')
    else:print('LINE Flex API validation: SKIPPED (credential unavailable)')
if __name__=='__main__':main()
