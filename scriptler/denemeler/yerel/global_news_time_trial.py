"""Bütün bülten için yerel bölümleme: kaynak sınır puanı, süre öncülü ve anlam bütünlüğü."""
from __future__ import annotations
from scriptler.lib.metrics import match_boundaries, metrics
import argparse
import bisect
import itertools
import json
import math
from pathlib import Path
import re
import time

import numpy as np

from scriptler.denemeler.yerel.channel_news_bias import features, scored, select
from scriptler.lib.timeline import process_lock, timeline
from scriptler.lib.metrics import match_boundaries
from scriptler.lib.batch_io import ROOT, digest, load_json, save_json
from scriptler.denemeler.yerel.same_event_merge import Encoder, MODEL_REVISION

BASE = ROOT / 'data/denemeler/kanal_bias_tam_02'
DEFAULT = ROOT / 'data/denemeler/butun_bulten_zamanli_02'
VERSION = 'global-dp-v1'


def source_axis(data):
    """Kelime zamanları altyazı aralığında doğrusal tahmindir; gerçek kelime hizalaması değildir."""
    text = data['text']
    spans = list(re.finditer(r'\S+', text))
    positions = np.array([m.start() for m in spans] + [len(text)], dtype=np.int64)
    units = data['units']
    if not units or units[0]['start_char'] != 0:
        raise ValueError('İlk birim ve zamanlı kaynak gerekli')
    times = np.zeros(len(positions), dtype=np.float64)
    for i, unit in enumerate(units):
        end = units[i + 1]['start_char'] if i + 1 < len(units) else len(text)
        a, b = np.searchsorted(positions, [unit['start_char'], end])
        if unit['start_seconds'] > unit['end_seconds']:
            raise ValueError('Geçersiz zaman')
        times[a:b] = np.linspace(unit['start_seconds'], unit['end_seconds'], b - a, endpoint=False)
    times[-1] = units[-1]['end_seconds']
    times = np.maximum.accumulate(times)
    return spans, positions, times


def block_vectors(text, spans, encoder):
    """Yaklaşık 24 kelimelik anlam blokları; çıktı sınırlarını kısıtlamaz."""
    blocks = []
    cursor = 0
    while cursor < len(spans):
        end = min(cursor + 32, len(spans))
        for j in range(cursor + 16, end):
            if re.search(r'[.!?…]["”]*$', spans[j - 1].group()):
                end = j
                break
        blocks.append((cursor, end, text[spans[cursor].start():spans[end - 1].end()]))
        cursor = end
    import torch.nn.functional as F
    examples = ['query: ' + b[2] for b in blocks]
    vectors = []
    for start in range(0, len(examples), 32):
        batch = encoder.tokenizer(examples[start:start + 32], padding=True, truncation=True,
                                  max_length=256, return_tensors='pt').to(encoder.device)
        with encoder.torch.inference_mode():
            hidden = encoder.model(**batch).last_hidden_state.float()
            mask = batch['attention_mask'].unsqueeze(-1)
            pooled = (hidden * mask).sum(1) / mask.sum(1)
            vectors.append(F.normalize(pooled, p=2, dim=1).cpu().numpy())
    values = np.concatenate(vectors)
    words = np.empty((len(spans), values.shape[1]), dtype=np.float32)
    for (a, b, _), v in zip(blocks, values):
        words[a:b] = v
    return words


def prepare_document(data, profile, encoder, cache):
    key = digest((VERSION + MODEL_REVISION + json.dumps(profile, sort_keys=True)
                  + json.dumps(data['units'], sort_keys=True, ensure_ascii=False) + data['text']).encode())
    path = cache / (key + '.npz')
    rows = scored(features(data['text'], data['units']), profile, profile['alpha'])
    # Every cue start, sentence start and capitalized word remains eligible,
    # including cue-interior starts. No known reference position is injected.
    candidates = [r for r in rows if any(r['features'][k] for k in ['cue_start', 'sentence_start', 'uppercase']) or r['score'] >= .5]
    spans, all_positions, all_times = source_axis(data)
    positions = np.array([0] + [r['position'] for r in candidates] + [len(data['text'])], dtype=np.int64)
    word_indices = np.searchsorted(all_positions, positions)
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            cost = saved['coherence']
    else:
        word_vectors = block_vectors(data['text'], spans, encoder)
        prefix = np.vstack([np.zeros((1, word_vectors.shape[1]), dtype=np.float32), np.cumsum(word_vectors, axis=0)])
        sums = prefix[word_indices]
        gram = sums @ sums.T
        norm = np.diag(gram)
        lengths = word_indices[None, :] - word_indices[:, None]
        square_norm = norm[:, None] + norm[None, :] - 2 * gram
        cumulative_norm = np.r_[0., np.cumsum((word_vectors * word_vectors).sum(axis=1))][word_indices]
        sum_norm = cumulative_norm[None, :] - cumulative_norm[:, None]
        cost = np.maximum(0, sum_norm - square_norm / np.maximum(1, lengths)) / 24
        cost = cost.astype(np.float32)
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, coherence=cost)
    if cost.shape != (len(positions), len(positions)):
        raise ValueError('Önbellek aday boyutu farklı')
    logits = np.array([0.] + [r['generic_logit'] + r['channel_bias_logit'] for r in candidates] + [0.])
    return {'data': data, 'positions': positions, 'word_indices': word_indices, 'times': all_times[word_indices],
            'logits': logits, 'coherence': cost, 'local_cuts': [r['position'] for r in select(rows, profile['threshold'])]}


def fit_duration(training):
    from sklearn.mixture import GaussianMixture
    durations = []
    for d in training:
        _, positions, times = source_axis(d['data'])
        starts = [0] + d['expected'] + [len(d['data']['text'])]
        indices = np.searchsorted(positions, starts)
        durations.extend(np.maximum(.01, np.diff(times[indices])))
    model = GaussianMixture(n_components=3, random_state=42, reg_covar=.04).fit(np.log(durations).reshape(-1, 1))
    prior = {'weights': model.weights_.tolist(), 'means': model.means_.ravel().tolist(),
             'variances': model.covariances_.ravel().tolist(), 'training_section_count': len(durations),
             'time_precision': 'Interpolated within source cue; not forced-aligned word timestamps'}
    axis = np.linspace(-5, 10, 2000)
    prior['peak_log_density'] = float(duration_density(np.exp(axis), prior).max())
    return prior


def duration_density(seconds, prior):
    x = np.log(np.maximum(.01, seconds))
    values = []
    for weight, mean, variance in zip(prior['weights'], prior['means'], prior['variances']):
        values.append(math.log(weight) - .5 * math.log(2 * math.pi * variance) - .5 * (x - mean) ** 2 / variance)
    return np.logaddexp.reduce(values)


def duration_cost(document, prior):
    differences = document['times'][None, :] - document['times'][:, None]
    return np.maximum(0, prior['peak_log_density'] - duration_density(differences, prior)).astype(np.float32)


def decode(document, duration, settings):
    """Tüm uygun başlangıçlar üzerinde tam dinamik programlama; sabit haber sayısı yok."""
    n = len(document['positions'])
    best = np.full(n, -np.inf)
    previous = np.full(n, -1, dtype=np.int64)
    best[0] = 0
    for end in range(1, n):
        candidates = (best[:end] + document['logits'][:end] - settings['penalty']
                      - settings['duration_weight'] * duration[:end, end]
                      - settings['coherence_weight'] * document['coherence'][:end, end])
        # The first section does not pay a learned boundary score/cut penalty.
        candidates[0] += settings['penalty']
        winner = int(np.argmax(candidates))
        best[end] = candidates[winner]
        previous[end] = winner
    cuts = []
    cursor = n - 1
    while previous[cursor] > 0:
        cursor = int(previous[cursor])
        cuts.append(int(document['positions'][cursor]))
    return sorted(cuts), float(best[-1])




def export(document, cuts, folder, model_hash, score):
    if folder.exists():
        raise ValueError('Mevcut çıktı korunuyor; başka hedef seç')
    text = document['data']['text']
    positions = [0] + cuts + [len(text)]
    if positions != sorted(set(positions)) or not set(cuts) <= set(map(int, document['positions'])):
        raise ValueError('Geçersiz kaynak sınırları')
    folder.mkdir(parents=True)
    (folder / 'transcript.txt').write_bytes(text.encode())
    save_json(folder / 'timeline.json', document['data'])
    sections = []
    for i, (a, b) in enumerate(zip(positions, positions[1:]), 1):
        name = f'taslak_{i:03d}.txt'
        (folder / name).write_bytes(text[a:b].encode())
        sections.append({'start_char': a, 'end_char': b, 'file': name, 'needs_review': True})
    if b''.join((folder / s['file']).read_bytes() for s in sections) != text.encode():
        raise ValueError('Kaynak metin kaybı')
    save_json(folder / 'sections.json', {'human_approved': False, 'text_preserved': True, 'status': 'experimental_draft',
              'model_hash': model_hash, 'source_hash': digest(text.encode()), 'objective': score, 'sections': sections})


def trial(job):
    if job.exists():
        raise ValueError('Deneme zaten var; başka --job seç')
    began = time.perf_counter()
    profile = load_json(BASE / 'profile.json')
    labels = load_json(BASE / 'labels.json')
    encoder = Encoder()
    cache = ROOT / 'work/global_news_cache'
    training = []
    for d in labels['documents']:
        if d['split'] != 'train':
            continue
        data = load_json(BASE / d['timeline'])
        if digest(data['text'].encode()) != d['text_hash']:
            raise ValueError('Eğitim kaynağı değişmiş')
        training.append({'data': data, 'expected': [b['char_position'] for b in d['boundaries']]})
    prior = fit_duration(training)
    dev = next(d for d in labels['documents'] if d['split'] == 'development')
    data = load_json(BASE / dev['timeline'])
    doc = prepare_document(data, profile, encoder, cache)
    expected = [b['char_position'] for b in dev['boundaries']]
    if not set(expected) <= set(map(int, doc['positions'])):
        raise ValueError('Geliştirme sınırlarından bazıları aday üretiminde kayboldu')
    duration = duration_cost(doc, prior)
    trials = []
    for penalty, duration_weight, coherence_weight in itertools.product([0., 1., 2., 3., 4.], [0., .5, 1., 2.], [0., 1., 3.]):
        settings = {'penalty': penalty, 'duration_weight': duration_weight, 'coherence_weight': coherence_weight}
        cuts, objective = decode(doc, duration, settings)
        metric = metrics(data, expected, cuts)
        trials.append({'settings': settings, 'metrics': metric, 'objective': objective})
    best = max(trials, key=lambda r: (r['metrics']['exact']['f1'], r['metrics']['within_80_chars']['f1'], -r['metrics']['windowdiff']))
    job.mkdir(parents=True)
    save_json(job / 'development_trials.json', trials)
    model = {'version': VERSION, 'channel': 'KanalD', 'profile': profile, 'duration_prior': prior, 'settings': best['settings'],
             'encoder_revision': MODEL_REVISION, 'human_approved': False,
             'training_dates': profile['training_dates'], 'development_date': dev['date'],
             'limitations': ['No independently approved gold labels', 'No explicit broadcast-role classifier yet',
                            'Historical check days have been seen in previous experiments; not fresh validation',
                            'No production approval; local pilot only'],
             'candidate_policy': 'cue start OR sentence start OR uppercase word OR local score >= 0.5; no reference injected'}
    save_json(job / 'model.json', model)
    model_hash = digest(json.dumps(model, sort_keys=True).encode())
    print('Ayarlar yalnız geliştirmede seçildi:', best['settings'], flush=True)
    report = {'development_date': dev['date'], 'development_global': best['metrics'],
              'development_local': metrics(data, expected, doc['local_cuts']), 'checks': [],
              'human_approved': False, 'not_independent_gold': True, 'api_calls': 0, 'api_cost_usd': 0}
    # Save predictions before loading each reference for historical checks.
    check_days = ['2025-02-05', '2025-01-28']
    for date in check_days:
        timeline_path = BASE / ('sources/' + date + '.json') if date != '2025-01-28' else BASE / 'fresh_reference/timeline.json'
        check_data = load_json(timeline_path)
        check_doc = prepare_document(check_data, profile, encoder, cache)
        cuts, objective = decode(check_doc, duration_cost(check_doc, prior), best['settings'])
        export(check_doc, cuts, job / 'drafts' / date, model_hash, objective)
        save_json(job / 'predictions' / (date + '.json'), {'cuts': cuts, 'model_hash': model_hash, 'reference_loaded_after_prediction': True})
        review = load_json(ROOT / 'data/incelemeler/KanalD' / date / 'inceleme.json')
        if review['source_sha256'] != digest(check_data['text'].encode()):
            raise ValueError('Kontrol referansı farklı kaynak')
        reference = [s['start_char'] for s in review['sections'] if s['start_char'] > 0]
        comparison = {'date': date, 'global': metrics(check_data, reference, cuts),
                      'local': metrics(check_data, reference, check_doc['local_cuts']), 'candidate_count': len(check_doc['positions']) - 2,
                      'reference_candidates_missing': sorted(set(reference) - set(map(int, check_doc['positions'])))}
        report['checks'].append(comparison)
        print(date, 'yerel', {k: comparison['local']['exact'][k] for k in ['tp', 'fp', 'fn', 'f1']},
              'bütün', {k: comparison['global']['exact'][k] for k in ['tp', 'fp', 'fn', 'f1']}, flush=True)
    report['elapsed_seconds'] = round(time.perf_counter() - began, 2)
    save_json(job / 'evaluation.json', report)
    print('Çıktı:', job, flush=True)


def apply(source, model_path, output):
    model = load_json(model_path)
    if model['version'] != VERSION or model['encoder_revision'] != MODEL_REVISION:
        raise ValueError('Model sürümü farklı')
    raw = source.read_bytes()
    if source.suffix == '.json':
        data = load_json(source)
    else:
        corrections = load_json(ROOT / 'scriptler/config/vtt_word_corrections.json')
        data = timeline(raw.decode('utf-8-sig'), corrections)
    identity = digest(raw + json.dumps(model, sort_keys=True).encode())[:20]
    with process_lock(output):
        folder = output / identity
        if (folder / 'sections.json').exists():
            print('Mevcut çıktı:', folder)
            return
        if folder.exists():
            raise ValueError('Yarım çıktı var; farklı --output kullan')
        document = prepare_document(data, model['profile'], Encoder(), ROOT / 'work/global_news_cache')
        cuts, score = decode(document, duration_cost(document, model['duration_prior']), model['settings'])
        export(document, cuts, folder, digest(json.dumps(model, sort_keys=True).encode()), score)
        print('Taslak bölüm:', len(cuts) + 1, 'Çıktı:', folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['trial', 'apply'])
    parser.add_argument('--job', type=Path, default=DEFAULT)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'trial':
        trial(args.job)
    else:
        if not args.input or not args.output:
            parser.error('--input ve --output gerekli')
        apply(args.input, args.job / 'model.json', args.output)
