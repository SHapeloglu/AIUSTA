"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Video Görüşme (Jitsi Meet)       ║
╚══════════════════════════════════════════════════════════════╝

Jitsi Meet entegrasyonu ile ücretsiz ve kurulum gerektirmeyen
WebRTC tabanlı video görüşme sistemi.

Özellikler:
    - meet.jit.si üzerinden (kendi sunucu gerekmez)
    - Benzersiz ve tahmin edilemez oda isimleri (token_urlsafe)
    - SMS + bildirim ile görüşme daveti
    - Süre takibi ve görüşme geçmişi
    - Jitsi External API ile mikrofon/kamera kontrolü

Rotalar:
    POST /video/oda-olustur     → Yeni görüşme odası oluştur + davet gönder
    GET  /video/oda/<id>        → Oda bilgisi ve Jitsi URL
    POST /video/oda/<id>/bitir  → Görüşmeyi bitir, süreyi kaydet
    GET  /video/gecmis          → Geçmiş görüşme listesi
    GET  /video/katil/<id>      → Görüşme sayfası (Jitsi embed)
"""

import uuid, secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, render_template_string
from database import query
from routes.auth import giris_gerekli, bildirim_olustur

video_bp = Blueprint("video", __name__, url_prefix="/video")

# ─── Jitsi Meet ayarları ──────────────────────────────────────────────────────
JITSI_DOMAIN  = "meet.jit.si"      # Ücretsiz, kurulum gerekmez
# Kendi Jitsi sunucunuz varsa: "jitsi.sirketiniz.com"
JITSI_APP_ID  = "istek_platform"   # Opsiyonel: Jitsi JWT için
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS video_odalar (
        id           VARCHAR(36)  PRIMARY KEY,
        oda_adi      VARCHAR(100) UNIQUE NOT NULL,
        ilan_id      VARCHAR(36),
        olusturan_id VARCHAR(36)  NOT NULL,
        davet_id     VARCHAR(36),
        baslik       VARCHAR(200),
        durum        ENUM('aktif','tamamlandi','iptal') DEFAULT 'aktif',
        baslangic    DATETIME,
        bitis        DATETIME,
        sure_dk      INT          DEFAULT 0,
        olusturma    DATETIME     DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (olusturan_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
        INDEX idx_olusturan (olusturan_id),
        INDEX idx_durum (durum)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
]

def init_video_db():
    from database import query as q
    for sql in VIDEO_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[Video DB] {e}")

# ── Oda oluştur ───────────────────────────────────────────────────────────────

@video_bp.route("/oda-olustur", methods=["POST"])
@giris_gerekli
def oda_olustur():
    b        = request.json or {}
    uid      = session["kullanici_id"]
    davet_id = b.get("davet_id")       # karşı tarafın kullanıcı ID'si
    ilan_id  = b.get("ilan_id")
    baslik   = b.get("baslik", "İştek Görüşmesi")

    # Benzersiz oda adı
    oda_adi = f"istek-{secrets.token_urlsafe(10)}"
    oid     = str(uuid.uuid4())

    query(
        """INSERT INTO video_odalar
           (id, oda_adi, ilan_id, olusturan_id, davet_id, baslik, baslangic)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (oid, oda_adi, ilan_id, uid, davet_id, baslik, datetime.now()),
        fetch="none"
    )

    # Davet edilen kişiye bildirim
    if davet_id:
        olusturan = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
        ad = olusturan["ad_soyad"] if olusturan else "Biri"
        bildirim_olustur(
            davet_id, "video",
            f"Video görüşme daveti",
            f"{ad} sizi görüşmeye davet etti: {baslik}",
            f"/video/katil/{oid}"
        )

        # SMS daveti
        try:
            davetli = query("SELECT ad_soyad, telefon FROM kullanicilar WHERE id=%s",
                            (davet_id,), fetch="one")
            if davetli and davetli.get("telefon"):
                from sms_service import send_sms
                send_sms(
                    davetli["telefon"],
                    f"Merhaba {davetli['ad_soyad'].split()[0]}, "
                    f"{ad} sizi video gorusmeye davet etti. "
                    f"Katilmak icin: istek.com/video/katil/{oid}"
                )
        except Exception:
            pass

    jitsi_url = f"https://{JITSI_DOMAIN}/{oda_adi}"

    return jsonify({
        "basarili":  True,
        "oda_id":    oid,
        "oda_adi":   oda_adi,
        "jitsi_url": jitsi_url,
        "katil_url": f"/video/katil/{oid}",
    }), 201

# ── Oda bilgisi ───────────────────────────────────────────────────────────────

@video_bp.route("/oda/<oda_id>", methods=["GET"])
@giris_gerekli
def oda_bilgi(oda_id):
    oda = query("""
        SELECT o.*, k.ad_soyad AS olusturan_ad,
               d.ad_soyad AS davetli_ad
        FROM video_odalar o
        JOIN kullanicilar k ON k.id=o.olusturan_id
        LEFT JOIN kullanicilar d ON d.id=o.davet_id
        WHERE o.id=%s
    """, (oda_id,), fetch="one")

    if not oda:
        return jsonify({"hata": "Oda bulunamadı."}), 404

    uid = session["kullanici_id"]
    if oda["olusturan_id"] != uid and oda.get("davet_id") != uid:
        return jsonify({"hata": "Bu görüşmeye erişim yetkiniz yok."}), 403

    for alan in ["baslangic", "bitis", "olusturma"]:
        if oda.get(alan):
            oda[alan] = str(oda[alan])

    oda["jitsi_url"] = f"https://{JITSI_DOMAIN}/{oda['oda_adi']}"
    return jsonify(oda)

# ── Görüşmeyi bitir ───────────────────────────────────────────────────────────

@video_bp.route("/oda/<oda_id>/bitir", methods=["POST"])
@giris_gerekli
def oda_bitir(oda_id):
    uid = session["kullanici_id"]
    oda = query("SELECT * FROM video_odalar WHERE id=%s AND olusturan_id=%s",
                (oda_id, uid), fetch="one")
    if not oda:
        return jsonify({"hata": "Oda bulunamadı."}), 404

    sure = 0
    if oda.get("baslangic"):
        sure = int((datetime.now() - oda["baslangic"]).total_seconds() / 60)

    query(
        "UPDATE video_odalar SET durum='tamamlandi', bitis=NOW(), sure_dk=%s WHERE id=%s",
        (sure, oda_id), fetch="none"
    )
    return jsonify({"basarili": True, "sure_dk": sure})

# ── Geçmiş görüşmeler ─────────────────────────────────────────────────────────

@video_bp.route("/gecmis", methods=["GET"])
@giris_gerekli
def gecmis():
    uid  = session["kullanici_id"]
    rows = query("""
        SELECT o.id, o.baslik, o.durum, o.sure_dk, o.baslangic,
               k.ad_soyad AS karsı_taraf
        FROM video_odalar o
        LEFT JOIN kullanicilar k ON k.id = (
            CASE WHEN o.olusturan_id=%s THEN o.davet_id ELSE o.olusturan_id END
        )
        WHERE o.olusturan_id=%s OR o.davet_id=%s
        ORDER BY o.olusturma DESC LIMIT 20
    """, (uid, uid, uid))

    for r in rows:
        if r.get("baslangic"): r["baslangic"] = str(r["baslangic"])
    return jsonify(rows)

# ── Görüşme sayfası ───────────────────────────────────────────────────────────

@video_bp.route("/katil/<oda_id>")
@giris_gerekli
def katil(oda_id):
    oda = query("SELECT * FROM video_odalar WHERE id=%s", (oda_id,), fetch="one")
    if not oda:
        return "Oda bulunamadı.", 404

    uid      = session["kullanici_id"]
    kullanici = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    ad        = kullanici["ad_soyad"] if kullanici else "Misafir"
    jitsi_url = f"https://{JITSI_DOMAIN}/{oda['oda_adi']}"

    return render_template_string("""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ baslik }} — İştek Video</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:sans-serif;background:#1A1A2E;color:white;height:100vh;display:flex;flex-direction:column;}
.topbar{background:rgba(229,57,53,.9);padding:12px 20px;display:flex;align-items:center;justify-content:space-between;}
.topbar h1{font-size:16px;font-weight:700;}
.topbar span{font-size:13px;opacity:.8;}
.video-wrap{flex:1;position:relative;}
#jitsi-container{width:100%;height:100%;}
.kontroller{background:#111;padding:14px 20px;display:flex;align-items:center;justify-content:center;gap:16px;}
.btn-video{padding:10px 22px;border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;}
.btn-bitir{background:#dc2626;color:white;}
.btn-geri{background:rgba(255,255,255,.1);color:white;text-decoration:none;display:inline-flex;align-items:center;}
.sure{font-size:13px;opacity:.6;margin-left:auto;}
</style>
</head>
<body>
<div class="topbar">
  <h1>{{ baslik }}</h1>
  <span id="sure-goster">00:00</span>
</div>
<div class="video-wrap">
  <div id="jitsi-container"></div>
</div>
<div class="kontroller">
  <a href="/dashboard" class="btn-video btn-geri">← Geri</a>
  <button class="btn-video btn-bitir" onclick="gorüsmeyiBitir()">Görüşmeyi Bitir</button>
  <span class="sure" id="baslangic-zaman" data-ts="{{ ts }}"></span>
</div>

<script src="https://meet.jit.si/external_api.js"></script>
<script>
const api = new JitsiMeetExternalAPI("meet.jit.si", {
    roomName:     "{{ oda_adi }}",
    parentNode:   document.getElementById("jitsi-container"),
    displayName:  "{{ kullanici_ad }}",
    lang:         "tr",
    configOverwrite: {
        startWithAudioMuted: false,
        startWithVideoMuted: false,
        prejoinPageEnabled:  false,
        disableDeepLinking:  true,
    },
    interfaceConfigOverwrite: {
        SHOW_JITSI_WATERMARK: false,
        SHOW_WATERMARK_FOR_GUESTS: false,
        TOOLBAR_BUTTONS: ['microphone','camera','chat','tileview','hangup'],
    },
});

api.addEventListeners({
    readyToClose: () => gorüsmeyiBitir(),
    videoConferenceLeft: () => gorüsmeyiBitir(),
});

// Süre sayacı
const baslangic = Date.now();
setInterval(() => {
    const s = Math.floor((Date.now() - baslangic) / 1000);
    const d = n => String(n).padStart(2,"0");
    document.getElementById("sure-goster").textContent = d(Math.floor(s/60)) + ":" + d(s%60);
}, 1000);

async function gorüsmeyiBitir() {
    try { api.executeCommand("hangup"); } catch(e) {}
    await fetch("/video/oda/{{ oda_id }}/bitir", { method: "POST" });
    window.location.href = "/dashboard";
}
</script>
</body>
</html>
""",
        baslik=oda.get("baslik", "Görüşme"),
        oda_adi=oda["oda_adi"],
        oda_id=oda_id,
        kullanici_ad=ad,
        ts=int(datetime.now().timestamp()),
    )
