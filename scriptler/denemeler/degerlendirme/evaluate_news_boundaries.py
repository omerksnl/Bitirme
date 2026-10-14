from scriptler.lib.metrics import match_boundaries, metrics
"""Kesintisiz, etiketlenmiş kaynak aralıklarında birebir sınır eşleştirmesi."""
import argparse
import json
from pathlib import Path
from scriptler.lib.batch_io import ROOT, digest, save_json




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
