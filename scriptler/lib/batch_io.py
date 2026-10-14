"""Batch submission and durable JSON storage shared by current and historical tools."""
import hashlib
import json
import os
from pathlib import Path
from .paths import ROOT


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    with temporary.open('wb') as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.replace(path)
    except PermissionError:
        # Some Windows folders allow writing but deny child deletion, which
        # also prevents replacing an existing file. Keep a recovery journal
        # and the previous valid value; do not change the folder ACL.
        if path.exists():
            backup=path.with_suffix(path.suffix+'.bak')
            backup.write_bytes(path.read_bytes())
        with path.open('wb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError,json.JSONDecodeError):
        # Recover an interrupted in-place write from its fully flushed journal.
        journal=path.with_suffix(path.suffix+'.tmp')
        if journal.exists():
            return json.loads(journal.read_text(encoding='utf-8-sig'))
        raise


def api_client():
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY ortam değişkeni tanımlı değil. Anahtarı kod/GitHub içine yazma.")
    try:
        from openai import OpenAI
    except ImportError as error:
        raise ValueError("Önce python -m pip install -r scriptler/requirements.txt çalıştır") from error
    # No implicit SDK retries for billable batch creation.
    return OpenAI(max_retries=0)


def submit(args) -> int:
    job = args.job.resolve()
    if not (job / "manifest.json").exists():
        if job.name == "review":
            raise ValueError("İkinci kontrol henüz hazırlanmamış. Önce collect ile ilk aşamanın sonuçlarını topla.")
        raise ValueError("İş hazırlanmış değil. Önce prepare çalıştır veya --job yolunu kontrol et.")
    manifest = load_json(job / "manifest.json")
    if manifest.get("version") not in (2, 3):
        raise ValueError("Bu iş eski alıntı yöntemiyle hazırlanmış. prepare ile yeni --job altında numaralı kelime istekleri hazırla.")
    raw = (job / "requests.jsonl").read_bytes()
    if digest(raw) != manifest["requests_sha256"]:
        raise ValueError("Hazırlanan istek dosyası değiştirilmiş; yeni iş hazırla")
    state_path = job / "batch_state.json"
    state = load_json(state_path) if state_path.exists() else {}
    journal_path=state_path.with_suffix('.json.tmp')
    if journal_path.exists():
        journal=load_json(journal_path)
        if journal.get('batch_id') and journal.get('input_file_id')==state.get('input_file_id'):
            # A batch was created but final persistence was interrupted.
            state=journal
            save_json(state_path,state)
    if state.get("batch_id"):
        raise ValueError(f"Bu iş zaten gönderildi: {state['batch_id']}; status kullan")
    # A previous interrupted creation must be reconciled in the platform,
    # instead of blindly submitting a second paid batch.
    if state.get("creation_pending"):
        raise ValueError("Önceki gönderimin sonucu belirsiz. Platformdaki Batch listesini kontrol et; tekrar gönderme.")
    client = api_client()
    lock = job / "submit.lock"
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    try:
        if not state.get("input_file_id"):
            with (job / "requests.jsonl").open("rb") as handle:
                uploaded = client.files.create(file=handle, purpose="batch")
            state["input_file_id"] = uploaded.id
            save_json(state_path, state)
        state["creation_pending"] = True
        save_json(state_path, state)
        batch = client.batches.create(input_file_id=state["input_file_id"], endpoint="/v1/responses", completion_window="24h", metadata={"task": "turkish_news_segmentation", "stage": manifest.get("stage", "legacy"), "requests_sha256": manifest["requests_sha256"]})
        state.update(batch_id=batch.id, creation_pending=False, status=batch.status)
        save_json(state_path, state)
        print(f"Batch gönderildi: {batch.id}\nDurum: {batch.status}")
    finally:
        lock.unlink(missing_ok=True)
    return 0


def response_payload(line: dict) -> dict:
    if line.get("error"):
        raise ValueError(f"API istek hatası: {line['error']}")
    response = line.get("response") or {}
    if response.get("status_code") != 200:
        raise ValueError(f"API HTTP durumu: {response.get('status_code')}")
    body = response.get("body") or {}
    if body.get("status") != "completed":
        raise ValueError(f"Model yanıtı tamamlanmadı: {body.get('status')}")
    texts = []
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise ValueError("Model bu kayıt için yanıt vermeyi reddetti")
            if content.get("type") == "output_text":
                texts.append(content["text"])
    if not texts:
        raise ValueError("JSON yanıtı bulunamadı")
    return json.loads("".join(texts))
