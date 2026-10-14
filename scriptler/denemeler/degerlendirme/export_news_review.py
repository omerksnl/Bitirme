"""İncelenmiş kaynak sınırlarını metni değiştirmeden haber TXT'lerine çıkarır."""
import argparse
from pathlib import Path
from scriptler.lib.batch_io import load_json, save_json, digest


def export(source,review,output):
    raw=source.read_bytes(); text=raw.decode('utf-8')
    if digest(raw)!=review['source_sha256']: raise ValueError('İncelenen kaynak değişmiş')
    if output.exists(): raise ValueError('Çıktı var; mevcut inceleme korunuyor')
    sections=review['sections']; starts=[s['start_char'] for s in sections]
    if not starts or starts[0]!=0 or starts!=sorted(set(starts)): raise ValueError('Sınırlar geçersiz')
    if any(not 0<=s<len(text) for s in starts): raise ValueError('Kaynak dışında sınır')
    output.mkdir(parents=True); parts=[]; result=[]; count=0
    for i,s in enumerate(sections):
        end=starts[i+1] if i+1<len(starts) else len(text); part=text[starts[i]:end]
        if s['kind']=='news': count+=1; name=f'{count:02d}_haber.txt'
        else: name=f'diger_{i+1:02d}.txt'
        (output/name).write_bytes(part.encode()); parts.append(part); result.append({**s,'end_char':end,'file':name})
    if ''.join(parts)!=text: raise ValueError('Metin korunamadı')
    save_json(output/'haberler.json',{**review,'sections':result,'text_preserved':True,'news_count':count})
    listing=['# '+review['channel']+' — '+review['date'],'','İnceleyen: Codex. İnsan onaylı gold veri değildir. Kaynak metin değişmedi.','']
    for s in result:
        listing.append(f"- [{s['title']}]({s['file']}) — {s['kind']}")
    (output/'HABER_LISTESI.md').write_text('\n'.join(listing),encoding='utf-8')
    return count


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--source',type=Path,required=True); p.add_argument('--review',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print('Haber:',export(a.source,load_json(a.review),a.output))
