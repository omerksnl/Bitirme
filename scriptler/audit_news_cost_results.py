"""Maliyet deneyini yerelde denetler; reddedilen Luna yanıtını üretime çıkarmaz."""
import argparse
import bisect
import json
from pathlib import Path
import re

from gpt_news_review_batch import checked_manifest, quote_position, usage_cost_usd
from global_news_time_trial import metrics
from openai_news_batch import ROOT, load_json, save_json, response_payload, digest

DEFAULT = ROOT / 'data/denemeler/maliyet_optimizasyonu_01'


def source_matches(text, quote, punctuation_only=False):
    tokens = list(re.finditer(r'\S+', text))
    query = quote.split()
    if not 1 <= len(query) <= 8:
        return []
    def key(word):
        return word.rstrip('.,!?;:…') if punctuation_only else word
    values = [key(t.group()) for t in tokens]
    expected = [key(w) for w in query]
    return [{'start_char': tokens[i].start(), 'end_char': tokens[i + len(query) - 1].end()}
            for i in range(len(tokens) - len(query) + 1) if values[i:i + len(query)] == expected]


def diagnose(data, payload):
    """Yakın, kelimeleri aynı adayları yalnız tanı için gösterir; üretim doğrulaması değişmez."""
    starts = [u['start_char'] for u in data['units']]
    ids = {u['id']: i for i, u in enumerate(data['units'])}
    segments, findings, unresolved = [], [], []
    for index, item in enumerate(payload['segments']):
        try:
            position = quote_position(data, item['unit'], item['start_quote'])
            status = 'strictly_valid'
        except ValueError as error:
            claimed = ids.get(item['unit'])
            candidates = source_matches(data['text'], item['start_quote'])
            method = 'exact_source_words'
            if not candidates:
                candidates = source_matches(data['text'], item['start_quote'], punctuation_only=True)
                method = 'trailing_punctuation_ignored_only'
            local = []
            for candidate in candidates:
                actual = max(0, bisect.bisect_right(starts, candidate['start_char']) - 1)
                if claimed is not None and abs(actual - claimed) <= 2:
                    local.append({**candidate, 'actual_unit': data['units'][actual]['id'], 'unit_distance': actual - claimed})
            finding = {'segment_index': index, 'response': item, 'error': str(error), 'matching_method': method,
                       'global_match_count': len(candidates), 'nearby_candidates': local,
                       'production_accepted': False}
            if len(local) != 1:
                finding['status'] = 'unresolved'
                unresolved.append(index)
                findings.append(finding)
                continue
            position = local[0]['start_char']
            status = 'diagnostic_candidate_needs_review'
            finding.update(status=status, proposed_start_char=position,
                           source_quote=data['text'][position:local[0]['end_char']])
            findings.append(finding)
        segments.append({**item, 'start_char': position, 'diagnostic_status': status})
    positions = [s['start_char'] for s in segments]
    complete = not unresolved and positions == sorted(set(positions)) and positions and positions[0] == 0
    return {'segments': segments, 'findings': findings, 'unresolved_indices': unresolved,
            'diagnostic_sequence_complete': bool(complete), 'production_accepted': not findings and bool(complete)}


def run(root, variants=None):
    result = {'human_approved': False, 'not_independent_gold': True, 'api_calls': 0, 'models': []}
    for name in variants or ['compact_sol', 'compact_luna']:
        job = root / name
        manifest = checked_manifest(job)
        collection = load_json(job / 'collection_report.json')
        records = {r['custom_id']: r for r in [json.loads(line) for line in (job / 'output.jsonl').read_text(encoding='utf8').splitlines()]}
        known_usage = [r['response']['body']['usage'] for r in records.values()
                       if (r.get('response') or {}).get('body', {}).get('usage')]
        measured_cost = sum(usage_cost_usd(u, manifest['model']) for u in known_usage)
        model = {'name': name, 'model': manifest['model'], 'reasoning_effort': manifest.get('reasoning_effort', 'low'),
                 'collection_exported': collection['exported'],
                 'collection_failed': collection['failed'], 'usage_cost_usd': measured_cost,
                 'collection_report_cost_usd': collection['usage_cost_usd_conservative'],
                 'billable_usage_known_for_all_requests': len(known_usage) == len(manifest['requests']),
                 'cost_method': 'Batch ordinary input, model-specific cached reads, 1.25x cache writes, output including reasoning',
                 'documents': []}
        for doc in manifest['requests']:
            data = load_json(job / doc['timeline'])
            raw = (job / doc['snapshot']).read_bytes()
            if digest(raw) != doc['sha256'] or data['text'].encode() != raw:
                raise ValueError('Kaynak kopyası değişmiş')
            record = records[doc['custom_id']]
            body = (record.get('response') or {}).get('body', {})
            if body.get('status') != 'completed' or record.get('error') or (record.get('response') or {}).get('status_code') != 200:
                model['documents'].append({'channel': doc['channel'], 'date': doc['date'],
                    'response_status': body.get('status'), 'incomplete_details': body.get('incomplete_details'),
                    'error': record.get('error') or body.get('error'), 'quality_evaluable': False})
                continue
            payload = response_payload(record)
            diagnostic = diagnose(data, payload)
            ref = load_json(ROOT / 'data/incelemeler' / doc['channel'] / doc['date'] / 'inceleme.json')
            if ref['source_sha256'] != doc['sha256']:
                raise ValueError('Referans farklı kaynak')
            expected = [s['start_char'] for s in ref['sections'] if s['start_char']]
            entry = {'channel': doc['channel'], 'date': doc['date'], 'payload_section_count': len(payload['segments']),
                     'payload_news_count': sum(s['kind'] == 'news' for s in payload['segments']),
                     'format_failure_count': len(diagnostic['findings']), 'diagnostic': diagnostic}
            if diagnostic['diagnostic_sequence_complete']:
                predicted = [s['start_char'] for s in diagnostic['segments'] if s['start_char']]
                entry['diagnostic_metrics'] = metrics(data, expected, predicted)
                ref_by_start = {s['start_char']: s for s in ref['sections']}
                entry['exact_kind_mismatches'] = [{'start_char': s['start_char'], 'reference_kind': ref_by_start[s['start_char']]['kind'],
                         'model_kind': s['kind'], 'title': ref_by_start[s['start_char']]['title']}
                         for s in diagnostic['segments'] if s['start_char'] in ref_by_start and s['kind'] != ref_by_start[s['start_char']]['kind']]
                entry['error_excerpts'] = {key: [{'position': p, 'left': data['text'][max(0, p - 120):p],
                                              'right': data['text'][p:p + 240]} for p in entry['diagnostic_metrics']['exact'][key]]
                                          for key in ['extra', 'missed']}
                print(name, doc['channel'], 'format', entry['format_failure_count'], 'diagnostic exact',
                      {k: entry['diagnostic_metrics']['exact'][k] for k in ['tp', 'fp', 'fn', 'f1']},
                      'near80', {k: entry['diagnostic_metrics']['within_80_chars'][k] for k in ['tp', 'fp', 'fn', 'f1']})
            else:
                print(name, doc['channel'], 'unresolved', diagnostic['unresolved_indices'])
            model['documents'].append(entry)
        model['fourteen_bulletins_per_day_sample_usd'] = model['usage_cost_usd'] / len(manifest['requests']) * 14
        model['thirty_days_sample_usd'] = model['fourteen_bulletins_per_day_sample_usd'] * 30
        result['models'].append(model)
    save_json(root / 'RESULT_AUDIT.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, default=DEFAULT)
    parser.add_argument('--variants', nargs='+', help='Kökte incelenecek tamamlanmış iş klasörleri')
    args = parser.parse_args()
    run(args.job.resolve(), args.variants)
