"""Yerel anlamsal birleştirme kapısı; sınır eklemez veya kaynak metni değiştirmez."""
import argparse
import bisect
import json
import math
import os
from pathlib import Path
import re

from scriptler.denemeler.yerel.channel_news_bias import features, scored, select, linear, sigmoid
from scriptler.lib.metrics import match_boundaries
from scriptler.lib.batch_io import ROOT, load_json, save_json, digest

DEFAULT=ROOT/'data/denemeler/olay_birlestirme_01'
BASE=ROOT/'data/denemeler/kanal_bias_tam_02'
MODEL_REVISION='614241f622f53c4eeff9890bdc4f31cfecc418b3'


def norm(word):
    return re.sub(r'[^\w]','',word.translate(str.maketrans('Iİ','ıi')).lower())


def pairs(text,cuts,base_scores):
    if any(type(c)!=int or not 0<c<len(text) for c in cuts) or len(set(cuts))!=len(cuts): raise ValueError('Kaynak dışı veya tekrarlı sınır')
    spans=list(re.finditer(r'\S+',text)); positions=[s.start() for s in spans]; words=[s.group() for s in spans]
    result=[]; ordered=[0]+sorted(set(cuts))+[len(text)]
    for i,pos in enumerate(ordered[1:-1],1):
        word=bisect.bisect_left(positions,pos)
        if word>=len(positions) or positions[word]!=pos: raise ValueError('Sınır kelime başında değil')
        lower=bisect.bisect_left(positions,ordered[i-1]); upper=bisect.bisect_left(positions,ordered[i+1])
        left=words[max(0,word-120):word]; right=words[word:word+120]
        segment_left=words[max(lower,word-120):word]; segment_right=words[word:min(upper,word+120)]
        left_keys={norm(w) for w in left if len(norm(w))>2}; right_keys={norm(w) for w in right if len(norm(w))>2}
        capitals_left={norm(w) for w in left if w[0].isupper()}; capitals_right={norm(w) for w in right if w[0].isupper()}
        numeric={'boundary_score':base_scores.get(pos,0),'lexical_overlap':len(left_keys&right_keys)/max(1,len(left_keys|right_keys)),
            'capital_overlap':len(capitals_left&capitals_right)/max(1,len(capitals_left|capitals_right)),
            'left_size':math.log1p(len(segment_left))/math.log(121),'right_size':math.log1p(len(segment_right))/math.log(121),
            'sentence_start':float(bool(re.search(r'[.!?…]["”]*$',words[word-1])))}
        result.append({'position':pos,'features':numeric,'texts':[' '.join(left),' '.join(right),' '.join(segment_left),' '.join(segment_right)]})
    return result


class Encoder:
    def __init__(self):
        os.environ.setdefault('USE_TF','0')
        import numpy as np
        import torch
        from transformers import AutoTokenizer,AutoModel
        self.np=np; self.torch=torch
        folder=ROOT/'work/models/multilingual-e5-small'
        revision=load_json(ROOT/'work/models/e5_revision.json')
        if revision['revision']!=MODEL_REVISION: raise ValueError('Yerel model sürümü farklı')
        self.tokenizer=AutoTokenizer.from_pretrained(folder,local_files_only=True,trust_remote_code=False)
        self.model=AutoModel.from_pretrained(folder,local_files_only=True,trust_remote_code=False,use_safetensors=True)
        self.device='cuda' if torch.cuda.is_available() else 'cpu'; self.model.to(self.device).eval(); torch.set_num_threads(4)
        if self.device=='cuda': self.model.half()
        print('Yerel anlamsal model:',self.device,flush=True)

    def add(self,rows):
        import torch.nn.functional as F
        examples=['query: '+(t or '…') for r in rows for t in r['texts']]
        cache=ROOT/'work/event_merge_embeddings'; cache.mkdir(parents=True,exist_ok=True)
        key=digest((MODEL_REVISION+'\n'+json.dumps(examples,ensure_ascii=False)).encode()); path=cache/(key+'.npy')
        if path.exists(): vectors=self.np.load(path,allow_pickle=False)
        else:
            batches=[]
            for start in range(0,len(examples),32):
                batch=self.tokenizer(examples[start:start+32],padding=True,truncation=True,max_length=512,return_tensors='pt').to(self.device)
                with self.torch.inference_mode():
                    hidden=self.model(**batch).last_hidden_state.float(); mask=batch['attention_mask'].unsqueeze(-1)
                    pooled=(hidden*mask).sum(1)/mask.sum(1)
                    batches.append(F.normalize(pooled,p=2,dim=1).cpu().numpy())
            vectors=self.np.concatenate(batches); self.np.save(path,vectors,allow_pickle=False)
        if len(vectors)!=len(examples): raise ValueError('Embedding cache boyutu geçersiz')
        for i,row in enumerate(rows):
            v=vectors[4*i:4*i+4]
            row['features'].update(context_similarity=float(v[0]@v[1]),section_similarity=float(v[2]@v[3]))
        return rows


def decisions(rows,model,threshold):
    return [{'position':r['position'],'keep_score':sigmoid(linear(r['features'],model)),
             'decision':'keep' if sigmoid(linear(r['features'],model))>=threshold else 'merge',
             'features':r['features']} for r in rows]


def export_merged(text,original_cuts,decisions_list,folder):
    if folder.exists(): raise ValueError('Birleştirilmiş çıktı var; üzerine yazılmadı')
    known=set(original_cuts)
    word_starts={m.start() for m in re.finditer(r'\S+',text)}
    if len(known)!=len(original_cuts) or any(c<=0 or c>=len(text) or c not in word_starts for c in known): raise ValueError('Kaynak sınırları geçersiz')
    if {d['position'] for d in decisions_list}!=known or len(decisions_list)!=len(known): raise ValueError('Kararlar sınırlarla uyuşmuyor')
    if any(d['decision'] not in {'keep','merge'} for d in decisions_list): raise ValueError('Geçersiz karar')
    kept=sorted(d['position'] for d in decisions_list if d['decision']=='keep'); starts=[0]+kept
    folder.mkdir(parents=True); sections=[]; parts=[]
    for i,start in enumerate(starts):
        end=starts[i+1] if i+1<len(starts) else len(text); name=f'taslak_{i+1:03d}.txt'; part=text[start:end]
        (folder/name).write_bytes(part.encode()); parts.append(part); sections.append({'file':name,'start_char':start,'end_char':end,'needs_review':True})
    if ''.join(parts)!=text: raise ValueError('Kaynak metin kaybı')
    save_json(folder/'sections.json',{'text_preserved':True,'human_approved':False,'sections':sections,'decisions':decisions_list})
    return kept


def run(job):
    if job.exists(): raise ValueError('Deneme var; ayrı --job seç')
    profile=load_json(BASE/'profile.json'); labels=load_json(BASE/'labels.json'); encoder=Encoder(); datasets=[]
    for doc in labels['documents']:
        if doc['split']=='test': continue
        data=load_json(BASE/doc['timeline']); candidates=scored(features(data['text'],data['units']),profile,profile['alpha'])
        original=select(candidates,profile['threshold']); cuts=[c['position'] for c in original]; expected=[b['char_position'] for b in doc['boundaries']]
        # Training includes true starts and automatically proposed false starts.
        # Ambiguous nearby shifted candidates are omitted from training targets.
        training_cuts=sorted(set(cuts+expected)) if doc['split']=='train' else cuts
        rows=encoder.add(pairs(data['text'],training_cuts,{c['position']:c['score'] for c in candidates}))
        datasets.append({'date':doc['date'],'split':doc['split'],'rows':rows,'cuts':cuts,'expected':expected})
        print(doc['date'],len(rows),'anlamsal sınır karşılaştırması',flush=True)
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    train_rows=[]; y=[]
    for d in datasets:
        if d['split']!='train': continue
        for r in d['rows']:
            nearest=min(abs(r['position']-p) for p in d['expected'])
            if nearest!=0 and nearest<=80: continue
            train_rows.append(r['features']); y.append(int(nearest==0))
    vectorizer=DictVectorizer(); matrix=vectorizer.fit_transform(train_rows)
    classifier=LogisticRegression(C=1,class_weight='balanced',max_iter=500,random_state=42).fit(matrix,y)
    model={'intercept':float(classifier.intercept_[0]),'weights':dict(zip(vectorizer.get_feature_names_out(),map(float,classifier.coef_[0])))}
    dev=next(d for d in datasets if d['split']=='development'); base=match_boundaries(dev['expected'],dev['cuts'],0); trials=[]
    for threshold in [.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95]:
        ds=decisions(dev['rows'],model,threshold); kept=[x['position'] for x in ds if x['decision']=='keep']; metric=match_boundaries(dev['expected'],kept,0)
        trials.append({'threshold':threshold,'exact':metric,'retains_90_percent_of_existing_true':metric['tp']>=.9*base['tp']})
    eligible=[t for t in trials if t['retains_90_percent_of_existing_true']]
    if not eligible: raise ValueError('Geliştirmede doğru sınır koruması sağlanamadı')
    best=max(eligible,key=lambda t:(t['exact']['f1'],t['exact']['tp'],t['threshold']))
    job.mkdir(parents=True)
    frozen={'model':model,'threshold':best['threshold'],'encoder_revision':MODEL_REVISION,'training_dates':[d['date'] for d in datasets if d['split']=='train'],
        'development_date':dev['date'],'human_approved':False,'scores_calibrated':False,'selection':'Development F1, at least 90% of previously correct development cuts retained'}
    save_json(job/'merge_model.json',frozen); save_json(job/'development_trials.json',trials)
    print('Birleştirme eşiği:',best['threshold'],flush=True)
    # No fresh reference is loaded until all decisions have been persisted.
    source_meta=next((BASE/'fresh_auto').rglob('sections.json')); source=load_json(source_meta); text=(source_meta.parent/'transcript.txt').read_bytes().decode()
    data=load_json(BASE/'fresh_reference/timeline.json')
    if data['text']!=text: raise ValueError('Yeni günün kaynak kopyaları uyuşmuyor')
    cuts=[s['start_char'] for s in source['sections'] if s['start_char']>0]
    scores={c['position']:c['score'] for c in scored(features(text,data['units']),profile,profile['alpha'])}
    rows=encoder.add(pairs(text,cuts,scores)); ds=decisions(rows,model,best['threshold']); save_json(job/'fresh_decisions_before_evaluation.json',ds)
    kept=export_merged(text,cuts,ds,job/'merged_drafts')
    ref=load_json(ROOT/'data/incelemeler/KanalD/2025-01-28/inceleme.json')
    if ref['source_sha256']!=digest(text.encode()): raise ValueError('Referans kaynağı farklı')
    expected=[s['start_char'] for s in ref['sections'] if s['start_char']>0]
    before=match_boundaries(expected,cuts,0); after=match_boundaries(expected,kept,0)
    report={'human_approved':False,'not_independent_gold':True,'date':'2025-01-28','before':before,'after':after,
        'before_within_80':match_boundaries(expected,cuts,80),'after_within_80':match_boundaries(expected,kept,80),
        'false_cuts_removed':before['fp']-after['fp'],'correct_cuts_lost':before['tp']-after['tp'],'cuts_before':len(cuts),'cuts_after':len(kept),'text_preserved':True,'api_calls':0}
    save_json(job/'evaluation.json',report)
    for name in ['before','after']: print(name,{k:report[name][k] for k in ['tp','fp','fn','f1']},flush=True)


def apply_saved(model_path,source_meta,output):
    if output.exists(): raise ValueError('Çıktı var; mevcut sonuçlar korunuyor')
    frozen=load_json(model_path)
    if frozen['encoder_revision']!=MODEL_REVISION: raise ValueError('Encoder sürümü uyuşmuyor')
    source=load_json(source_meta); text=(source_meta.parent/'transcript.txt').read_bytes().decode()
    if ''.join((source_meta.parent/s['file']).read_bytes().decode() for s in source['sections'])!=text:
        raise ValueError('Otomatik bölümler kaynakla uyuşmuyor')
    boundaries=[s for s in source['sections'] if s['start_char']>0]
    if any(type(s.get('score')) not in {int,float} for s in boundaries):
        raise ValueError('Başlangıç modelinin sınır puanları gerekli')
    cuts=[s['start_char'] for s in boundaries]; scores={s['start_char']:s['score'] for s in boundaries}
    rows=Encoder().add(pairs(text,cuts,scores)); ds=decisions(rows,frozen['model'],frozen['threshold'])
    kept=export_merged(text,cuts,ds,output)
    print('Sınır:',len(cuts),'->',len(kept),'Kaynak korundu; anlamsal kalite doğrulanmadı.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--job',type=Path,default=DEFAULT)
    parser.add_argument('--apply',type=Path,help='Sınır puanlarını içeren sections.json; referans gerektirmez')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.apply:
        if not args.output: parser.error('--output gerekli')
        apply_saved(args.job/'merge_model.json',args.apply,args.output)
    else: run(args.job)
