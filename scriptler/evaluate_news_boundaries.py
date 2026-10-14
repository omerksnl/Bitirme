"""Kesintisiz, etiketlenmiş kaynak aralıklarında birebir sınır eşleştirmesi."""
import argparse
import json
from pathlib import Path
from openai_news_batch import ROOT, digest, save_json


def match_boundaries(expected, predicted, tolerance):
    expected,predicted=sorted(set(expected)),sorted(set(predicted))
    table={}
    for i in range(len(expected)+1):
        for j in range(len(predicted)+1):
            if not i or not j:
                table[i,j]=(0,0,[]); continue
            options=[table[i-1,j],table[i,j-1]]
            distance=abs(expected[i-1]-predicted[j-1])
            if distance<=tolerance:
                count,total,pairs=table[i-1,j-1]
                options.append((count+1,total+distance,pairs+[(expected[i-1],predicted[j-1],distance)]))
            table[i,j]=max(options,key=lambda x:(x[0],-x[1]))
    matches=[{'reference':a,'prediction':b,'distance_chars':d} for a,b,d in table[len(expected),len(predicted)][2]]
    used_a={m['reference'] for m in matches}; used_b={m['prediction'] for m in matches}
    tp=len(matches); fp=len(predicted)-tp; fn=len(expected)-tp
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'matches':matches,'missed':sorted(set(expected)-used_a),'extra':sorted(set(predicted)-used_b)}


def evaluate(labels, jobs):
    output={'annotation_author':labels['annotation_author'],'human_approved':labels['human_approved'],
            'scope':'Convenience sample; not corpus-wide quality or independent gold labels','runs':[]}
    for job in jobs:
        manifest=json.loads((job/'manifest.json').read_text(encoding='utf-8'))
        run={'job':str(job),'documents':[]}
        for annotation in labels['documents']:
            doc=next(d for d in manifest['documents'] if d['channel']==annotation['channel'])
            text=(job/doc['snapshot']).read_bytes().decode('utf-8')
            if digest(text.encode('utf-8'))!=annotation['source_sha256']:
                raise ValueError('Etiket kaynağı değişmiş')
            expected=[b['char_position'] for b in annotation['boundaries']]
            meta=json.loads((job/'api_taslaklar'/Path(doc['source']).with_suffix('')/'bolumler.json').read_text(encoding='utf-8'))
            predicted=[s['start_char'] for s in meta['sections'] if annotation['start_char']<s['start_char']<annotation['end_char']]
            run['documents'].append({'channel':annotation['channel'],'exact':match_boundaries(expected,predicted,0),
                                     'within_120_chars':match_boundaries(expected,predicted,120)})
        for metric in ['exact','within_120_chars']:
            tp=sum(d[metric]['tp'] for d in run['documents']); fp=sum(d[metric]['fp'] for d in run['documents']); fn=sum(d[metric]['fn'] for d in run['documents'])
            run[metric]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn), 'f1':2*tp/(2*tp+fp+fn)}
        output['runs'].append(run)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',type=Path,required=True)
    parser.add_argument('--jobs',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=evaluate(json.loads(args.labels.read_text(encoding='utf-8')),args.jobs)
    save_json(args.output,report)
    for run in report['runs']:
        print(Path(run['job']).name, 'exact',run['exact'],'120char',run['within_120_chars'])
