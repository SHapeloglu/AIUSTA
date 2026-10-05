# CLAUDE.md

Bu dosya, bu proje üzerinde çalışırken Claude'un (Claude Code dahil) izlemesi gereken bağlamı ve kuralları içerir.

## Proje

**İştek Platform 🇹🇷** — Türkiye'ye özel TaskRabbit benzeri hizmet platformu — Python / Flask M�şteriler iş ilanı açar, doğrulanmış uzmanlar teklif verir. Platform; ödeme, mesajlaşma, randevu ve iş takibini uçtan uca yönetir.

- GitHub: https://github.com/SHapeloglu/AIUSTA

## Teknoloji Yığını

- Flask
- MySQL (PyMySQL)
- requests

## Önemli Dosyalar

- `app.py`
- `requirements.txt`
- `templates/index.html`

Mimari ayrıntılar için bkz. `architect.md`.

## Sık Kullanılan Komutlar

```bash
python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
python app.py
```

## Kurallar

- Gizli anahtar, DB bağlantısı vb. yapılandırmayı ortam değişkenlerinden / `.env`den oku; koda gömme.
- Route içinde iş mantığını büyütme; yardımcı modüllere/servislere ayır.
- `.env`, parola, token ve API anahtarlarını asla commit etme.
- Her çalışma oturumunun sonunda `session.md`ye kısa kayıt düş; görev durumunu `task.md`de güncelle.
- Önceliklendirilmemiş fikirleri `backlog.md`ye yaz; somutlaşınca `task.md`ye taşı.

## Çalışma Dosyaları

| Dosya | Amaç |
|---|---|
| `architect.md` | Mimari ve dizin yapısı referansı |
| `task.md` | Aktif / devam eden / tamamlanan görevler |
| `backlog.md` | Önceliklendirilmemiş fikir ve teknik borç havuzu |
| `session.md` | Oturum günlüğü — her oturum sonunda güncellenir |
