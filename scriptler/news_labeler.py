"""Tek kanal için yerel, kaynak konumlarını koruyan haber sınırı etiketleyici."""
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from urllib.parse import urlparse

from daily_news_pipeline import timeline
from openai_news_batch import ROOT,load_json,save_json,digest

DEFAULT=ROOT/'data/etiketleme/KanalD'
UI=ROOT/'web-prototype/public/etiketleme/index.html'
WRITE_LOCK=threading.Lock()


def prepare(project,source,channel,count):
    if (project/'manifest.json').exists(): return load_json(project/'manifest.json')
    files=sorted([p for p in source.iterdir() if p.is_file() and p.suffix.lower() in {'.txt','.srt','.vtt'}],key=lambda p:p.name,reverse=True)
    selected=[]; dates=set()
    for f in files:
        date=f.name[:8]
        if date in dates: continue
        dates.add(date); selected.append(f)
        if len(selected)>=count: break
    if not selected: raise ValueError('Kaynak altyazı bulunamadı')
    corrections=load_json(ROOT/'scriptler/vtt_word_corrections.json'); docs=[]
    for f in sorted(selected):
        raw=f.read_bytes(); data=timeline(raw.decode('utf-8-sig'),corrections); identifier=digest(raw)[:20]
        folder=project/'documents'/identifier; folder.mkdir(parents=True,exist_ok=True)
        (folder/'source.srt').write_bytes(raw); (folder/'transcript.txt').write_bytes(data['text'].encode())
        save_json(folder/'timeline.json',data)
        save_json(folder/'labels.json',{'revision':0,'source_hash':digest(data['text'].encode()),'human_approved':False,
            'boundaries':[{'start_char':0,'kind':'other','title':'Açılış'}],'updated_at':None})
        docs.append({'id':identifier,'date':f.name[:8],'source':str(f.resolve()),'raw_hash':digest(raw),'text_hash':digest(data['text'].encode()),'length':len(data['text'])})
    manifest={'channel':channel,'annotation_policy':'Aynı olayın anonsu, paketi, röportajı ve yorumu birlikte. Farklı olay yeni haber. Selamlama, reklam ve kapanış diğer. Tartışmalı yerler belirsiz işaretlenebilir.','documents':docs}
    save_json(project/'manifest.json',manifest); return manifest


def document(project,identifier):
    manifest=load_json(project/'manifest.json')
    entry=next((d for d in manifest['documents'] if d['id']==identifier),None)
    if not entry: raise ValueError('Bülten bulunamadı')
    folder=project/'documents'/identifier; raw=(folder/'transcript.txt').read_bytes()
    if digest(raw)!=entry['text_hash']: raise ValueError('Kaynak metin değiştirilmiş')
    return entry,raw.decode(),load_json(folder/'labels.json')


def validate_labels(text,payload,revision):
    if not isinstance(payload,dict) or set(payload)!={'revision','human_approved','boundaries'}: raise ValueError('Geçersiz etiket isteği')
    if type(payload['revision'])!=int or payload['revision']!=revision: raise RuntimeError('Başka sekme bu bülteni değiştirdi. Sayfayı yenile.')
    if type(payload['human_approved'])!=bool: raise ValueError('Onay bilgisi geçersiz')
    boundaries=payload['boundaries']; allowed={m.start() for m in re.finditer(r'\S+',text)}|{0}
    if not isinstance(boundaries,list) or not boundaries or len(boundaries)>1000: raise ValueError('Bölüm sayısı geçersiz')
    previous=-1
    for b in boundaries:
        if not isinstance(b,dict) or set(b)!={'start_char','kind','title'}: raise ValueError('Bölüm alanları geçersiz')
        pos=b['start_char']
        if type(pos)!=int or pos not in allowed or pos<=previous: raise ValueError('Başlangıçlar sıralı, tekil ve kelime başında olmalı')
        if b['kind'] not in {'news','other','uncertain'} or not isinstance(b['title'],str) or len(b['title'])>200: raise ValueError('Tür/başlık geçersiz')
        previous=pos
    if boundaries[0]['start_char']!=0: raise ValueError('Bülten başlangıcı korunmalı')
    if payload['human_approved'] and any(b['kind']=='uncertain' for b in boundaries): raise ValueError('Belirsiz bölümler çözülmeden tamamlanmış sayılmaz')
    return {'revision':revision+1,'source_hash':digest(text.encode()),'human_approved':payload['human_approved'],
            'boundaries':boundaries,'updated_at':datetime.now(timezone.utc).isoformat()}


def persist(project,identifier,payload):
    with WRITE_LOCK:
        entry,text,old=document(project,identifier); new=validate_labels(text,payload,old['revision'])
        folder=project/'documents'/identifier
        # An export is an immutable revision: exact source slices plus labels.
        export=folder/'exports'/f"revision_{new['revision']:04d}"; export.mkdir(parents=True,exist_ok=True)
        sections=[]; parts=[]
        for i,b in enumerate(new['boundaries']):
            end=new['boundaries'][i+1]['start_char'] if i+1<len(new['boundaries']) else len(text)
            name=f'{i+1:03d}_{b["kind"]}.txt'; part=text[b['start_char']:end]; parts.append(part)
            (export/name).write_bytes(part.encode()); sections.append({**b,'end_char':end,'file':name})
        if ''.join(parts)!=text: raise ValueError('Kaynak korunamadı')
        save_json(export/'sections.json',{'source':entry['source'],'source_hash':new['source_hash'],'human_approved':new['human_approved'],'sections':sections})
        save_json(folder/'labels.json',new)
        return new


def handler(project):
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,data,mime='application/json; charset=utf-8'):
            raw=json.dumps(data,ensure_ascii=False).encode() if not isinstance(data,bytes) else data
            self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(raw)

        def trusted(self):
            port=self.server.server_port
            hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
            return self.headers.get('Host') in hosts and self.headers.get('Origin') in {None,*('http://'+h for h in hosts)}

        def do_GET(self):
            if not self.trusted(): self.send(403,{'error':'Yalnız yerel erişim'}); return
            path=urlparse(self.path).path
            try:
                if path=='/': self.send(200,UI.read_bytes(),'text/html; charset=utf-8')
                elif path=='/api/documents':
                    manifest=load_json(project/'manifest.json')
                    for d in manifest['documents']:
                        _,_,labels=document(project,d['id']); d['human_approved']=labels['human_approved']; d['sections']=len(labels['boundaries'])
                    self.send(200,manifest)
                elif path.startswith('/api/document/'):
                    entry,text,labels=document(project,path.removeprefix('/api/document/'))
                    self.send(200,{'document':entry,'text':text,'labels':labels})
                else: self.send(404,{'error':'Bulunamadı'})
            except (ValueError,OSError) as error: self.send(400,{'error':str(error)})

        def do_POST(self):
            if not self.trusted(): self.send(403,{'error':'Yalnız yerel erişim'}); return
            path=urlparse(self.path).path
            if not path.startswith('/api/document/'): self.send(404,{'error':'Bulunamadı'}); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1048576 or not self.headers.get('Content-Type','').startswith('application/json'): raise ValueError('Geçersiz içerik')
                payload=json.loads(self.rfile.read(length)); self.send(200,persist(project,path.removeprefix('/api/document/'),payload))
            except RuntimeError as error: self.send(409,{'error':str(error)})
            except (ValueError,TypeError,OSError) as error: self.send(400,{'error':str(error)})
        def log_message(self,*args): pass
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=DEFAULT)
    parser.add_argument('--source',type=Path,default=ROOT/'data/Ekonomi/-Ekonomi_Temiz/KanalD')
    parser.add_argument('--channel',default='KanalD')
    parser.add_argument('--count',type=int,default=5)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.count<1 or not 1024<=args.port<=65535: parser.error('Geçersiz adet veya port')
    manifest=prepare(args.project,args.source,args.channel,args.count)
    print(f"{manifest['channel']}: {len(manifest['documents'])} tam bülten hazır",flush=True)
    if args.prepare_only: return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(args.project))
    print(f'Etiketleme: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__': main()
