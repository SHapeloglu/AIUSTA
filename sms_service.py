"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Netgsm SMS Servisi               ║
╚══════════════════════════════════════════════════════════════╝

Netgsm API üzerinden Türkiye'ye SMS gönderimi.
Tüm SMS'ler arka planda Thread ile gönderilir (isteği bloklamaz).

Hazır Şablonlar:
    send_teklif_sms()          → Müşteriye: yeni teklif geldi
    send_teklif_kabul_sms()    → Uzmana: teklifiniz kabul edildi
    send_randevu_sms()         → Randevu hatırlatması
    send_odeme_sms()           → Ödeme onayı
    send_uzman_onay_sms()      → Uzman profil onayı
    send_kayit_sms()           → Hoş geldin SMS'i
    send_iptal_sms()           → İptal bildirimi
    send_iade_sms()            → İade bildirimi

Kurulum:
    1. netgsm.com.tr → Hesabım → API Bilgileri
    2. NETGSM_KULLANICI, NETGSM_SIFRE ve NETGSM_BASLIK'ı ayarlayın
    3. SMS başlığının (BASLIK) Netgsm tarafından onaylanmış olması gerekir
"""

import requests
from threading import Thread
from datetime import datetime

# ─── NETGSM AYARLARI ──────────────────────────────────────────────────────────
NETGSM_KULLANICI = "850XXXXXXX"          # ← Netgsm kullanıcı adınız (GSM no)
NETGSM_SIFRE     = "NETGSM_SIFRENIZ"    # ← Netgsm şifreniz
NETGSM_BASLIK    = "ISTEK"              # ← Onaylı başlığınız (max 11 karakter)
NETGSM_API_URL   = "https://api.netgsm.com.tr/sms/send/get"
# ─────────────────────────────────────────────────────────────────────────────

def _telefon_duzenle(tel: str) -> str:
    """05XX → 905XX formatına çevirir."""
    tel = "".join(filter(str.isdigit, tel or ""))
    if tel.startswith("0"):
        tel = "9" + tel
    elif not tel.startswith("90"):
        tel = "90" + tel
    return tel

def _sms_gonder(telefon: str, mesaj: str):
    """Senkron SMS gönderir — Thread içinde çağrılır."""
    telefon = _telefon_duzenle(telefon)
    if len(telefon) != 12:
        print(f"[SMS] Geçersiz telefon: {telefon}")
        return

    try:
        params = {
            "usercode":  NETGSM_KULLANICI,
            "password":  NETGSM_SIFRE,
            "gsmno":     telefon,
            "message":   mesaj,
            "msgheader": NETGSM_BASLIK,
            "dil":       "TR",
        }
        r = requests.get(NETGSM_API_URL, params=params, timeout=10)
        kod = r.text.strip().split("\n")[0]
        if kod == "00" or kod == "01":
            print(f"[SMS ✅] {telefon} → {mesaj[:40]}...")
        else:
            print(f"[SMS ❌] Hata kodu: {kod} → {telefon}")
    except Exception as e:
        print(f"[SMS Hata] {e}")

def send_sms(telefon: str, mesaj: str):
    """Arka planda SMS gönderir — isteği bloklamaz."""
    Thread(target=_sms_gonder, args=(telefon, mesaj), daemon=True).start()

# ── Hazır SMS şablonları ──────────────────────────────────────────────────────

def send_teklif_sms(telefon, musteri_ad, uzman_ad, ilan_baslik, fiyat):
    """Müşteriye: yeni teklif geldi."""
    mesaj = (
        f"Merhaba {musteri_ad.split()[0]}, "
        f'"{ilan_baslik[:30]}" ilaniniza '
        f"{uzman_ad.split()[0]}'den "
        f"₺{fiyat:,.0f} teklif geldi. "
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_teklif_kabul_sms(telefon, uzman_ad, ilan_baslik, fiyat):
    """Uzmana: teklifi kabul edildi."""
    mesaj = (
        f"Tebrikler {uzman_ad.split()[0]}! "
        f'"{ilan_baslik[:30]}" icin '
        f"₺{fiyat:,.0f} teklifiniz kabul edildi. "
        f"istek.com/chat"
    )
    send_sms(telefon, mesaj)

def send_randevu_sms(telefon, ad, tarih, saat, diger_kisi):
    """Randevu hatırlatması."""
    mesaj = (
        f"Hatirlatma: {ad.split()[0]}, "
        f"yarin {tarih} {saat} "
        f"{diger_kisi.split()[0]} ile randevunuz var. "
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_odeme_sms(telefon, ad, tutar, ilan_baslik):
    """Ödeme onayı."""
    mesaj = (
        f"Odeme alindi! {ad.split()[0]}, "
        f"₺{tutar:,.2f} odemeniz onaylandi. "
        f'Is: "{ilan_baslik[:25]}" '
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_uzman_onay_sms(telefon, uzman_ad):
    """Uzman profil onayı."""
    mesaj = (
        f"Tebrikler {uzman_ad.split()[0]}! "
        f"Istek profiliniz onaylandi. "
        f"Artik is ilanlarına teklif verebilirsiniz. "
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_kayit_sms(telefon, ad):
    """Hoş geldin SMS'i."""
    mesaj = (
        f"Hosgeldiniz {ad.split()[0]}! "
        f"Istek hesabiniz olusturuldu. "
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_iptal_sms(telefon, ad, ilan_baslik, sebep=""):
    """İptal bildirimi."""
    mesaj = (
        f"Merhaba {ad.split()[0]}, "
        f'"{ilan_baslik[:30]}" isleminiz iptal edildi.'
        + (f" Sebep: {sebep[:30]}" if sebep else "") +
        f" istek.com/dashboard"
    )
    send_sms(telefon, mesaj)

def send_iade_sms(telefon, ad, tutar):
    """İade bildirimi."""
    mesaj = (
        f"Merhaba {ad.split()[0]}, "
        f"₺{tutar:,.2f} iade talebiniz isleme alindi. "
        f"3-5 is gunu icinde hesabiniza yansir. "
        f"istek.com/dashboard"
    )
    send_sms(telefon, mesaj)
