from pathlib import Path
from lun import parse_html
FIXTURE=Path('/mnt/data/lun/Купити будинок Львів, продаж приватних будинків.html')
html=FIXTURE.read_text(encoding='utf-8')
listings,total=parse_html(html)
assert total==5502, total
assert len(listings)==24, len(listings)
ids=[x['source_id'] for x in listings]
assert all(ids)
assert len(ids)==len(set(ids))
print('PASS')
print('total:', total)
print('rendered:', len(listings))
print('unique_ids:', len(set(ids)))
