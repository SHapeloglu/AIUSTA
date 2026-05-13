/**
 * İştek Platform — React Native API Servisi
 * 
 * Kurulum:
 *   npm install axios @react-native-async-storage/async-storage
 * 
 * Kullanım:
 *   import api from './api_service';
 *   const uzmanlar = await api.uzmanlar.listele({ kategori: 'temizlik' });
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ─── AYARLAR ──────────────────────────────────────────────────────────────────
const BASE_URL = 'http://192.168.1.X:5000'; // ← Bilgisayarınızın IP'si
// Canlı: 'https://istek.com'
// ─────────────────────────────────────────────────────────────────────────────

const http = axios.create({
  baseURL:         BASE_URL,
  timeout:         15000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// Token interceptor
http.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('session_token');
  if (token) config.headers['X-Session-Token'] = token;
  return config;
});

// Hata interceptor
http.interceptors.response.use(
  res => res.data,
  err => {
    const mesaj = err.response?.data?.hata || 'Bağlantı hatası';
    throw new Error(mesaj);
  }
);

// ─── API MODÜLLERI ─────────────────────────────────────────────────────────────

const api = {

  // ── Kimlik doğrulama ──────────────────────────────────────────────────────
  auth: {
    giris: (email, sifre) =>
      http.post('/auth/giris', { email, sifre }),

    kayit: (data) =>
      http.post('/auth/kayit', data),

    cikis: () =>
      http.post('/auth/cikis'),

    ben: () =>
      http.get('/auth/ben'),

    profilGuncelle: (data) =>
      http.post('/auth/profil-guncelle', data),

    sifreDegistir: (eski_sifre, yeni_sifre) =>
      http.post('/auth/sifre-degistir', { eski_sifre, yeni_sifre }),
  },

  // ── Uzmanlar ──────────────────────────────────────────────────────────────
  uzmanlar: {
    listele: ({ kategori = '', sehir = '', arama = '', siralama = 'puan' } = {}) =>
      http.get('/api/uzmanlar', { params: { kategori, sehir, arama, siralama } }),

    detay: (uzman_id) =>
      http.get(`/api/uzman/${uzman_id}`),

    yakinimda: (lat, lng, yaricap_km = 50, kategori = '') =>
      http.post('/konum/yakinimda', { lat, lng, yaricap_km, kategori }),

    harita: (kategori = '') =>
      http.get('/konum/uzmanlar-harita', { params: { kategori } }),
  },

  // ── İlanlar ───────────────────────────────────────────────────────────────
  ilanlar: {
    listele: ({ kategori = '', sehir = '' } = {}) =>
      http.get('/api/ilanlar', { params: { kategori, sehir } }),

    olustur: (data) =>
      http.post('/api/ilanlar', data),

    teklifVer: (ilan_id, fiyat, mesaj) =>
      http.post('/api/teklif', { ilan_id, fiyat, mesaj }),
  },

  // ── AI Eşleştirme ─────────────────────────────────────────────────────────
  eslestir: {
    ilanIcin: (ilan_id, limit = 5) =>
      http.get(`/eslestir/${ilan_id}`, { params: { limit } }),

    anlik: ({ baslik, aciklama, kategori, butce, sehir, limit = 5 }) =>
      http.post('/eslestir/anlik', { baslik, aciklama, kategori, butce, sehir, limit }),

    neden: (uzman_id, ilan_id) =>
      http.get(`/eslestir/neden/${uzman_id}/${ilan_id}`),
  },

  // ── İş Takibi ─────────────────────────────────────────────────────────────
  takip: {
    surec: (ilan_id) =>
      http.get(`/takip/${ilan_id}`),

    adimGuncelle: (ilan_id, adim_kodu, aciklama = '') =>
      http.post(`/takip/${ilan_id}/adim`, { adim_kodu, aciklama }),

    notEkle: (ilan_id, metin) =>
      http.post(`/takip/${ilan_id}/not`, { metin }),

    tamamla: (ilan_id) =>
      http.post(`/takip/${ilan_id}/tamamla`),

    aktifIsler: () =>
      http.get('/takip/aktif'),
  },

  // ── Ödeme ─────────────────────────────────────────────────────────────────
  odeme: {
    baslat: (ilan_id, uzman_id, tutar) =>
      http.post('/odeme/baslat', { ilan_id, uzman_id, tutar }),

    gecmis: () =>
      http.get('/odeme/gecmis'),

    fatura: (odeme_id) =>
      http.get(`/odeme/fatura/${odeme_id}`),
  },

  // ── İade & İptal ──────────────────────────────────────────────────────────
  iade: {
    talep: (ilan_id, sebep) =>
      http.post('/iade/talep', { ilan_id, sebep }),

    benim: () =>
      http.get('/iade/benim'),

    ilanIptal: (ilan_id, sebep = '') =>
      http.post(`/iptal/ilan/${ilan_id}`, { sebep }),
  },

  // ── Mesajlaşma ────────────────────────────────────────────────────────────
  chat: {
    konusmalar: () =>
      http.get('/chat/konusmalar'),

    mesajlar: (diger_id) =>
      http.get(`/chat/mesajlar/${diger_id}`),

    gonder: (alici_id, metin, ilan_id = null) =>
      http.post('/chat/gonder', { alici_id, metin, ilan_id }),

    okunmamis: () =>
      http.get('/chat/okunmamis'),
  },

  // ── Takvim & Randevu ──────────────────────────────────────────────────────
  takvim: {
    musaitlik: (uzman_id) =>
      http.get(`/takvim/musaitlik/${uzman_id}`),

    musaitlikAyarla: (gunler) =>
      http.post('/takvim/musaitlik', { gunler }),

    randevuOlustur: (uzman_id, tarih, baslangic, bitis, ilan_id) =>
      http.post('/takvim/randevu', { uzman_id, tarih, baslangic, bitis, ilan_id }),

    randevularim: () =>
      http.get('/takvim/randevularim'),

    randevuOnayla: (randevu_id) =>
      http.post(`/takvim/randevu/${randevu_id}/onayla`),

    randevuIptal: (randevu_id) =>
      http.post(`/takvim/randevu/${randevu_id}/iptal`),
  },

  // ── Video Görüşme ─────────────────────────────────────────────────────────
  video: {
    odaOlustur: (davet_id, ilan_id, baslik) =>
      http.post('/video/oda-olustur', { davet_id, ilan_id, baslik }),

    odaBilgi: (oda_id) =>
      http.get(`/video/oda/${oda_id}`),

    bitir: (oda_id) =>
      http.post(`/video/oda/${oda_id}/bitir`),

    gecmis: () =>
      http.get('/video/gecmis'),
  },

  // ── Bildirimler ───────────────────────────────────────────────────────────
  bildirimler: {
    listele: () =>
      http.get('/api/bildirimler'),

    hepsiniOku: () =>
      http.post('/api/bildirimler/okundu'),
  },

  // ── Fotoğraf Yükleme ──────────────────────────────────────────────────────
  upload: {
    profilFoto: (formData) =>
      http.post('/upload/profil-foto', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      }),

    ilanFoto: (ilan_id, formData) => {
      formData.append('ilan_id', ilan_id);
      return http.post('/upload/ilan-foto', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },

    portfolyo: (formData, aciklama = '') => {
      formData.append('aciklama', aciklama);
      return http.post('/upload/portfolyo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    },
  },

  // ── Konum ─────────────────────────────────────────────────────────────────
  konum: {
    sehirBul: (lat, lng) =>
      http.get('/konum/sehir-bul', { params: { lat, lng } }),

    sehirler: () =>
      http.get('/konum/sehirler'),
  },

  // ── Kimlik Doğrulama ──────────────────────────────────────────────────────
  kimlik: {
    belgYukle: (formData) =>
      http.post('/kimlik/belge-yukle', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      }),

    durum: () =>
      http.get('/kimlik/durum'),
  },

  // ── İstatistik ────────────────────────────────────────────────────────────
  istatistik: () =>
    http.get('/api/istatistik'),
};

export default api;

/* ─── KULLANIM ÖRNEKLERİ ───────────────────────────────────────────────────────

// Giriş
const kullanici = await api.auth.giris('mehmet@demo.com', 'demo123');

// GPS ile yakın uzman ara
const { uzmanlar } = await api.uzmanlar.yakinimda(41.0082, 28.9784, 30, 'temizlik');

// AI eşleştirme
const eslesme = await api.eslestir.anlik({
  baslik: 'Ev temizliği yaptırmak istiyorum',
  kategori: 'temizlik',
  sehir: 'İstanbul',
  butce: 500,
});

// Video görüşme başlat
const oda = await api.video.odaOlustur(uzmanId, ilanId, 'Keşif Görüşmesi');
// Ardından WebView ile: oda.katil_url açılır

// Socket.IO bağlantısı (react-native-socket.io-client)
import io from 'socket.io-client';
const socket = io(BASE_URL, { withCredentials: true });
socket.emit('oda_katil', { kullanici_id: ben.id });
socket.on('mesaj_al', (msg) => console.log(msg));

─────────────────────────────────────────────────────────────────────────────── */
