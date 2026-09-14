import asyncio
from lun_browser import crawl_lun_all_pages
async def main():
    listings=await crawl_lun_all_pages(max_pages=10)
    ids=[x['source_id'] for x in listings]
    print('Listings collected:',len(listings))
    print('Unique IDs:',len(set(ids)))
    if not ids or len(ids)!=len(set(ids)): raise SystemExit('FAIL')
asyncio.run(main())
