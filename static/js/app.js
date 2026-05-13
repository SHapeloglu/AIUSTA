let aktifTab = 'uzmanlar';

const KATEGORI_ADLARI = {
  temizlik: '🧹 Ev Temizliği', tamirat: '🔧 Tamirat', nakliyat: '🚚 Nakliyat',
  bahce: '🌿 Bahçe', boya: '🎨 Boya', elektrik: '⚡ Elektrik',
  tesisaat: '🚿 Tesisat', guvenlik: '🔐 Güvenlik', klima: '❄️ Klima', diger: '📦 Diğer'
};

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadContent();
  document.getElementById('gorevForm').addEventListener('submit', gorevOlustur);
});

async function loadStats() {
  try {
    const res = await fetch('/api/istatistik');
    const d = await res.json();
    animateCount('stat-uzman', d.uzmanSayisi);
    animateCount('stat-gorev', d.tamamlanan);
    document.getElementById('stat-puan').textContent = d.memnuniyet.toFixed(1) + ' ⭐';
  } catch(e) {}
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  let start = 0, duration = 1500;
  const step = (timestamp) => {
    if (!start) start = timestamp;
    const progress = Math.min((timestamp - start) / duration, 1);
    el.textContent = Math.floor(progress * target).toLocaleString('tr-TR') + '+';
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function showTab(tab) {
  aktifTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('tab-' + tab);
  if (btn) btn.classList.add('active');
  if (tab === 'nasil') {
    document.getElementById('nasil').scrollIntoView({ behavior: 'smooth' });
    return;
  }
  loadContent();
}

async function loadContent() {
  const kategori = document.getElementById('filterKategori').value;
  const sehir = document.getElementById('filterSehir').value;
  const arama = document.getElementById('filterArama')?.value || '';
  const area = document.getElementById('content-area');
  const loading = document.getElementById('loading');
  const bos = document.getElementById('bos-durum');

  area.innerHTML = ''; loading.style.display = 'block'; bos.style.display = 'none';

  try {
    if (aktifTab === 'uzmanlar') {
      const params = new URLSearchParams({ kategori, sehir, arama });
      const res = await fetch('/api/uzmanlar?' + params);
      const uzmanlar = await res.json();
      loading.style.display = 'none';
      if (!uzmanlar.length) { bos.style.display = 'block'; return; }
      area.innerHTML = uzmanlar.map(u => uzmanKarti(u)).join('');
    } else {
      const params = new URLSearchParams({ kategori, sehir });
      const res = await fetch('/api/gorevler?' + params);
      const gorevler = await res.json();
      loading.style.display = 'none';
      if (!gorevler.length) { bos.style.display = 'block'; return; }
      area.innerHTML = gorevler.map(g => gorevKarti(g)).join('');
    }
  } catch(e) {
    loading.style.display = 'none';
    area.innerHTML = '<p style="color:red;padding:20px">Veri yüklenemedi.</p>';
  }
}

function uzmanKarti(u) {
  const katAd = KATEGORI_ADLARI[u.kategori] || u.kategori;
  return `
  <div class="uzman-kart" onclick="uzmanDetay(${JSON.stringify(u).replace(/"/g,'&quot;')})">
    <div class="uk-header">
      <div class="uk-avatar">${u.avatar || u.ad[0]}</div>
      <div>
        <div class="uk-ad">${u.ad}</div>
        <div class="uk-sehir">📍 ${u.sehir}</div>
      </div>
    </div>
    <div class="uk-puan">
      <span class="puan-star">★</span>
      <span class="puan-val">${u.puan}</span>
      <span class="puan-cnt">(${u.isTamamlanan} iş tamamlandı)</span>
    </div>
    <div class="uk-aciklama">${u.aciklama}</div>
    <div class="uk-footer">
      <div class="uk-fiyat">₺${u.fiyat} <span>/ saat'ten</span></div>
      <div class="uk-badge">${katAd}</div>
    </div>
  </div>`;
}

function gorevKarti(g) {
  const katAd = KATEGORI_ADLARI[g.kategori] || g.kategori;
  return `
  <div class="gorev-kart">
    <div class="gk-baslik">${g.baslik}</div>
    <div class="gk-meta">
      <span class="gk-tag">${katAd}</span>
      <span class="gk-tag">📍 ${g.sehir}</span>
      <span class="gk-tag">📅 ${g.tarih}</span>
    </div>
    <div class="gk-aciklama">${g.aciklama}</div>
    <div class="gk-footer">
      <div class="gk-butce">₺${g.butce?.toLocaleString('tr-TR')}</div>
      <div class="gk-teklif">👥 ${g.teklifSayisi} teklif</div>
    </div>
  </div>`;
}

function uzmanDetay(u) {
  const katAd = KATEGORI_ADLARI[u.kategori] || u.kategori;
  document.getElementById('ud-ad').textContent = u.ad + ' — Profil';
  document.getElementById('uzman-detay-icerik').innerHTML = `
    <div class="ud-grid">
      <div class="ud-info">
        <div class="ud-ust">
          <div class="ud-avatar-lg">${u.avatar || u.ad[0]}</div>
          <div class="ud-meta">
            <div style="font-family:'Sora',sans-serif;font-weight:800;font-size:20px">${u.ad}</div>
            <div style="color:#888;font-size:14px">📍 ${u.sehir} · ${katAd}</div>
            <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
              <span style="color:#FFB300;font-size:16px">★</span>
              <span style="font-weight:700">${u.puan}</span>
              <span style="color:#888;font-size:13px">(${u.isTamamlanan} iş)</span>
            </div>
          </div>
        </div>
        <p style="font-size:15px;color:#555;line-height:1.6">${u.aciklama}</p>
        <div class="ud-istatler">
          <div class="ud-istat">
            <div class="ud-istat-val">${u.puan}</div>
            <div class="ud-istat-lbl">Ortalama Puan</div>
          </div>
          <div class="ud-istat">
            <div class="ud-istat-val">${u.isTamamlanan}</div>
            <div class="ud-istat-lbl">Tamamlanan İş</div>
          </div>
          <div class="ud-istat">
            <div class="ud-istat-val">₺${u.fiyat}</div>
            <div class="ud-istat-lbl">Saatlik Ücret</div>
          </div>
          <div class="ud-istat">
            <div class="ud-istat-val">${u.uygunluk ? '✅' : '❌'}</div>
            <div class="ud-istat-lbl">Müsaitlik</div>
          </div>
        </div>
      </div>
      <div class="teklif-form">
        <h4>Bu uzmana iş teklif edin</h4>
        <div class="form-group">
          <label>İş Başlığı</label>
          <input type="text" id="tf-baslik" placeholder="Ne yaptırmak istiyorsunuz?">
        </div>
        <div class="form-group">
          <label>Açıklama</label>
          <textarea id="tf-aciklama" rows="3" placeholder="İş detaylarını belirtin..."></textarea>
        </div>
        <div class="form-group">
          <label>Bütçe (₺)</label>
          <input type="number" id="tf-butce" placeholder="Tahmini bütçeniz">
        </div>
        <button class="btn-primary btn-full" onclick="teklifGonder('${u.id}', '${u.ad}')">
          Teklif Gönder →
        </button>
      </div>
    </div>`;
  showModal('uzmanDetay');
}

async function teklifGonder(uzmanId, uzmanAd) {
  const baslik = document.getElementById('tf-baslik').value;
  const aciklama = document.getElementById('tf-aciklama').value;
  const butce = document.getElementById('tf-butce').value;
  if (!baslik || !aciklama) { showToast('⚠️ Lütfen tüm alanları doldurun'); return; }
  try {
    await fetch('/api/teklif/ver', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ uzmanId, fiyat: butce, mesaj: baslik + ' - ' + aciklama })
    });
    closeModal('uzmanDetay');
    showToast('✅ Teklifiniz ' + uzmanAd + "'e gönderildi!");
  } catch(e) {
    showToast('❌ Hata oluştu, tekrar deneyin');
  }
}

async function gorevOlustur(e) {
  e.preventDefault();
  const body = {
    baslik: document.getElementById('g-baslik').value,
    kategori: document.getElementById('g-kategori').value,
    sehir: document.getElementById('g-sehir').value,
    butce: parseInt(document.getElementById('g-butce').value),
    aciklama: document.getElementById('g-aciklama').value,
    musteri: document.getElementById('g-musteri').value
  };
  if (!body.baslik || !body.aciklama) { showToast('⚠️ Lütfen tüm alanları doldurun'); return; }
  try {
    const res = await fetch('/api/gorev/olustur', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    await res.json();
    closeModal('gorevOlustur');
    showToast('🎉 İlanınız yayınlandı! Uzmanlar tekliflerini gönderecek.');
    e.target.reset();
    showTab('gorevler');
  } catch(err) {
    showToast('❌ Hata oluştu');
  }
}

function filterKategori(id) {
  document.querySelectorAll('.kategori-kart').forEach(k => {
    k.classList.toggle('aktif', k.dataset.id === id);
  });
  document.getElementById('filterKategori').value = id;
  document.getElementById('main-content').scrollIntoView({ behavior: 'smooth' });
  loadContent();
}

function heroAra() {
  const arama = document.getElementById('heroSearch').value;
  const sehir = document.getElementById('heroSehir').value;
  if (arama) document.getElementById('filterArama').value = arama;
  if (sehir) document.getElementById('filterSehir').value = sehir;
  document.getElementById('main-content').scrollIntoView({ behavior: 'smooth' });
  showTab('uzmanlar');
}

function showModal(id) {
  document.getElementById('modal-' + id).classList.add('open');
}
function closeModal(id) {
  document.getElementById('modal-' + id).classList.remove('open');
}

let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}
