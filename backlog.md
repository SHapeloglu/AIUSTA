# backlog.md — İştek Platform Fikir Havuzu

Önceliklendirilmemiş işler. Sıraya girince `task.md`'ye taşı.

## Teknik Borç

- **Migration aracı** (Alembic veya basit sürüm tablolu SQL dosyaları) — şu an `CREATE TABLE IF NOT EXISTS` kolon değişikliklerini uygulamıyor.
- **`SECRET_KEY` zorunlu olsun**: ayarlı değilken geçici anahtar üretmek her restart'ta tüm oturumları düşürüyor; canlıda başlatmayı reddetmek daha güvenli.
- **SocketIO `cors_allowed_origins="*"`** → `FRONTEND_URL` ile sınırla.
- **Rate limit depolaması**: çoklu worker/sunucuda `memory://` paylaşılmaz → canlıda `REDIS_URL` zorunlu hale getir.
- **Ödeme/iade için iyzico SDK** veya ortak bir istemci modülü — `odeme.py` ve `iade.py` anahtarları ayrı ayrı okuyor.
- E-posta/SMS gönderimini `Thread` yerine kuyruğa (RQ/Celery) taşı; hata/yeniden deneme kaydı yok.

## Özellikler

- Uzman eşleştirmede kullanıcı geri bildirimiyle ağırlık ayarı (hangi önerilen uzman seçildi?).
- Escrow'dan uzmana otomatik ödeme aktarımı (iş "Tamamlandı" adımında).
- Bildirimler için web push / mobil push.
- Kendi Jitsi sunucusu + JWT (`JITSI_APP_ID` yer tutucusu `routes/video.py`'de hazır).
- Admin panelinde gelir/komisyon raporu.
- Dağıtım: Dockerfile + gunicorn/eventlet + nginx örneği.

## Ekleme Şablonu

```markdown
### Başlık
- **Kategori:** yeni özellik / iyileştirme / teknik borç / araştırma
- **Neden:** kısa gerekçe
- **Notlar:** büyüklük, bağımlılıklar, riskler
```
