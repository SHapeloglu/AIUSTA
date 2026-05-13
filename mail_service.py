"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — E-posta Bildirim Servisi         ║
╚══════════════════════════════════════════════════════════════╝

Flask-Mail ile Gmail SMTP üzerinden HTML e-posta gönderimi.
Tüm mailler arka planda Thread ile gönderilir (isteği bloklamaz).

Hazır Şablonlar:
    send_hosgeldin()           → Kayıt sonrası hoş geldin maili
    send_teklif_bildirimi()    → Müşteriye: yeni teklif geldi
    send_teklif_kabul()        → Uzmana: teklifiniz kabul edildi
    send_odeme_onay()          → Müşteriye: ödeme onaylandı
    send_odeme_uzman()         → Uzmana: ödemeniz aktarıldı
    send_uzman_onay()          → Uzmana: profiliniz onaylandı
    send_mesaj_bildirimi()     → Yeni mesaj bildirimi
    send_sifre_sifirlama()     → Şifre sıfırlama bağlantısı
    send_randevu_hatirlatma()  → Randevu hatırlatması

Gmail Kurulumu:
    1. Gmail hesabı → Güvenlik → 2 Adımlı Doğrulama açın
    2. Güvenlik → Uygulama Şifreleri → Yeni şifre oluşturun
    3. MAIL_USERNAME ve MAIL_PASSWORD'ü ayarlayın
"""

from flask_mail import Mail, Message
from flask import render_template_string
from threading import Thread

mail = Mail()

# ─── SMTP AYARLARI (app.py'de app.config'e eklenir) ──────────────────────────
MAIL_CONFIG = {
    "MAIL_SERVER":   "smtp.gmail.com",
    "MAIL_PORT":     587,
    "MAIL_USE_TLS":  True,
    "MAIL_USERNAME": "istek.platform@gmail.com",   # ← Gmail adresiniz
    "MAIL_PASSWORD": "xxxx xxxx xxxx xxxx",        # ← Gmail uygulama şifresi
    "MAIL_DEFAULT_SENDER": ("İştek Platform", "istek.platform@gmail.com"),
}
# ─────────────────────────────────────────────────────────────────────────────

def _async_send(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"[Mail Hata] {e}")

def send_mail(app, subject, recipients, html_body, text_body=""):
    """Arka planda mail gönderir — isteği bloklamaz."""
    msg            = Message(subject, recipients=recipients)
    msg.html       = html_body
    msg.body       = text_body or "HTML destekli bir mail istemcisi kullanın."
    Thread(target=_async_send, args=(app, msg), daemon=True).start()

# ─── Mail şablonları ──────────────────────────────────────────────────────────

BASE = """
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08);}}
  .header{{background:#E53935;padding:28px 32px;text-align:center;}}
  .header h1{{color:#fff;margin:0;font-size:22px;letter-spacing:-.5px;}}
  .header p{{color:rgba(255,255,255,.8);margin:6px 0 0;font-size:13px;}}
  .body{{padding:28px 32px;}}
  .body p{{color:#444;font-size:15px;line-height:1.6;margin:0 0 14px;}}
  .kart{{background:#FFF5F5;border-left:4px solid #E53935;border-radius:6px;padding:16px 20px;margin:20px 0;}}
  .kart .label{{font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.06em;}}
  .kart .val{{font-size:18px;font-weight:700;color:#E53935;margin-top:4px;}}
  .btn{{display:inline-block;background:#E53935;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;margin:8px 0;}}
  .footer{{background:#f9f9f9;padding:18px 32px;text-align:center;border-top:1px solid #eee;}}
  .footer p{{color:#bbb;font-size:12px;margin:0;}}
</style></head>
<body><div class="wrap">
  <div class="header"><h1>İştek</h1><p>Türkiye'nin güvenilir hizmet platformu</p></div>
  <div class="body">{body}</div>
  <div class="footer"><p>© 2024 İştek Platform · Bu maili siz talep ettiniz.</p></div>
</div></body></html>
"""

def _render(body_html):
    return BASE.format(body=body_html)

# ── 1. Hoş geldin maili ───────────────────────────────────────────────────────

def send_hosgeldin(app, email, ad, rol):
    rol_metin = "uzman" if rol == "uzman" else "müşteri"
    body = f"""
    <p>Merhaba <strong>{ad}</strong>,</p>
    <p>İştek ailesine hoş geldiniz! {rol_metin.capitalize()} hesabınız başarıyla oluşturuldu.</p>
    {"<div class='kart'><div class='label'>Bilgi</div><div class='val' style='font-size:14px;color:#555'>Profiliniz admin onayından geçtikten sonra iş ilanlarına teklif verebilirsiniz.</div></div>" if rol == 'uzman' else ""}
    <a href='https://istek.com/dashboard' class='btn'>Dashboard'a Git →</a>
    <p style='font-size:13px;color:#999;margin-top:20px'>Herhangi bir sorunuz varsa destek@istek.com adresine yazabilirsiniz.</p>
    """
    send_mail(app, "İştek'e Hoş Geldiniz! 🎉", [email], _render(body))

# ── 2. Yeni teklif bildirimi (müşteriye) ──────────────────────────────────────

def send_teklif_bildirimi(app, musteri_email, musteri_ad, uzman_ad, ilan_baslik, teklif_fiyat, ilan_id):
    body = f"""
    <p>Merhaba <strong>{musteri_ad}</strong>,</p>
    <p><strong>{uzman_ad}</strong> adlı uzman ilanınıza teklif gönderdi.</p>
    <div class='kart'>
      <div class='label'>İlan</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>Teklif Fiyatı</div>
      <div class='val'>₺{teklif_fiyat:,.0f}</div>
    </div>
    <p>Teklifi inceleyip uzmanla iletişime geçebilirsiniz.</p>
    <a href='https://istek.com/dashboard' class='btn'>Teklifi İncele →</a>
    """
    send_mail(app, f"Yeni Teklif: {ilan_baslik}", [musteri_email], _render(body))

# ── 3. Teklif kabul bildirimi (uzmana) ───────────────────────────────────────

def send_teklif_kabul(app, uzman_email, uzman_ad, musteri_ad, ilan_baslik, fiyat):
    body = f"""
    <p>Merhaba <strong>{uzman_ad}</strong>,</p>
    <p>Harika haber! <strong>{musteri_ad}</strong> teklifinizi kabul etti.</p>
    <div class='kart'>
      <div class='label'>İş</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>Onaylanan Ücret</div>
      <div class='val'>₺{fiyat:,.0f}</div>
    </div>
    <p>Müşteri ile iletişime geçerek randevu belirleyebilirsiniz.</p>
    <a href='https://istek.com/chat' class='btn'>Müşteriye Mesaj Gönder →</a>
    """
    send_mail(app, f"Teklifiniz Kabul Edildi! ✅", [uzman_email], _render(body))

# ── 4. Ödeme onay bildirimi ───────────────────────────────────────────────────

def send_odeme_onay(app, musteri_email, musteri_ad, ilan_baslik, tutar, uzman_ad):
    body = f"""
    <p>Merhaba <strong>{musteri_ad}</strong>,</p>
    <p>Ödemeniz başarıyla alındı. İş tamamlandığında uzmanınızı değerlendirmeyi unutmayın!</p>
    <div class='kart'>
      <div class='label'>Hizmet</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>Uzman</div>
      <div class='val' style='font-size:15px;color:#333'>{uzman_ad}</div>
      <div class='label' style='margin-top:12px'>Ödenen Tutar</div>
      <div class='val'>₺{tutar:,.2f}</div>
    </div>
    <a href='https://istek.com/dashboard' class='btn'>Dashboard'a Git →</a>
    """
    send_mail(app, "Ödemeniz Onaylandı ✅", [musteri_email], _render(body))

def send_odeme_uzman(app, uzman_email, uzman_ad, ilan_baslik, net_tutar):
    body = f"""
    <p>Merhaba <strong>{uzman_ad}</strong>,</p>
    <p>Ödemeniz hesabınıza aktarıldı.</p>
    <div class='kart'>
      <div class='label'>İş</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>Net Kazanç</div>
      <div class='val'>₺{net_tutar:,.2f}</div>
    </div>
    <a href='https://istek.com/dashboard' class='btn'>Kazançlarımı Gör →</a>
    """
    send_mail(app, "Ödemeniz Aktarıldı 💰", [uzman_email], _render(body))

# ── 5. Uzman onay bildirimi ───────────────────────────────────────────────────

def send_uzman_onay(app, uzman_email, uzman_ad):
    body = f"""
    <p>Merhaba <strong>{uzman_ad}</strong>,</p>
    <p>Profiliniz ekibimiz tarafından incelendi ve <strong>onaylandı</strong>! 🎉</p>
    <p>Artık aktif iş ilanlarına teklif verebilir, müşterilerle iletişime geçebilirsiniz.</p>
    <a href='https://istek.com/dashboard' class='btn'>Teklif Vermeye Başla →</a>
    """
    send_mail(app, "Profiliniz Onaylandı! 🎉", [uzman_email], _render(body))

# ── 6. Yeni mesaj bildirimi ───────────────────────────────────────────────────

def send_mesaj_bildirimi(app, alici_email, alici_ad, gonderen_ad, mesaj_onizleme):
    body = f"""
    <p>Merhaba <strong>{alici_ad}</strong>,</p>
    <p><strong>{gonderen_ad}</strong> size bir mesaj gönderdi:</p>
    <div class='kart'>
      <div class='val' style='font-size:14px;color:#555;font-style:italic'>"{mesaj_onizleme[:120]}{"..." if len(mesaj_onizleme)>120 else ""}"</div>
    </div>
    <a href='https://istek.com/chat' class='btn'>Yanıtla →</a>
    """
    send_mail(app, f"Yeni Mesaj: {gonderen_ad}", [alici_email], _render(body))

# ── 7. Şifre sıfırlama ────────────────────────────────────────────────────────

def send_sifre_sifirlama(app, email, ad, reset_token):
    reset_url = f"https://istek.com/sifre-sifirla/{reset_token}"
    body = f"""
    <p>Merhaba <strong>{ad}</strong>,</p>
    <p>Şifre sıfırlama talebinde bulundunuz. Aşağıdaki bağlantıya tıklayarak yeni şifrenizi belirleyebilirsiniz.</p>
    <p style='color:#999;font-size:13px'>Bu bağlantı 1 saat geçerlidir.</p>
    <a href='{reset_url}' class='btn'>Şifremi Sıfırla →</a>
    <p style='color:#bbb;font-size:12px;margin-top:20px'>Bu talebi siz yapmadıysanız bu maili görmezden gelebilirsiniz.</p>
    """
    send_mail(app, "Şifre Sıfırlama Talebi", [email], _render(body))

# ── 8. Randevu hatırlatması ───────────────────────────────────────────────────

def send_randevu_hatirlatma(app, email, ad, ilan_baslik, randevu_tarihi, diger_kisi_ad):
    body = f"""
    <p>Merhaba <strong>{ad}</strong>,</p>
    <p>Yarın bir randevunuz var, hazır olun!</p>
    <div class='kart'>
      <div class='label'>İş</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>Karşı Taraf</div>
      <div class='val' style='font-size:15px;color:#333'>{diger_kisi_ad}</div>
      <div class='label' style='margin-top:12px'>Randevu</div>
      <div class='val'>{randevu_tarihi}</div>
    </div>
    <a href='https://istek.com/chat' class='btn'>Mesaj Gönder →</a>
    """
    send_mail(app, f"Yarın Randevunuz Var! 📅", [email], _render(body))
