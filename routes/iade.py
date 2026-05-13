import os
"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — İptal ve İade Yönetimi           ║
╚══════════════════════════════════════════════════════════════╝

Otomatik iade oranı hesaplama ve iyzico refund entegrasyonu.

İade Politikası:
    ┌──────────────────────────────────┬────────┐
    │ Randevudan 24+ saat önce         │ %100   │
    │ Randevudan 2-24 saat önce        │  %50   │
    │ Randevu başladıktan sonra        │   %0   │
    │ Randevu yoksa                    │ %100   │
    └──────────────────────────────────┴────────┘

Rotalar:
    POST /iade/talep              → Müşteri iade talebi açar
    POST /iade/onayla/<id>        → Admin onaylar → iyzico refund
    POST /iade/reddet/<id>        → Admin reddeder (sebep ile)
    GET  /iade/talepler           → Admin: bekleyen talepler
    GET  /iade/benim              → Kullanıcının kendi talepleri
    POST /iptal/ilan/<id>         → İlan iptali (müşteri/admin)
"""

import uuid, requests, json, hashlib, base64
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from database import query
from routes.auth import giris_gerekli, bildirim_olustur
from mail_service import mail, send_mail, _render

iade_bp = Blueprint("iade", __name__, url_prefix="/iade")
iptal_bp = Blueprint("iptal", __name__, url_prefix="/iptal")

# iyzico ayarları (odeme.py'den aynı)
IYZICO_API_KEY    = os.environ.get("IYZICO_API_KEY", "sandbox-your-api-key")
IYZICO_SECRET_KEY = os.environ.get("IYZICO_SECRET_KEY", "sandbox-your-secret-key")
IYZICO_BASE_URL   = "https://sandbox-api.iyzipay.com"

KOMISYON_ORANI = 0.12

# ─── İptal & iade kuralları ───────────────────────────────────────────────────
# Hizmet başlamadan 24 saat önce → %100 iade
# Hizmet başlamadan 2-24 saat    → %50 iade
# Hizmet başladıktan sonra       → iade yok (admin kararı)

def iade_orani_hesapla(odeme: dict, randevu_tarihi=None) -> float:
    if not randevu_tarihi:
        return 1.0   # Randevu yoksa tam iade
    kalan = (randevu_tarihi - datetime.now()).total_seconds() / 3600
    if kalan > 24:   return 1.0
    if kalan > 2:    return 0.5
    return 0.0

def iyzico_iade(odeme_id: str, tutar: float) -> dict:
    """iyzico üzerinden para iadesi yapar."""
    body = {
        "locale":         "tr",
        "conversationId": str(uuid.uuid4()).replace("-","")[:16],
        "paymentTransactionId": odeme_id,
        "price":          f"{tutar:.2f}",
        "currency":       "TRY",
        "ip":             "85.34.78.112",
    }
    random_str = str(uuid.uuid4()).replace("-","")[:8]
    body_str   = json.dumps(body, ensure_ascii=False, separators=(",",":"))
    raw        = f"apiKey={IYZICO_API_KEY}&randomKey={random_str}&signature={IYZICO_SECRET_KEY}{body_str}"
    imza       = hashlib.sha256(raw.encode()).hexdigest()
    pki        = f"apiKey={IYZICO_API_KEY}&randomKey={random_str}&signature={imza}"
    encoded    = base64.b64encode(pki.encode()).decode()

    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"IYZWSv2 {encoded}",
        "x-iyzi-rnd":    random_str,
    }
    try:
        r = requests.post(
            IYZICO_BASE_URL + "/payment/refund",
            headers=headers,
            data=json.dumps(body, ensure_ascii=False),
            timeout=20,
        )
        return r.json()
    except Exception as e:
        return {"status": "failure", "errorMessage": str(e)}

# ── İade talebi oluştur ───────────────────────────────────────────────────────

@iade_bp.route("/talep", methods=["POST"])
@giris_gerekli
def iade_talep():
    b       = request.json or {}
    uid     = session["kullanici_id"]
    ilan_id = b.get("ilan_id")
    sebep   = b.get("sebep", "").strip()

    if not sebep:
        return jsonify({"hata": "İade sebebi zorunludur."}), 400

    # Ödeme kaydını bul
    odeme = query(
        "SELECT * FROM odemeler WHERE ilan_id=%s AND musteri_id=%s AND durum='onaylandi'",
        (ilan_id, uid), fetch="one"
    )
    if not odeme:
        return jsonify({"hata": "Onaylı ödeme bulunamadı."}), 404

    # Zaten açık talep var mı?
    var = query(
        "SELECT id FROM iade_talepler WHERE odeme_id=%s AND durum='beklemede'",
        (odeme["id"],), fetch="one"
    )
    if var:
        return jsonify({"hata": "Bu ödeme için zaten açık bir iade talebi var."}), 409

    # İade oranını belirle
    randevu = query(
        "SELECT tarih, baslangic FROM randevular WHERE ilan_id=%s AND durum='onaylandi' LIMIT 1",
        (ilan_id,), fetch="one"
    )
    randevu_dt = None
    if randevu:
        randevu_dt = datetime.strptime(
            f"{randevu['tarih']} {randevu['baslangic']}", "%Y-%m-%d %H:%M:%S"
        )

    oran       = iade_orani_hesapla(odeme, randevu_dt)
    iade_tutar = round(float(odeme["tutar"]) * oran, 2)

    tid = str(uuid.uuid4())
    query(
        """INSERT INTO iade_talepler
           (id, odeme_id, ilan_id, musteri_id, uzman_id, sebep, iade_tutari, oran, durum)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'beklemede')""",
        (tid, odeme["id"], ilan_id, uid,
         odeme["uzman_id"], sebep, iade_tutar, oran),
        fetch="none"
    )

    # Bildirimleri gönder
    bildirim_olustur(uid, "iade",
        "İade talebiniz alındı",
        f"₺{iade_tutar:,.2f} iade talebiniz incelemeye alındı.",
        "/iade/benim"
    )
    # Admin'e bildir
    adminler = query("SELECT id FROM kullanicilar WHERE rol='admin'")
    for admin in adminler:
        bildirim_olustur(admin["id"], "iade",
            "Yeni iade talebi",
            f"₺{iade_tutar:,.2f} — {sebep[:60]}",
            "/admin"
        )

    # SMS — müşteriye
    musteri = query("SELECT ad_soyad, telefon FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    if musteri and musteri.get("telefon"):
        try:
            from sms_service import send_iade_sms
            send_iade_sms(musteri["telefon"], musteri["ad_soyad"], iade_tutar)
        except Exception:
            pass

    return jsonify({
        "basarili":    True,
        "talep_id":    tid,
        "iade_tutari": iade_tutar,
        "oran":        f"%{int(oran*100)}",
        "mesaj":       f"₺{iade_tutar:,.2f} iade talebiniz alındı. 1-3 iş günü içinde incelenir."
    }), 201

# ── İade onayla (admin) ───────────────────────────────────────────────────────

@iade_bp.route("/onayla/<talep_id>", methods=["POST"])
@giris_gerekli
def iade_onayla(talep_id):
    if session["kullanici_rol"] != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    talep = query("SELECT * FROM iade_talepler WHERE id=%s AND durum='beklemede'",
                  (talep_id,), fetch="one")
    if not talep:
        return jsonify({"hata": "Talep bulunamadı."}), 404

    odeme = query("SELECT * FROM odemeler WHERE id=%s", (talep["odeme_id"],), fetch="one")
    if not odeme:
        return jsonify({"hata": "Ödeme kaydı bulunamadı."}), 404

    # iyzico iade
    sonuc = iyzico_iade(
        odeme.get("iyzico_odeme_id", ""),
        float(talep["iade_tutari"])
    )

    if sonuc.get("status") == "success":
        query("UPDATE iade_talepler SET durum='onaylandi', islem_tarihi=NOW() WHERE id=%s",
              (talep_id,), fetch="none")
        query("UPDATE odemeler SET durum='iade' WHERE id=%s",
              (odeme["id"],), fetch="none")
        query("UPDATE ilanlar SET durum='iptal' WHERE id=%s",
              (talep["ilan_id"],), fetch="none")

        # Bildirimler
        bildirim_olustur(talep["musteri_id"], "iade",
            "İade Onaylandı ✅",
            f"₺{float(talep['iade_tutari']):,.2f} iadeniz onaylandı. 3-5 iş günü içinde hesabınıza yansır.",
        )
        bildirim_olustur(talep["uzman_id"], "iade",
            "İş İptal Edildi",
            "Müşteri iade talebinde bulundu ve onaylandı.",
        )

        # Mail
        musteri = query("SELECT ad_soyad, email, telefon FROM kullanicilar WHERE id=%s",
                        (talep["musteri_id"],), fetch="one")
        if musteri:
            ilan = query("SELECT baslik FROM ilanlar WHERE id=%s", (talep["ilan_id"],), fetch="one")
            _iade_mail(musteri["email"], musteri["ad_soyad"],
                       float(talep["iade_tutari"]), ilan["baslik"] if ilan else "-")
            if musteri.get("telefon"):
                try:
                    from sms_service import send_iade_sms
                    send_iade_sms(musteri["telefon"], musteri["ad_soyad"], float(talep["iade_tutari"]))
                except Exception:
                    pass

        return jsonify({"basarili": True, "mesaj": "İade başarıyla gerçekleştirildi."})
    else:
        return jsonify({
            "hata": "iyzico iade başarısız.",
            "detay": sonuc.get("errorMessage", "")
        }), 502

# ── İade reddet (admin) ───────────────────────────────────────────────────────

@iade_bp.route("/reddet/<talep_id>", methods=["POST"])
@giris_gerekli
def iade_reddet(talep_id):
    if session["kullanici_rol"] != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    b      = request.json or {}
    red_sebebi = b.get("sebep", "Talebiniz iade politikamız kapsamında değerlendirilemedi.")

    talep = query("SELECT * FROM iade_talepler WHERE id=%s AND durum='beklemede'",
                  (talep_id,), fetch="one")
    if not talep:
        return jsonify({"hata": "Talep bulunamadı."}), 404

    query("UPDATE iade_talepler SET durum='reddedildi', red_sebebi=%s, islem_tarihi=NOW() WHERE id=%s",
          (red_sebebi, talep_id), fetch="none")

    bildirim_olustur(talep["musteri_id"], "iade",
        "İade Talebi Reddedildi",
        red_sebebi[:100]
    )
    return jsonify({"basarili": True})

# ── Talepler (admin) ──────────────────────────────────────────────────────────

@iade_bp.route("/talepler", methods=["GET"])
@giris_gerekli
def tum_talepler():
    if session["kullanici_rol"] != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    durum = request.args.get("durum", "beklemede")
    rows  = query("""
        SELECT t.*, i.baslik AS ilan_baslik,
               m.ad_soyad AS musteri_ad, m.email AS musteri_email,
               u.ad_soyad AS uzman_ad
        FROM iade_talepler t
        JOIN ilanlar i      ON i.id = t.ilan_id
        JOIN kullanicilar m ON m.id = t.musteri_id
        JOIN kullanicilar u ON u.id = t.uzman_id
        WHERE t.durum = %s
        ORDER BY t.olusturma DESC
    """, (durum,))

    for r in rows:
        r["iade_tutari"]  = float(r["iade_tutari"])
        r["oran"]         = float(r["oran"])
        r["olusturma"]    = str(r["olusturma"])
        if r.get("islem_tarihi"): r["islem_tarihi"] = str(r["islem_tarihi"])

    return jsonify(rows)

# ── Kullanıcının kendi talepleri ──────────────────────────────────────────────

@iade_bp.route("/benim", methods=["GET"])
@giris_gerekli
def benim_taleplerim():
    uid  = session["kullanici_id"]
    rows = query("""
        SELECT t.*, i.baslik AS ilan_baslik
        FROM iade_talepler t
        JOIN ilanlar i ON i.id = t.ilan_id
        WHERE t.musteri_id = %s
        ORDER BY t.olusturma DESC
    """, (uid,))

    for r in rows:
        r["iade_tutari"] = float(r["iade_tutari"])
        r["oran"]        = float(r["oran"])
        r["olusturma"]   = str(r["olusturma"])
    return jsonify(rows)

# ── İlan iptali ───────────────────────────────────────────────────────────────

@iptal_bp.route("/ilan/<ilan_id>", methods=["POST"])
@giris_gerekli
def ilan_iptal(ilan_id):
    uid  = session["kullanici_id"]
    rol  = session["kullanici_rol"]
    b    = request.json or {}

    ilan = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı."}), 404

    # Yetki: müşteri sadece kendi ilanını, admin hepsini iptal edebilir
    if rol != "admin" and ilan["musteri_id"] != uid:
        return jsonify({"hata": "Bu ilanı iptal etme yetkiniz yok."}), 403

    if ilan["durum"] == "iptal":
        return jsonify({"hata": "İlan zaten iptal edilmiş."}), 409

    query("UPDATE ilanlar SET durum='iptal' WHERE id=%s", (ilan_id,), fetch="none")

    # İlgili teklifleri reddet
    query("UPDATE teklifler SET durum='red' WHERE ilan_id=%s AND durum='beklemede'",
          (ilan_id,), fetch="none")

    # Randevuları iptal et
    query("UPDATE randevular SET durum='iptal' WHERE ilan_id=%s AND durum IN ('beklemede','onaylandi')",
          (ilan_id,), fetch="none")

    # Teklif veren uzmanlara bildir
    uzmanlar = query(
        "SELECT DISTINCT uzman_id FROM teklifler WHERE ilan_id=%s", (ilan_id,)
    )
    for u in uzmanlar:
        bildirim_olustur(u["uzman_id"], "iptal",
            "İlan İptal Edildi",
            f'"{ilan["baslik"]}" ilanı iptal edildi.',
        )
        uzman_bilgi = query("SELECT ad_soyad, telefon FROM kullanicilar WHERE id=%s",
                            (u["uzman_id"],), fetch="one")
        if uzman_bilgi and uzman_bilgi.get("telefon"):
            try:
                from sms_service import send_iptal_sms
                send_iptal_sms(uzman_bilgi["telefon"], uzman_bilgi["ad_soyad"],
                               ilan["baslik"], b.get("sebep",""))
            except Exception:
                pass

    return jsonify({"basarili": True})

# ── Mail şablonu ──────────────────────────────────────────────────────────────

def _iade_mail(email, ad, tutar, ilan_baslik):
    body = f"""
    <p>Merhaba <strong>{ad}</strong>,</p>
    <p>İade talebiniz onaylandı. Tutar 3-5 iş günü içinde ödeme yönteminize iade edilecektir.</p>
    <div class='kart'>
      <div class='label'>Hizmet</div>
      <div class='val' style='font-size:15px;color:#333'>{ilan_baslik}</div>
      <div class='label' style='margin-top:12px'>İade Tutarı</div>
      <div class='val'>₺{tutar:,.2f}</div>
    </div>
    <p style='font-size:13px;color:#999'>Sorularınız için destek@istek.com</p>
    """
    from flask import current_app
    send_mail(current_app._get_current_object(), "İade Onaylandı ✅", [email], _render(body))

# ── Veritabanı tabloları ──────────────────────────────────────────────────────

IADE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS iade_talepler (
        id            VARCHAR(36)  PRIMARY KEY,
        odeme_id      VARCHAR(36)  NOT NULL,
        ilan_id       VARCHAR(36)  NOT NULL,
        musteri_id    VARCHAR(36)  NOT NULL,
        uzman_id      VARCHAR(36)  NOT NULL,
        sebep         TEXT         NOT NULL,
        iade_tutari   DECIMAL(10,2) NOT NULL,
        oran          DECIMAL(3,2) DEFAULT 1.00,
        durum         ENUM('beklemede','onaylandi','reddedildi') DEFAULT 'beklemede',
        red_sebebi    TEXT,
        islem_tarihi  DATETIME,
        olusturma     DATETIME     DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (odeme_id)   REFERENCES odemeler(id)      ON DELETE CASCADE,
        FOREIGN KEY (musteri_id) REFERENCES kullanicilar(id)  ON DELETE CASCADE,
        FOREIGN KEY (uzman_id)   REFERENCES kullanicilar(id)  ON DELETE CASCADE,
        INDEX idx_durum (durum),
        INDEX idx_musteri (musteri_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

def init_iade_db():
    from database import query as q
    for sql in IADE_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[İade DB] {e}")
