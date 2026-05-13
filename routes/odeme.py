import os
"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — iyzico Ödeme Entegrasyonu        ║
╚══════════════════════════════════════════════════════════════╝

iyzico ödeme altyapısı ile güvenli ödeme akışı sağlar.
Escrow modeli: para önce platformda tutulur, iş tamamlanınca uzmana aktarılır.

Ödeme Akışı:
    1. POST /odeme/baslat  → iyzico checkout formu HTML'i döner
    2. Kullanıcı ödeme yapar (iframe içinde)
    3. POST /odeme/callback → iyzico sonucu bildirir
    4. Platform ödemeyi doğrular ve kayıt günceller

Rotalar:
    POST /odeme/baslat      → Ödeme başlat, checkout form HTML döner
    POST /odeme/callback    → iyzico webhook (otomatik çağrılır)
    GET  /odeme/basarili    → Başarılı ödeme sonrası yönlendirme
    GET  /odeme/basarisiz   → Başarısız ödeme yönlendirme
    GET  /odeme/gecmis      → Kullanıcı ödeme geçmişi
    GET  /odeme/fatura/<id> → Fatura detayı

Sandbox Test:
    iyzico sandbox kimlik bilgileri: sandbox-api.iyzipay.com
    Test kart: 5528790000000008 / 12/30 / 123
"""

import hashlib, base64, json, uuid, hmac, requests as req
from datetime import datetime
from flask import Blueprint, request, jsonify, session, render_template_string
from database import query
from routes.auth import giris_gerekli, bildirim_olustur

odeme_bp = Blueprint("odeme", __name__, url_prefix="/odeme")

# ─── iyzico AYARLARI ──────────────────────────────────────────────────────────
# Sandbox (test) anahtarları — canlıya geçince değiştirin
IYZICO_API_KEY    = os.environ.get("IYZICO_API_KEY", "sandbox-your-api-key")       # ← iyzico panelinden alın
IYZICO_SECRET_KEY = os.environ.get("IYZICO_SECRET_KEY", "sandbox-your-secret-key")    # ← iyzico panelinden alın
IYZICO_BASE_URL   = os.environ.get("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com")
# IYZICO_BASE_URL = "https://api.iyzipay.com"           # canlı

KOMISYON_ORANI = 0.12   # %12 platform komisyonu
# ─────────────────────────────────────────────────────────────────────────────

def iyzico_imza(api_key, secret, random_str, body_str):
    """iyzico PKI imza üreteci"""
    raw = f"apiKey={api_key}&randomKey={random_str}&signature={secret}{body_str}"
    return hashlib.sha256(raw.encode()).hexdigest()

def iyzico_header(body: dict) -> dict:
    random_str = str(uuid.uuid4()).replace("-","")[:8]
    body_str   = json.dumps(body, ensure_ascii=False, separators=(",",":"))
    imza       = iyzico_imza(IYZICO_API_KEY, IYZICO_SECRET_KEY, random_str, body_str)
    pki        = f"apiKey={IYZICO_API_KEY}&randomKey={random_str}&signature={imza}"
    encoded    = base64.b64encode(pki.encode()).decode()
    return {
        "Content-Type":  "application/json",
        "Authorization": f"IYZWSv2 {encoded}",
        "x-iyzi-rnd":    random_str,
    }

def iyzico_post(endpoint: str, body: dict):
    headers = iyzico_header(body)
    r = req.post(
        IYZICO_BASE_URL + endpoint,
        headers=headers,
        data=json.dumps(body, ensure_ascii=False),
        timeout=20,
    )
    return r.json()

# ── Ödeme Başlat ──────────────────────────────────────────────────────────────

@odeme_bp.route("/baslat", methods=["POST"])
@giris_gerekli
def odeme_baslat():
    b        = request.json or {}
    ilan_id  = b.get("ilan_id")
    uzman_id = b.get("uzman_id")
    tutar    = float(b.get("tutar", 0))

    if tutar <= 0:
        return jsonify({"hata": "Geçersiz tutar."}), 400

    ilan   = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    uzman  = query("SELECT * FROM kullanicilar WHERE id=%s", (uzman_id,), fetch="one")
    musteri = query(
        "SELECT * FROM kullanicilar WHERE id=%s",
        (session["kullanici_id"],), fetch="one"
    )

    if not ilan or not uzman or not musteri:
        return jsonify({"hata": "Geçersiz ilan veya kullanıcı."}), 404

    komisyon  = round(tutar * KOMISYON_ORANI, 2)
    odeme_id  = str(uuid.uuid4())
    konusma_id = str(uuid.uuid4()).replace("-","")[:16]

    # Ödeme kaydını oluştur (beklemede)
    query(
        "INSERT INTO odemeler (id, ilan_id, musteri_id, uzman_id, tutar, komisyon, durum) "
        "VALUES (%s,%s,%s,%s,%s,%s,'beklemede')",
        (odeme_id, ilan_id, musteri["id"], uzman_id, tutar, komisyon),
        fetch="none"
    )

    # iyzico isteği oluştur
    ad_parcalari = musteri["ad_soyad"].split(" ", 1)
    isim   = ad_parcalari[0]
    soyisim = ad_parcalari[1] if len(ad_parcalari) > 1 else "-"

    body = {
        "locale": "tr",
        "conversationId": konusma_id,
        "price": str(tutar),
        "paidPrice": str(tutar),
        "currency": "TRY",
        "basketId": odeme_id,
        "paymentGroup": "PRODUCT",
        "callbackUrl": request.host_url.rstrip("/") + "/odeme/callback",
        "enabledInstallments": [1, 2, 3, 6, 9, 12],
        "buyer": {
            "id": musteri["id"],
            "name": isim,
            "surname": soyisim,
            "gsmNumber": musteri.get("telefon") or "+905000000000",
            "email": musteri["email"],
            "identityNumber": "74300864791",   # Sandbox için sabit
            "lastLoginDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "registrationDate": "2024-01-01 00:00:00",
            "registrationAddress": musteri.get("sehir") or "İstanbul",
            "ip": request.remote_addr or "85.34.78.112",
            "city": musteri.get("sehir") or "İstanbul",
            "country": "Turkey",
        },
        "shippingAddress": {
            "contactName": musteri["ad_soyad"],
            "city": musteri.get("sehir") or "İstanbul",
            "country": "Turkey",
            "address": "Hizmet adresi",
        },
        "billingAddress": {
            "contactName": musteri["ad_soyad"],
            "city": musteri.get("sehir") or "İstanbul",
            "country": "Turkey",
            "address": "Fatura adresi",
        },
        "basketItems": [
            {
                "id": ilan_id,
                "name": (ilan.get("baslik") or "Hizmet")[:100],
                "category1": "Hizmet",
                "itemType": "VIRTUAL",
                "price": str(tutar),
            }
        ],
    }

    sonuc = iyzico_post("/payment/iyzipos/initialize/checkoutform", body)

    if sonuc.get("status") != "success":
        return jsonify({
            "hata": sonuc.get("errorMessage", "iyzico hatası"),
            "detay": sonuc
        }), 502

    # Token'ı kaydet
    query(
        "UPDATE odemeler SET iyzico_token=%s WHERE id=%s",
        (sonuc.get("token"), odeme_id), fetch="none"
    )

    return jsonify({
        "basarili": True,
        "odeme_id": odeme_id,
        "checkout_form_content": sonuc.get("checkoutFormContent"),
        "token": sonuc.get("token"),
    })

# ── iyzico Callback ───────────────────────────────────────────────────────────

@odeme_bp.route("/callback", methods=["POST"])
def odeme_callback():
    token = request.form.get("token")
    if not token:
        return "Geçersiz token", 400

    # Sonucu sorgula
    body  = {"locale": "tr", "token": token}
    sonuc = iyzico_post("/payment/iyzipos/checkoutform/auth/ecom/detail", body)

    odeme = query("SELECT * FROM odemeler WHERE iyzico_token=%s", (token,), fetch="one")
    if not odeme:
        return "Ödeme bulunamadı", 404

    if sonuc.get("status") == "success":
        iyzico_odeme_id = sonuc.get("paymentId","")
        query(
            "UPDATE odemeler SET durum='onaylandi', iyzico_odeme_id=%s WHERE id=%s",
            (iyzico_odeme_id, odeme["id"]), fetch="none"
        )
        query(
            "UPDATE ilanlar SET durum='tamamlandi' WHERE id=%s",
            (odeme["ilan_id"],), fetch="none"
        )
        # Bildirimleri gönder
        bildirim_olustur(
            odeme["musteri_id"], "odeme",
            "Ödemeniz alındı",
            f"₺{odeme['tutar']} tutarındaki ödemeniz başarıyla tamamlandı.",
            f"/ilan/{odeme['ilan_id']}"
        )
        bildirim_olustur(
            odeme["uzman_id"], "odeme",
            "Yeni ödeme alındı",
            f"₺{odeme['tutar'] - odeme['komisyon']} tutarında ödeme hesabınıza aktarıldı.",
            f"/ilan/{odeme['ilan_id']}"
        )
        return "<script>window.location='/odeme/basarili'</script>"
    else:
        query(
            "UPDATE odemeler SET durum='basarisiz' WHERE id=%s",
            (odeme["id"],), fetch="none"
        )
        return "<script>window.location='/odeme/basarisiz'</script>"

# ── Sonuç Sayfaları ───────────────────────────────────────────────────────────

@odeme_bp.route("/basarili")
def odeme_basarili():
    return render_template_string("""
    <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
    <title>Ödeme Başarılı</title>
    <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f0fdf4;}
    .box{text-align:center;background:white;padding:48px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);}
    .ic{font-size:64px;margin-bottom:16px;} h1{color:#166534;} p{color:#555;} a{color:#16a34a;}</style></head>
    <body><div class="box"><div class="ic">✅</div>
    <h1>Ödeme Başarılı!</h1>
    <p>Ödemeniz alındı. Uzmanınız en kısa sürede sizinle iletişime geçecek.</p>
    <a href="/">Ana Sayfaya Dön</a></div></body></html>
    """)

@odeme_bp.route("/basarisiz")
def odeme_basarisiz():
    return render_template_string("""
    <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
    <title>Ödeme Başarısız</title>
    <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#fef2f2;}
    .box{text-align:center;background:white;padding:48px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);}
    .ic{font-size:64px;margin-bottom:16px;} h1{color:#991b1b;} p{color:#555;} a{color:#dc2626;}</style></head>
    <body><div class="box"><div class="ic">❌</div>
    <h1>Ödeme Başarısız</h1>
    <p>İşleminiz tamamlanamadı. Lütfen tekrar deneyin veya farklı bir kart kullanın.</p>
    <a href="/">Ana Sayfaya Dön</a></div></body></html>
    """)

# ── Ödeme Geçmişi ─────────────────────────────────────────────────────────────

@odeme_bp.route("/gecmis", methods=["GET"])
@giris_gerekli
def odeme_gecmis():
    uid = session["kullanici_id"]
    rol = session["kullanici_rol"]

    if rol == "musteri":
        odemeler = query(
            """SELECT o.*, i.baslik AS ilan_baslik, k.ad_soyad AS uzman_ad
               FROM odemeler o
               JOIN ilanlar i ON i.id = o.ilan_id
               JOIN kullanicilar k ON k.id = o.uzman_id
               WHERE o.musteri_id=%s ORDER BY o.tarih DESC""",
            (uid,)
        )
    else:
        odemeler = query(
            """SELECT o.*, i.baslik AS ilan_baslik, k.ad_soyad AS musteri_ad,
                      (o.tutar - o.komisyon) AS net_tutar
               FROM odemeler o
               JOIN ilanlar i ON i.id = o.ilan_id
               JOIN kullanicilar k ON k.id = o.musteri_id
               WHERE o.uzman_id=%s ORDER BY o.tarih DESC""",
            (uid,)
        )

    for o in odemeler:
        o["tutar"]    = float(o["tutar"])
        o["komisyon"] = float(o["komisyon"])
        if o.get("tarih"):
            o["tarih"] = str(o["tarih"])

    return jsonify(odemeler)

# ── Fatura (basit) ────────────────────────────────────────────────────────────

@odeme_bp.route("/fatura/<odeme_id>", methods=["GET"])
@giris_gerekli
def fatura(odeme_id):
    uid = session["kullanici_id"]
    o = query(
        """SELECT o.*, i.baslik, k.ad_soyad AS musteri_ad, u.ad_soyad AS uzman_ad
           FROM odemeler o
           JOIN ilanlar i ON i.id=o.ilan_id
           JOIN kullanicilar k ON k.id=o.musteri_id
           JOIN kullanicilar u ON u.id=o.uzman_id
           WHERE o.id=%s AND (o.musteri_id=%s OR o.uzman_id=%s)""",
        (odeme_id, uid, uid), fetch="one"
    )
    if not o:
        return jsonify({"hata": "Fatura bulunamadı."}), 404

    o["tutar"]    = float(o["tutar"])
    o["komisyon"] = float(o["komisyon"])
    if o.get("tarih"):
        o["tarih"] = str(o["tarih"])
    return jsonify(o)
