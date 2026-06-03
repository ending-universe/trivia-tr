# TriviaТR 🎯

Open Trivia Database sorularını Python `deep-translator` kütüphanesi ile otomatik Türkçe'ye çeviren bilgi yarışması uygulaması.

## Özellikler
- 🌐 Open Trivia DB'den gerçek zamanlı soru çekme
- 🔄 `deep-translator` ile ücretsiz Türkçe çeviri (API key gerekmez!)
- ⚡ In-memory cache (UI'dan açılıp kapatılabilir)
- ⏱️ 30 saniye sayacı
- 📊 Sonuç özeti

## Kurulum

### Gereksinimler
- Docker Desktop

### Çalıştırma

```bash
docker compose up --build
```

Tarayıcıda aç: **http://localhost:3000**

### Durdurma

```bash
docker compose down
```

## Mimari

```
http://localhost:3000  →  Frontend (nginx)
                               ↕
http://localhost:4000  →  Backend (Python Flask)
                               ↕
                    OpenTDB API + deep-translator
```
