import csv, os, subprocess, sys, time, urllib.request, json
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
Path('results').mkdir(exist_ok=True)
for version in ['sync','bad_async','async']:
 for label,args in [(f'C={n}',['--mode','closed','--clients',str(n)]) for n in [1,10,40,80]]+[('open 5.0/s',['--mode','open','--rate','5'])]:
  existing=list(csv.DictReader(open('results/benchmarks.csv'))) if Path('results/benchmarks.csv').exists() else []
  if any(r['version']==version and r['mode']==label for r in existing): continue
  print('START',version,label,flush=True)
  subprocess.run(['docker','compose','up','-d','--build','--force-recreate','search'],env={**os.environ,'MODE':version},check=True)
  for retry in range(90):
   try:
    with urllib.request.urlopen('http://localhost:8000/health',timeout=3) as response: ready=json.load(response).get('mode')==version
    if ready: break
   except Exception: pass
   time.sleep(2)
  else: raise RuntimeError('Search not ready')
  subprocess.run([sys.executable,'load.py',*args,'--warmup','10','--duration','60'],check=True)
print('ALL_15_DONE',flush=True)
