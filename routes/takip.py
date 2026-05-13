"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — İş Durum Takip Sistemi           ║
╚══════════════════════════════════════════════════════════════╝

Her ilanın 8 adımlı iş sürecini takip eder.

İş Akışı Adımları:
    1. 📋 İlan Yayınlandı
    2. 📩 Teklif Alındı
    3. ✅ Teklif Kabul Edildi
    4. 💳 Ödeme Yapıldı
    5. 📅 Randevu Belirlendi
    6. 🔨 İş Başladı
    7. 🎉 İş Tamamlandı
    8. ⭐ Değerlendirildi

Rotalar:
    GET  /takip/<ilan_id>          → İş süreci, adımlar ve notlar
    POST /takip/<ilan_id>/adim     → Adım güncelle (tamamlandı işaretle)
    POST /takip/<ilan_id>/not      → İş notu ekle
    POST /takip/<ilan_id>/tamamla  → İşi tamamla (uzman veya admin)
    GET  /takip/aktif              → Kullanıcının aktif işleri
"""

from flask import Blueprint, request, jsonify, session
from database import query
from routes.auth import giris_gerekli, bildirim_olustur
import uuid
from datetime import datetime

takip_bp = Blueprint("takip", __name__, url_prefix="/takip")

# ─── Sabit iş adımları ────────────────────────────────────────────────────────
IS_ADIMLARI = [
    {"sira": 1, "kod": "ilan_acildi",        "ad": "İlan Yayınlandı",        "ikon": "📋"},
    {"sira": 2, "kod": "teklif_alindi",       "ad": "Teklif Alındı",          "ikon": "📩"},
    {"sira": 3, "kod": "teklif_kabul",        "ad": "Teklif Kabul Edildi",    "ikon": "✅"},
    {"sira": 4, "kod": "odeme_yapildi",       "ad": "Ödeme Yapıldı",          "ikon": "💳"},
    {"sira": 5, "kod": "randevu_belirlendi",  "ad": "Randevu Belirlendi",     "ikon": "📅"},
    {"sira": 6, "kod": "is_basladi",          "ad": "İş Başladı",             "ikon": "🔨"},
    {"sira": 7, "kod": "is_tamamlandi",       "ad": "İş Tamamlandı",          "ikon": "🎉"},
    {"sira": 8, "kod": "degerlendirildi",     "ad": "Değerlendirildi",        "ikon": "⭐"},
]

# ─── Veritabanı tabloları ─────────────────────────────────────────────────────
TAKIP_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS is_takip (
        id            VARCHAR(36)  PRIMARY KEY,
        ilan_id       VARCHAR(36)  NOT NULL,
        adim_kodu     VARCHAR(50)  NOT NULL,
        adim_adi      VARCHAR(100),
        tamamlandi    TINYINT(1)   DEFAULT 0,
        tarih         DATETIME,
        aciklama      TEXT,
        ekleyen_id    VARCHAR(36),
        UNIQUE KEY tek_adim (ilan_id, adim_kodu),
        FOREIGN KEY (ilan_id) REFERENCES ilanlar(id) ON DELETE CASCADE,
        INDEX idx_ilan (ilan_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS is_notlar (
        id        VARCHAR(36) PRIMARY KEY,
        ilan_id   VARCHAR(36) NOT NULL,
        yazan_id  VARCHAR(36) NOT NULL,
        metin     TEXT        NOT NULL,
        tarih     DATETIME    DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ilan_id)  REFERENCES ilanlar(id)      ON DELETE CASCADE,
        FOREIGN KEY (yazan_id) REFERENCES kullanicilar(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

def init_takip_db():
    from database import query as q
    for sql in TAKIP_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[Takip DB] {e}")

def adim_olustur(ilan_id: str, adim_kodu: str, aciklama: str = "", ekleyen_id: str = None):
    """Bir adımı tamamlandı olarak işaretle (yoksa oluştur)."""
    adim_meta = next((a for a in IS_ADIMLARI if a["kod"] == adim_kodu), None)
    adim_adi  = adim_meta["ad"] if adim_meta else adim_kodu

    query(
        """INSERT INTO is_takip (id, ilan_id, adim_kodu, adim_adi, tamamlandi, tarih, aciklama, ekleyen_id)
           VALUES (%s,%s,%s,%s,1,%s,%s,%s)
           ON DUPLICATE KEY UPDATE tamamlandi=1, tarih=%s, aciklama=%s""",
        (str(uuid.uuid4()), ilan_id, adim_kodu, adim_adi,
         datetime.now(), aciklama, ekleyen_id,
         datetime.now(), aciklama),
        fetch="none"
    )

# ─── API: İş süreci ───────────────────────────────────────────────────────────

@takip_bp.route("/<ilan_id>", methods=["GET"])
@giris_gerekli
def is_sureci(ilan_id):
    ilan = query("""
        SELECT i.*, k.ad_soyad AS musteri_ad,
               t.durum AS kabul_teklif_durum,
               u.ad_soyad AS uzman_ad, u.id AS uzman_id,
               p.saatlik_ucret, p.puan
        FROM ilanlar i
        LEFT JOIN kullanicilar k ON k.id = i.musteri_id
        LEFT JOIN teklifler t ON t.ilan_id=i.id AND t.durum='kabul'
        LEFT JOIN kullanicilar u ON u.id = t.uzman_id
        LEFT JOIN uzman_profiller p ON p.kullanici_id = u.id
        WHERE i.id=%s
    """, (ilan_id,), fetch="one")

    if not ilan:
        return jsonify({"hata": "İlan bulunamadı."}), 404

    # Kaydedilmiş adımları al
    kayitli = {r["adim_kodu"]: r for r in
               query("SELECT * FROM is_takip WHERE ilan_id=%s", (ilan_id,))}

    # Tüm adımları birleştir
    adimlar = []
    for meta in IS_ADIMLARI:
        kayit = kayitli.get(meta["kod"])
        adimlar.append({
            "sira":        meta["sira"],
            "kod":         meta["kod"],
            "ad":          meta["ad"],
            "ikon":        meta["ikon"],
            "tamamlandi":  bool(kayit["tamamlandi"]) if kayit else False,
            "tarih":       str(kayit["tarih"]) if kayit and kayit.get("tarih") else None,
            "aciklama":    kayit["aciklama"] if kayit else None,
        })

    # Aktif adım: tamamlanmamışların ilki
    aktif_sira = next((a["sira"] for a in adimlar if not a["tamamlandi"]), len(adimlar))

    # Notlar
    notlar = query("""
        SELECT n.metin, n.tarih, k.ad_soyad AS yazan_ad, k.rol
        FROM is_notlar n
        JOIN kullanicilar k ON k.id=n.yazan_id
        WHERE n.ilan_id=%s ORDER BY n.tarih ASC
    """, (ilan_id,))
    for n in notlar:
        n["tarih"] = str(n["tarih"])

    # Ödeme durumu
    odeme = query(
        "SELECT durum, tutar FROM odemeler WHERE ilan_id=%s ORDER BY tarih DESC LIMIT 1",
        (ilan_id,), fetch="one"
    )

    # Randevu
    randevu = query(
        "SELECT tarih, baslangic, bitis, durum FROM randevular WHERE ilan_id=%s AND durum='onaylandi' LIMIT 1",
        (ilan_id,), fetch="one"
    )
    if randevu:
        randevu["tarih"] = str(randevu["tarih"])
        randevu["baslangic"] = str(randevu["baslangic"])
        randevu["bitis"] = str(randevu["bitis"])

    return jsonify({
        "ilan": {
            "id":          ilan["id"],
            "baslik":      ilan["baslik"],
            "durum":       ilan["durum"],
            "musteri_ad":  ilan["musteri_ad"],
            "uzman_ad":    ilan.get("uzman_ad"),
            "uzman_id":    ilan.get("uzman_id"),
        },
        "adimlar":    adimlar,
        "aktif_sira": aktif_sira,
        "tamamlanma": f"{sum(1 for a in adimlar if a['tamamlandi'])}/{len(adimlar)}",
        "yuzde":      round(sum(1 for a in adimlar if a["tamamlandi"]) / len(adimlar) * 100),
        "notlar":     notlar,
        "odeme":      {"durum": odeme["durum"], "tutar": float(odeme["tutar"])} if odeme else None,
        "randevu":    randevu,
    })

# ─── API: Adım güncelle ───────────────────────────────────────────────────────

@takip_bp.route("/<ilan_id>/adim", methods=["POST"])
@giris_gerekli
def adim_guncelle(ilan_id):
    b          = request.json or {}
    adim_kodu  = b.get("adim_kodu")
    aciklama   = b.get("aciklama", "")
    uid        = session["kullanici_id"]

    if not adim_kodu:
        return jsonify({"hata": "adim_kodu zorunlu."}), 400

    ilan = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı."}), 404

    adim_olustur(ilan_id, adim_kodu, aciklama, uid)

    # Bildirimleri gönder
    adim_meta = next((a for a in IS_ADIMLARI if a["kod"] == adim_kodu), {})
    hedef_id  = ilan["musteri_id"] if session["kullanici_rol"] == "uzman" else None

    if hedef_id:
        bildirim_olustur(
            hedef_id, "takip",
            f"İş güncellemesi: {adim_meta.get('ad','Güncelleme')}",
            f"{ilan['baslik']} — {aciklama or adim_meta.get('ad','')}",
            f"/takip/{ilan_id}"
        )

    return jsonify({"basarili": True, "adim": adim_kodu})

# ─── API: Not ekle ────────────────────────────────────────────────────────────

@takip_bp.route("/<ilan_id>/not", methods=["POST"])
@giris_gerekli
def not_ekle(ilan_id):
    b     = request.json or {}
    metin = (b.get("metin") or "").strip()
    uid   = session["kullanici_id"]

    if not metin:
        return jsonify({"hata": "Not metni zorunlu."}), 400

    query(
        "INSERT INTO is_notlar (id, ilan_id, yazan_id, metin) VALUES (%s,%s,%s,%s)",
        (str(uuid.uuid4()), ilan_id, uid, metin), fetch="none"
    )
    return jsonify({"basarili": True})

# ─── API: İşi tamamla ────────────────────────────────────────────────────────

@takip_bp.route("/<ilan_id>/tamamla", methods=["POST"])
@giris_gerekli
def is_tamamla(ilan_id):
    uid  = session["kullanici_id"]
    ilan = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı."}), 404

    # İşi tamamla
    query("UPDATE ilanlar SET durum='tamamlandi' WHERE id=%s", (ilan_id,), fetch="none")
    adim_olustur(ilan_id, "is_tamamlandi", "İş başarıyla tamamlandı.", uid)

    # Uzmanın iş sayısını artır
    teklif = query(
        "SELECT uzman_id FROM teklifler WHERE ilan_id=%s AND durum='kabul' LIMIT 1",
        (ilan_id,), fetch="one"
    )
    if teklif:
        query(
            "UPDATE uzman_profiller SET is_tamamlanan=is_tamamlanan+1 WHERE kullanici_id=%s",
            (teklif["uzman_id"],), fetch="none"
        )
        bildirim_olustur(
            teklif["uzman_id"], "takip",
            "İş tamamlandı! 🎉",
            f"{ilan['baslik']} tamamlandı. Müşteri sizi değerlendirmeyi bekliyoruz.",
        )

    # Müşteriye değerlendirme daveti
    if ilan.get("musteri_id"):
        bildirim_olustur(
            ilan["musteri_id"], "takip",
            "İşiniz tamamlandı!",
            f"{ilan['baslik']} — Uzmanınızı değerlendirmeyi unutmayın.",
        )

    # SMS
    try:
        from sms_service import send_sms
        if ilan.get("musteri_id"):
            musteri = query("SELECT ad_soyad, telefon FROM kullanicilar WHERE id=%s",
                            (ilan["musteri_id"],), fetch="one")
            if musteri and musteri.get("telefon"):
                send_sms(musteri["telefon"],
                         f"Merhaba {musteri['ad_soyad'].split()[0]}, "
                         f"'{ilan['baslik'][:30]}' isleminiz tamamlandi! "
                         f"Uzmaninizi degerlendirin: istek.com/dashboard")
    except Exception:
        pass

    return jsonify({"basarili": True})

# ─── API: Aktif işler ─────────────────────────────────────────────────────────

@takip_bp.route("/aktif", methods=["GET"])
@giris_gerekli
def aktif_isler():
    uid = session["kullanici_id"]
    rol = session["kullanici_rol"]

    if rol == "musteri":
        ilanlar = query(
            "SELECT * FROM ilanlar WHERE musteri_id=%s AND durum='aktif' ORDER BY olusturma_tarihi DESC",
            (uid,)
        )
    else:
        # Uzmansa kabul edilmiş tekliflerin ilanları
        ilanlar = query("""
            SELECT i.* FROM ilanlar i
            JOIN teklifler t ON t.ilan_id=i.id
            WHERE t.uzman_id=%s AND t.durum='kabul' AND i.durum='aktif'
            ORDER BY i.olusturma_tarihi DESC
        """, (uid,))

    sonuc = []
    for ilan in ilanlar:
        tamamlanan_adim = query(
            "SELECT COUNT(*) AS n FROM is_takip WHERE ilan_id=%s AND tamamlandi=1",
            (ilan["id"],), fetch="one"
        )["n"]
        yuzde = round(tamamlanan_adim / len(IS_ADIMLARI) * 100)
        sonuc.append({
            "id":      ilan["id"],
            "baslik":  ilan["baslik"],
            "sehir":   ilan["sehir"],
            "durum":   ilan["durum"],
            "yuzde":   yuzde,
            "tarih":   str(ilan["olusturma_tarihi"]) if ilan.get("olusturma_tarihi") else None,
        })

    return jsonify(sonuc)
