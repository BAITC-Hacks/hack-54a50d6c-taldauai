"""Check saved API state and DOCX after restarting API/PostgreSQL."""
import argparse
import io
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

parser = argparse.ArgumentParser()
parser.add_argument('--api', default='http://127.0.0.1:8000')
args = parser.parse_args()
state = json.loads((Path(__file__).resolve().parents[1] / 'data/acceptance/state.json').read_text())
with urlopen(args.api + '/api/meetings/' + state['meeting']['id']) as response:
    actual = json.load(response)
assert actual == state['meeting'], 'Meeting changed or was not persisted'
with urlopen(args.api + '/api/notifications') as response:
    notifications = json.load(response)
assert next(n for n in notifications if n['id'] == state['notification_id'])['read_at']
with urlopen(args.api + '/api/meetings/' + actual['id'] + '/export.docx') as response:
    document = response.read()
with ZipFile(io.BytesIO(document)) as archive:
    xml = archive.read('word/document.xml').decode()
for expected in ('Ручное поручение:', 'Юридический отдел', 'Внешний юрист'):
    assert expected in xml, expected
print('PASS: transcript, participants, edits, confirmations, notification read state and DOCX persisted')
