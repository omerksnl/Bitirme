"""Source-preserving timed transcript conversion and process locking."""
from contextlib import contextmanager
import os
import re
from scriptler.vtt_to_txt import read_cues, deduplicate, correct_words


@contextmanager
def process_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    handle=(root/'pipeline.lock').open('a+b')
    handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        handle.close(); raise ValueError('Başka pipeline işlemi çalışıyor')
    try:
        yield
    finally:
        handle.close()  # OS lock also releases after a crash.


def timeline(source, corrections):
    cues=read_cues(source)
    if not cues:
        raise ValueError('Geçerli zamanlı altyazı yok; düz TXT otomatik tahmin edilmedi')
    units=[]; parts=[]; offset=0
    # Same rolling overlap rules as the existing converter; retain cue times.
    # At most 200 lexical/punctuation tokens of emitted history are needed.
    from scriptler.vtt_to_txt import WORDS, key
    recent=[]; previous_end=-100.0
    for index,(start,end,text,speaker) in enumerate(cues):
        if end<start or start<0 or (index and start<cues[index-1][0]):
            raise ValueError('Sırasız veya geçersiz altyazı zamanı')
        matches=list(WORDS.finditer(text)); current=[key(m.group()) for m in matches]; overlap=0
        if start-previous_end<=1 and not speaker:
            for size in range(min(len(recent),len(current)),0,-1):
                if recent[-size:]==current[:size]:
                    lexical=sum(bool(re.search(r'\w',token)) for token in current[:size])
                    if lexical>=2 or (size==len(current) and start<previous_end):
                        overlap=size; break
        retained=text[matches[overlap-1].end():].lstrip() if overlap else text
        if retained:
            retained,_=correct_words(retained,corrections)
            if parts:
                offset+=1
            units.append({'id':f'U{len(units):05d}','start_seconds':start,'end_seconds':end,
                          'raw_cue_index':index,'start_char':offset,'text':retained})
            parts.append(retained); offset+=len(retained)
        if speaker or start-previous_end>1:
            recent=[]
        recent=(recent+current[overlap:])[-200:]; previous_end=max(previous_end,end)
    cleaned=' '.join(parts)+'\n'
    expected,_=correct_words(deduplicate(cues)[0],corrections)
    if cleaned!=expected+'\n':
        raise ValueError('Zamanlı çıktı mevcut tekrar temizleme yöntemiyle uyuşmadı')
    return {'text':cleaned,'units':units,'cue_count':len(cues),'timing_precision':'source cue; not exact word time'}
