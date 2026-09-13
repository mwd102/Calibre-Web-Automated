import json,csv,io,zipfile,collections,datetime,re,unicodedata
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Rebuild factual curated catalogs from downloaded public archive ZIPs. No network or credentials required.')
parser.add_argument('--nyt', required=True, type=Path)
parser.add_argument('--goodreads', required=True, type=Path)
args=parser.parse_args()
out=Path(__file__).resolve().parents[1]/'cps/data/curated'
out.mkdir(parents=True,exist_ok=True)
def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
nyturl='https://www.kaggle.com/datasets/bryantreese/nyt-bestsellers-1931-2024-fictionnon-fiction'
z=zipfile.ZipFile(args.nyt)
rs=[]
for row in csv.DictReader(io.TextIOWrapper(z.open('merged_genres.csv'))):
    day=datetime.datetime.strptime(row['Date'], '%m-%d-%Y').date()
    if day.year>=2015:
        row['date']=str(day)
        rs.append(row)
group={};dates=collections.defaultdict(set);rejected=collections.Counter()
for r in rs:
 r['Author']=re.split(r',?\s+\(',r['Author'],maxsplit=1)[0].strip().rstrip(',')
 y=int(r['date'][:4]);cat=r['Genre'];key=(y,cat,norm(r['Title']),norm(r['Author']));rank=int(r['Rank'])
 dates[(y,cat)].add(r['date'])
 if not r['Author'].strip() or not r['Title'].strip() or not 1<=rank<=25:
  rejected[(y,cat)]+=1
  continue
 if key not in group:group[key]=dict(year=y,category=cat,title=r['Title'].strip(),authors=[r['Author'].strip()],rank=rank,first_date=r['date'],last_date=r['date'])
 g=group[key];g['rank']=min(g['rank'],rank);g['first_date']=min(g['first_date'],r['date']);g['last_date']=max(g['last_date'],r['date'])
coverage=[]
for (y,c),ds in sorted(dates.items()):
 expected={str(datetime.date(y,1,1)+datetime.timedelta(days=i)) for i in range((datetime.date(y+1,1,1)-datetime.date(y,1,1)).days) if (datetime.date(y,1,1)+datetime.timedelta(days=i)).weekday()==6}
 coverage.append(dict(year=y,category=c,weeks=len(ds),rejected_rows=rejected[(y,c)],expected_weeks=len(expected),missing_dates=sorted(expected-ds),first_date=min(ds),last_date=max(ds)))
(out/'nyt.json').write_text(json.dumps(dict(name='NYT Bestsellers',source=nyturl,note='Public fiction and nonfiction archive. List format is not specified by the archive; paperback, children’s and other specialist lists are not confirmed. Malformed rows without a title, author or plausible rank are excluded. Best recorded ranks apply only to the weeks and entries available here. 2025 onward is not covered.',records=list(group.values()),coverage=coverage),ensure_ascii=False,indent=2)+'\n')
z=zipfile.ZipFile(args.goodreads);rs=list(csv.DictReader(io.TextIOWrapper(z.open('final_books_data_2011_2024.csv'))));groups=collections.defaultdict(list)
for r in rs:
 if int(r['award_year'])>=2015:groups[(int(r['award_year']),r['category'])].append(r)
records=[]
for (y,c),rows in sorted(groups.items()):
 winner=max(rows,key=lambda r:int(r['votes'].replace(',','')))
 records.append(dict(year=y,category=c,title=winner['title'],authors=[winner['author']],source=f'https://www.goodreads.com/choiceawards/best-books-{y}'))
latest='''Fiction|My Friends|Fredrik Backman
Historical Fiction|Atmosphere|Taylor Jenkins Reid
Mystery & Thriller|Not Quite Dead Yet|Holly Jackson
Romance|Great Big Beautiful Life|Emily Henry
Romantasy|Onyx Storm|Rebecca Yarros
Fantasy|Bury Our Bones in the Midnight Soil|V. E. Schwab
Science Fiction|The Compound|Aisling Rawle
Horror|Witchcraft for Wayward Girls|Grady Hendrix
Debut Novel|Alchemised|SenLinYu
Audiobook|Onyx Storm|Rebecca Yarros
Young Adult Fantasy & Sci-Fi|Sunrise on the Reaping|Suzanne Collins
Young Adult Fiction|Fake Skating|Lynn Painter
Nonfiction|Everything Is Tuberculosis|John Green
Memoir|The House of My Mother|Shari Franke
History & Biography|How to Kill a Witch|Claire Mitchell;Zoe Venditozzi'''
for line in latest.splitlines():
 c,t,a=line.split('|');records.append(dict(year=2025,category=c,title=t,authors=a.split(';'),source='https://www.goodreads.com/blog/show/3030-meet-the-winners-of-the-2025-goodreads-choice-awards'))
(out/'goodreads.json').write_text(json.dumps(dict(name='Goodreads Choice',source='https://www.kaggle.com/datasets/krisbruurs/goodreads-choice-awards-2011-2024-books',note='Category winners, 2015–2025. Historical winners are selected by the highest recorded vote count per category in the public archive. 2026 winners have not been announced.',records=records,coverage=[]),ensure_ascii=False,indent=2)+'\n')
# Pulitzer is a separately reviewed all-time catalog; archive rebuilds preserve it.
print('NYT', len(group), 'Goodreads', len(records))
for c in coverage:
 if c['missing_dates']:print('Missing',c)
