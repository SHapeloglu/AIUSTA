"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Gerçek Zamanlı Mesajlaşma        ║
╚══════════════════════════════════════════════════════════════╝

Flask-SocketIO ile WebSocket tabanlı gerçek zamanlı mesajlaşma.
REST API (fallback) ve Socket.IO eventleri birlikte çalışır.

REST Rotaları:
    GET  /chat/konusmalar          → Tüm konuşmaların listesi (son mesaj, okunmamış sayısı)
    GET  /chat/mesajlar/<diger_id> → İki kullanıcı arası tüm mesajlar
    POST /chat/gonder              → Mesaj gönder (REST fallback)
    GET  /chat/okunmamis           → Okunmamış mesaj sayısı

Socket.IO Olayları (client → server):
    'oda_katil'      → { kullanici_id } — Kişisel odaya katıl
    'mesaj_gonder'   → { gonderen_id, alici_id, metin, ilan_id? }
    'okundu_isaretle'→ { gonderen_id, alici_id }

Socket.IO Olayları (server → client):
    'mesaj_al'       → { id, gonderen_id, gonderen_ad, metin, tarih, benim }
"""

from flask import Blueprint, request, jsonify, session
from database import query
import uuid
from datetime import datetime

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

from routes.auth import giris_gerekli, bildirim_olustur

# ── REST: Konuşmalar ──────────────────────────────────────────────────────────

@chat_bp.route("/konusmalar", methods=["GET"])
@giris_gerekli
def konusmalar():
    uid = session["kullanici_id"]

    rows = query("""
        SELECT
            k.id, k.ad_soyad, k.rol,
            m.metin AS son_mesaj,
            m.tarih AS son_tarih,
            SUM(CASE WHEN m2.okundu=0 AND m2.alici_id=%s THEN 1 ELSE 0 END) AS okunmamis
        FROM kullanicilar k
        JOIN mesajlar m ON (
            (m.gonderen_id=%s AND m.alici_id=k.id) OR
            (m.alici_id=%s AND m.gonderen_id=k.id)
        )
        LEFT JOIN mesajlar m2 ON (
            m2.gonderen_id=k.id AND m2.alici_id=%s
        )
        WHERE k.id != %s
        GROUP BY k.id, k.ad_soyad, k.rol, m.metin, m.tarih
        ORDER BY m.tarih DESC
    """, (uid, uid, uid, uid, uid))

    for r in rows:
        if r.get("son_tarih"):
            r["son_tarih"] = str(r["son_tarih"])

    return jsonify(rows)

# ── REST: Mesajlar ────────────────────────────────────────────────────────────

@chat_bp.route("/mesajlar/<diger_id>", methods=["GET"])
@giris_gerekli
def mesajlar(diger_id):
    uid = session["kullanici_id"]

    rows = query("""
        SELECT m.*, k.ad_soyad AS gonderen_ad
        FROM mesajlar m
        JOIN kullanicilar k ON k.id = m.gonderen_id
        WHERE (m.gonderen_id=%s AND m.alici_id=%s)
           OR (m.gonderen_id=%s AND m.alici_id=%s)
        ORDER BY m.tarih ASC
    """, (uid, diger_id, diger_id, uid))

    # Okundu olarak işaretle
    query(
        "UPDATE mesajlar SET okundu=1 WHERE gonderen_id=%s AND alici_id=%s AND okundu=0",
        (diger_id, uid), fetch="none"
    )

    for r in rows:
        if r.get("tarih"):
            r["tarih"] = str(r["tarih"])
        r["benim"] = (r["gonderen_id"] == uid)

    return jsonify(rows)

# ── REST: Mesaj Gönder ────────────────────────────────────────────────────────

@chat_bp.route("/gonder", methods=["POST"])
@giris_gerekli
def mesaj_gonder():
    b       = request.json or {}
    alici   = b.get("alici_id")
    metin   = (b.get("metin") or "").strip()
    ilan_id = b.get("ilan_id")
    uid     = session["kullanici_id"]

    if not alici or not metin:
        return jsonify({"hata": "Alıcı ve mesaj zorunludur."}), 400

    mid = str(uuid.uuid4())
    query(
        "INSERT INTO mesajlar (id, gonderen_id, alici_id, ilan_id, metin) "
        "VALUES (%s,%s,%s,%s,%s)",
        (mid, uid, alici, ilan_id, metin), fetch="none"
    )

    gonderen = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    bildirim_olustur(
        alici, "mesaj",
        f"{gonderen['ad_soyad']} size mesaj gönderdi",
        metin[:80],
        f"/chat/{uid}"
    )

    return jsonify({"basarili": True, "mesaj_id": mid})

# ── REST: Okunmamış sayısı ────────────────────────────────────────────────────

@chat_bp.route("/okunmamis", methods=["GET"])
@giris_gerekli
def okunmamis():
    uid = session["kullanici_id"]
    r   = query(
        "SELECT COUNT(*) AS n FROM mesajlar WHERE alici_id=%s AND okundu=0",
        (uid,), fetch="one"
    )
    return jsonify({"sayi": r["n"]})


# ─────────────────────────────────────────────────────────────────────────────
# Socket.IO olay işleyicileri — app.py içinde socketio.on() ile kaydedilir
# ─────────────────────────────────────────────────────────────────────────────

def register_socket_events(socketio):
    """app.py'de: register_socket_events(socketio) şeklinde çağrılır."""

    aktif_kullanicilar = {}   # {kullanici_id: socket_id}

    @socketio.on("oda_katil")
    def oda_katil(data):
        from flask_socketio import join_room
        kid = data.get("kullanici_id")
        if kid:
            aktif_kullanicilar[kid] = request.sid
            join_room(kid)

    @socketio.on("mesaj_gonder")
    def ws_mesaj_gonder(data):
        from flask_socketio import emit
        gonderen_id = data.get("gonderen_id")
        alici_id    = data.get("alici_id")
        metin       = (data.get("metin") or "").strip()

        if not gonderen_id or not alici_id or not metin:
            return

        mid = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        query(
            "INSERT INTO mesajlar (id, gonderen_id, alici_id, ilan_id, metin) "
            "VALUES (%s,%s,%s,%s,%s)",
            (mid, gonderen_id, alici_id, data.get("ilan_id"), metin),
            fetch="none"
        )

        gonderen = query(
            "SELECT ad_soyad FROM kullanicilar WHERE id=%s", (gonderen_id,), fetch="one"
        )

        payload = {
            "id": mid,
            "gonderen_id": gonderen_id,
            "gonderen_ad": gonderen["ad_soyad"] if gonderen else "?",
            "metin": metin,
            "tarih": now,
            "benim": False,
        }

        # Alıcıya gönder
        emit("mesaj_al", {**payload, "benim": False}, room=alici_id)
        # Göndericiye gönder (onay)
        emit("mesaj_al", {**payload, "benim": True}, room=gonderen_id)

    @socketio.on("okundu_isaretle")
    def okundu_isaretle(data):
        alici_id    = data.get("alici_id")
        gonderen_id = data.get("gonderen_id")
        if alici_id and gonderen_id:
            query(
                "UPDATE mesajlar SET okundu=1 WHERE gonderen_id=%s AND alici_id=%s AND okundu=0",
                (gonderen_id, alici_id), fetch="none"
            )

    @socketio.on("disconnect")
    def disconnect():
        for kid, sid in list(aktif_kullanicilar.items()):
            if sid == request.sid:
                del aktif_kullanicilar[kid]
                break
