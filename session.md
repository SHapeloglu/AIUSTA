# session.md — İştek Platform Oturum Günlüğü

Her oturum sonunda en üste yeni kayıt ekle: ne yapıldı, hangi kararlar alındı, açık kalanlar, sıradaki adım.

---

## 2026-10-05

**Yapılanlar:**
- Şablondan üretilmiş yüzeysel çalışma dosyaları, kod okunarak yeniden yazıldı (CLAUDE.md, architect.md, task.md, backlog.md, session.md).

**Tespitler:**
- `mail_service.py` / `sms_service.py` `.env` okumuyor; `.env.example` ile tutarsız.
- README'deki demo admin şifresi koddakiyle (`Admin123!`) uyuşmuyor.
- `scikit-learn`/`numpy` bağımlılık listesinde ama kullanılmıyor.
- Test yok.

**Sıradaki adım:**
- `task.md` → "Sıradaki" listesi.

---

## 2026-05-13

- Proje tek commit ile GitHub'a yüklendi ("zzzz"). Öncesine ait oturum kaydı yok.

---

### Kayıt Şablonu

```markdown
## YYYY-AA-GG
**Yapılanlar:** ...
**Kararlar / neden:** ...
**Açık sorunlar:** ...
**Sıradaki adım:** ...
```
