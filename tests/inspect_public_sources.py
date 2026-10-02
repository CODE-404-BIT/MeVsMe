from pathlib import Path
from html.parser import HTMLParser
import httpx

class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a' and '/football/teams/' in attrs.get('href',''):self.links.add(attrs['href'])
    def __init__(self):super().__init__();self.links=set()

with httpx.Client(timeout=25,follow_redirects=True) as client:
    for path in ('Armenia/Premier-League','Kazakhstan/Premier-League'):
        response=client.get('https://www.live-result.com/football/'+path)
        parser=Links();parser.feed(response.text)
        Path('data/raw/research/'+path.replace('/','-')+'.html').write_text(response.text,encoding='utf-8')
        print(path,response.status_code,sorted(parser.links))
