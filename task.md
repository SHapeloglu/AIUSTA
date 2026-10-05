# task.md — İştek Platform Görevleri

## 🔜 Sıradaki

- [ ] `mail_service.py` ve `sms_service.py` ayarlarını `.env`'den oku (`MAIL_USERNAME`, `MAIL_PASSWORD`, `NETGSM_KULLANICI`, `NETGSM_SIFRE`, `NETGSM_BASLIK`)
  - Bağlam: `.env.example` bu değişkenleri tanımlıyor ama kod sabit yer tutucu kullanıyor; gerçek değer girmek için kodu düzenlemek gerekiyor → sızıntı riski.
  - Kabul: değerler yalnızca `.env`'den geliyor, kodda kimlik bilgisi kalmıyor.
- [ ] README'yi koda göre düzelt
  - Demo admin şifresi koda göre `Admin123!` (README `admin123` diyor); "Yapılandırma" bölümü hâlâ dosya düzenlemeyi anlatıyor, `.env`'i anlatmalı; 11. satırdaki bozuk karakter ("M�şteriler").
- [ ] `requirements.txt`'ten kullanılmayan `scikit-learn` ve `numpy`'ı çıkar (ya da eşleştirmeyi gerçekten sklearn'e taşı)
- [ ] Duman testleri: `pytest` + Flask test client ile kayıt/giriş, ilan oluşturma, teklif, iade oranı hesaplama (`iade_orani_hesapla`), eşleştirme skoru (`uzman_skoru_hesapla`)

## 🚧 Devam Eden

_(şu anda boş)_

## ✅ Tamamlanan

- [x] 2026-10-05 — Çalışma dosyaları kod okunarak yeniden yazıldı (CLAUDE.md, architect.md, task.md, backlog.md, session.md)
- [x] 2026-05-13 — Proje GitHub'a yüklendi
