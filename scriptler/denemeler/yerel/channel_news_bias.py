"""Örneklerden öğrenilen kanal önceliği; kelime/olay listesi içermeyen yerel pilot."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from scriptler.lib.timeline import timeline, process_lock
from scriptler.lib.metrics import match_boundaries
from scriptler.lib.batch_io import ROOT, digest, load_json, save_json
from scriptler.vtt_to_txt import read_cues

DEFAULT=ROOT/'data/denemeler/kanal_bias_01'
NUMERIC=['cue_start','sentence_start','pause','novelty','uppercase','previous_question']


def features(text,units):
    spans=list(re.finditer(r'\S+',text)); words=[s.group() for s in spans]
    normalized=[re.sub(r'[^\w]','',w.translate(str.maketrans('Iİ','ıi')).lower()) for w in words]
    cues={u['start_char']:u for u in units}; pauses={}
    previous_end=0
    for u in units:
        pauses[u['start_char']]=max(0,min(5,u['start_seconds']-previous_end))/5
        previous_end=max(previous_end,u['end_seconds'])
    result=[]
    for i,s in enumerate(spans):
        if i==0: continue
        left=normalized[max(0,i-60):i]; right=normalized[i:i+8]
        row={'cue_start':float(s.start() in cues),'sentence_start':float(bool(re.search(r'[.!?…]["”]*$',words[i-1]))),
             'pause':pauses.get(s.start(),0),'novelty':len(set(right)-set(left))/max(1,len(set(right))),
             'uppercase':float(words[i][0].isupper()),'previous_question':float(words[i-1].endswith('?'))}
        # Relative positions, rather than topic-only bags. Coefficients are
        # learned from labels; no channel-specific trigger words in the code.
        for n in [1,2,3]:
            phrase=' '.join(normalized[i:i+n])
            if phrase: row[f'prefix{n}={phrase}']=1.
        for n in [1,2]:
            row[f'left{n}='+ ' '.join(normalized[max(0,i-n):i])]=1.
        for w in set(right):
            if w: row['right='+w]=1.
        result.append({'position':s.start(),'word_index':i,'features':row})
    return result


def sigmoid(value):
    return 1/(1+math.exp(-max(-50,min(50,value))))


def linear(row,model):
    return model['intercept']+sum(v*model['weights'].get(k,0) for k,v in row.items())


def scored(candidates,profile,alpha):
    values=[]
    for c in candidates:
        base=linear(c['features'],profile['generic'])
        adapted=linear(c['features'],profile['channel_model'])
        value=base+alpha*(adapted-base)
        values.append({**c,'score':sigmoid(value),'generic_logit':base,'channel_bias_logit':alpha*(adapted-base)})
    return values


def select(candidates,threshold,gap=12):
    chosen=[]
    for c in sorted(candidates,key=lambda c:(-c['score'],c['position'])):
        if c['score']>=threshold and all(abs(c['word_index']-o['word_index'])>=gap for o in chosen):
            chosen.append(c)
    return sorted(chosen,key=lambda c:c['position'])


def fit_model(rows,y,lexical):
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    vec=DictVectorizer()
    restricted=[r if lexical else {k:v for k,v in r.items() if k in NUMERIC} for r in rows]
    matrix=vec.fit_transform(restricted)
    clf=LogisticRegression(C=.3,class_weight='balanced',max_iter=500,random_state=42).fit(matrix,y)
    return {'intercept':float(clf.intercept_[0]),'weights':dict(zip(vec.get_feature_names_out(),map(float,clf.coef_[0])))}


def dataset(job):
    labels=load_json(job/'labels.json'); result=[]
    for d in labels['documents']:
        data=load_json(job/d['timeline'])
        if digest(data['text'].encode())!=d['text_hash']: raise ValueError('Etiket kaynağı değişmiş')
        text=data['text'][:d['annotated_end_char']]
        candidates=features(text,data['units'])
        expected=[b['char_position'] for b in d['boundaries']]
        if not set(expected)<=set(c['position'] for c in candidates): raise ValueError('Etiket bir kelime başlangıcı değil')
        result.append({**d,'data':data,'candidates':candidates,'expected':expected})
    return labels,result


def measure(docs,profile,alpha,threshold):
    results=[]
    for d in docs:
        chosen=select(scored(d['candidates'],profile,alpha),threshold)
        predicted=[c['position'] for c in chosen]
        results.append({'date':d['date'],'exact':match_boundaries(d['expected'],predicted,0),
                        'within_80_chars':match_boundaries(d['expected'],predicted,80)})
    totals={}
    for mode in ['exact','within_80_chars']:
        tp=sum(d[mode]['tp'] for d in results); fp=sum(d[mode]['fp'] for d in results); fn=sum(d[mode]['fn'] for d in results)
        totals[mode]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn) if tp+fn else 0,
                      'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0}
    return {'documents':results,**totals}


def train(job):
    labels,docs=dataset(job); training=[d for d in docs if d['split']=='train']; development=[d for d in docs if d['split']=='development']
    if not training or not development: raise ValueError('Ayrı eğitim ve geliştirme günleri gerekli')
    if any(not d.get('annotation_complete') for d in training+development): raise ValueError('Eğitim/geliştirme etiketleri tamamlanmamış')
    rows=[c['features'] for d in training for c in d['candidates']]
    y=[int(c['position'] in d['expected']) for d in training for c in d['candidates']]
    if not any(y) or all(y): raise ValueError('Hem haber sınırı hem devam örnekleri gerekli')
    profile={'channel':labels['channel'],'human_approved':False,'probabilities_calibrated':False,
             'format_version':1,'annotation_hash':digest(json.dumps(labels,sort_keys=True).encode()),
             'generic':fit_model(rows,y,False),'channel_model':fit_model(rows,y,True),
             'training_dates':[d['date'] for d in training],'development_dates':[d['date'] for d in development],
             'training_hashes':[d['text_hash'] for d in training], 'policy':'Learned lexical bias; no forced splits; all output is draft'}
    trials=[]
    for alpha in [0,.25,.5,.75,1]:
        for threshold in [.35,.5,.65,.8,.9,.95,.98,.995]:
            metric=measure(development,profile,alpha,threshold)
            trials.append({'alpha':alpha,'threshold':threshold,'exact':metric['exact'],'within_80_chars':metric['within_80_chars']})
    # Thresholds/alpha selected only on development; test is untouched.
    best=max(trials,key=lambda x:(x['exact']['f1'],x['within_80_chars']['f1'],-x['alpha'],x['threshold']))
    baseline=max([t for t in trials if t['alpha']==0],key=lambda x:(x['exact']['f1'],x['within_80_chars']['f1'],x['threshold']))
    profile.update(alpha=best['alpha'],threshold=best['threshold'],baseline_threshold=baseline['threshold'])
    save_json(job/'profile.json',profile); save_json(job/'development_trials.json',trials)
    print(f"Profil: {profile['channel']}; alpha={profile['alpha']}; eşik={profile['threshold']}; yalnız geliştirme gününde seçildi")


def evaluate(job):
    labels,docs=dataset(job); profile=load_json(job/'profile.json'); testing=[d for d in docs if d['split']=='test']
    if set(d['date'] for d in testing)&set(profile['training_dates']+profile['development_dates']): raise ValueError('Test günleri eğitimle örtüşüyor')
    if not testing or any(not d.get('annotation_complete') for d in testing): raise ValueError('Test etiketleri tamamlanmamış; başarı ölçülemez')
    report={'human_approved':False,'annotation_author':labels['annotation_author'],'not_independent_gold':True,
            'test_dates':[d['date'] for d in testing], 'scope':labels.get('evaluation_scope','Annotated bulletin prefixes, not full broadcasts'),
            'baseline':measure(testing,profile,0,profile['baseline_threshold']),
            'channel_bias':measure(testing,profile,profile['alpha'],profile['threshold'])}
    save_json(job/'test_report.json',report)
    for name in ['baseline','channel_bias']: print(name,report[name]['exact'])


def convert_with_profile(source,profile,output,corrections):
    if read_cues(source):
        data=timeline(source,corrections); data['timing_available']=True
    else:
        if source.lstrip('\ufeff').startswith('WEBVTT') or not source.strip():
            raise ValueError('Boş metin veya bozuk VTT')
        # Existing TXT remains byte-for-byte intact as Unicode text. Missing
        # timing is explicit; no artificial cue times or duration guesses.
        data={'text':source,'units':[],'timing_available':False}
    candidates=features(data['text'],data['units'])
    selected=select(scored(candidates,profile,profile['alpha']),profile['threshold'])
    output.mkdir(parents=True,exist_ok=True)
    if (output/'sections.json').exists(): return 'existing'
    (output/'transcript.txt').write_bytes(data['text'].encode()); save_json(output/'timeline.json',data)
    cuts=[0]+[c['position'] for c in selected]; pieces=[]; sections=[]
    for i,start in enumerate(cuts):
        end=cuts[i+1] if i+1<len(cuts) else len(data['text']); part=data['text'][start:end]; name=f'taslak_{i+1:03d}.txt'
        (output/name).write_bytes(part.encode()); pieces.append(part)
        sections.append({'file':name,'start_char':start,'end_char':end,'score':selected[i-1]['score'] if i else None,'needs_review':True})
    assert ''.join(pieces)==data['text']
    save_json(output/'sections.json',{'channel':profile['channel'],'human_approved':False,'text_preserved':True,
        'profile_hash':digest(json.dumps(profile,sort_keys=True).encode()),'sections':sections})
    return 'created'


def convert_directory(args,profile,corrections):
    if not args.input.exists(): raise ValueError('Girdi klasörü bulunamadı')
    files=[args.input] if args.input.is_file() else sorted(f for f in args.input.rglob('*') if f.suffix.lower() in {'.vtt','.srt','.txt'} and f.is_file())
    base=args.input.parent if args.input.is_file() else args.input
    if args.output.resolve()==base.resolve() or base.resolve() in args.output.resolve().parents: raise ValueError('Çıktı kaynak dışında olmalı')
    counts=Counter(); entries=[]
    with process_lock(args.output):
        for f in files:
            raw=f.read_bytes(); version=digest(raw+json.dumps(profile,sort_keys=True).encode()+json.dumps(corrections,sort_keys=True).encode())[:20]
            folder=args.output/f.relative_to(base).with_suffix('')/version
            try:
                result=convert_with_profile(raw.decode('utf-8-sig'),profile,folder,corrections); counts[result]+=1
                entries.append({'source':str(f.resolve()),'output':str(folder.resolve()),'status':result,'source_hash':digest(raw)})
            except (ValueError,UnicodeError,OSError) as error:
                counts['error']+=1; entries.append({'source':str(f),'status':'error','error':str(error)})
        save_json(args.output/'last_run.json',{'counts':dict(counts),'files':entries,'human_approved':False})
    print(dict(counts))
    return 1 if counts['error'] else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['train','evaluate','convert'])
    parser.add_argument('--job',type=Path,default=DEFAULT)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='train': train(args.job)
    elif args.command=='evaluate': evaluate(args.job)
    else:
        if not args.input or not args.output: parser.error('--input ve --output gerekli')
        profile=load_json(args.job/'profile.json'); corrections=load_json(ROOT/'scriptler/config/vtt_word_corrections.json')
        return convert_directory(args,profile,corrections)


if __name__=='__main__': raise SystemExit(main())
