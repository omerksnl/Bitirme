"""Qwen'i yükler, 10 haberi yorumlar ve website JSON'unu üretir."""

import json
import re
from pathlib import Path

import torch

MODEL_NAME = "Qwen/Qwen3.8-27B"
WEB_ROOT = Path("/content/drive/MyDrive/Benim_Colab_Projem/scriptler/web-prototype")
INPUT_PATH = WEB_ROOT / "public/data/model_inputs.json"
OUTPUT_PATH = WEB_ROOT / "public/data/news_results.json"

SYSTEM_PROMPT = """
Sen Türkçe televizyon haberlerinde enflasyon anlatısını analiz eden bir araştırma asistanısın.
Haberin gerçek ekonomik etkisini tahmin etme; metnin enflasyonu nasıl çerçevelediğini sınıflandır.
Sınıflar:
- iyimser: Enflasyonda düşüş, iyileşme, rahatlama veya olumlu beklenti.
- kotumser: Fiyat artışı, zam, bozulma veya olumsuz beklenti.
- notr: Açık olumlu ya da olumsuz çerçevesi olmayan bilgi.
Yalnızca geçerli JSON döndür:
{
  "prediction": "iyimser | kotumser | notr",
  "scores": {"iyimser": 0, "kotumser": 0, "notr": 0},
  "reason": "Kısa Türkçe gerekçe",
  "evidence": "Metinden kısa kanıt"
}
Skorlar 0-100 arasında ve toplamları 100 olmalı.
""".strip()


def parse_json(text):
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"Model geçerli JSON üretmedi: {text}")
        return json.loads(match.group(0))


def normalize_prediction(analysis):
    prediction = str(analysis.get("prediction", "notr")).lower()
    prediction = prediction.replace("kötümser", "kotumser").replace("nötr", "notr")
    if prediction not in {"iyimser", "kotumser", "notr"}:
        prediction = "notr"
    raw = analysis.get("scores", {})
    values = {
        "iyimser": float(raw.get("iyimser", 0)),
        "kotumser": float(raw.get("kotumser", raw.get("kötümser", 0))),
        "notr": float(raw.get("notr", raw.get("nötr", 0))),
    }
    total = sum(max(0, value) for value in values.values())
    if total == 0:
        values = {"iyimser": 0.0, "kotumser": 0.0, "notr": 100.0}
    else:
        values = {key: round(max(0, value) / total * 100, 2) for key, value in values.items()}
    return prediction, values


if not INPUT_PATH.exists():
    raise FileNotFoundError(f"Website girdi dosyası bulunamadı: {INPUT_PATH}")

if "model" not in globals() or "tokenizer" not in globals():
    raise RuntimeError(
        "Qwen bellekte değil. Önce model ve tokenizer yükleme hücresini çalıştırın."
    )
if not hasattr(model, "generate"):
    raise RuntimeError(
        "Model AutoModelForCausalLM olarak yüklenmeli; sınıflandırma modeli metin üretemez."
    )

print("Bellekteki Qwen kullanılıyor.")
model.eval()

with INPUT_PATH.open("r", encoding="utf-8") as file:
    news_items = json.load(file)

directions = {"iyimser": "positive", "kotumser": "negative", "notr": "neutral"}
results = []

for index, news in enumerate(news_items, start=1):
    print(f"[{index}/{len(news_items)}] {news['channel']} yorumlanıyor...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Haber metni:\n{news['text']}"},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
    with torch.no_grad():
        generated = model.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    answer = tokenizer.decode(generated[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    analysis = parse_json(answer)
    prediction, scores = normalize_prediction(analysis)
    result = dict(news)
    result.update({
        "prediction": prediction,
        "direction": directions[prediction],
        "confidence": scores[prediction],
        "probabilities": scores,
        "model_comment": analysis.get("reason", ""),
        "evidence": analysis.get("evidence", ""),
        "model": MODEL_NAME,
    })
    results.append(result)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as file:
    json.dump(results, file, ensure_ascii=False, indent=2)

print(f"Tamamlandı: {len(results)} haber websiteye yazıldı.")
print(f"Çıktı: {OUTPUT_PATH}")
