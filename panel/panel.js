// Vellum — 1c "Tek Ağız".
// Arayüz bir gösterge tablosu değil, bir konuşma. Ajanlar görünmez; künye
// onların orada olduğunu söyler. Gösterge tablosu Defter görünümünde durur.

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz',
  'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const GUNLER = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];

let D = null;                 // /api/durum çıktısı
let gorunum = 'konusma';      // 'konusma' | 'defter'
let defterOdak = 'projeler';  // 'projeler' | 'ajanda' | 'arsiv' | 'posta' | 'mesaj'
let acikProje = null;
let etiketSuzgeci = null;
let sohbetGecmisi = [];
let taslakMetinleri = {};     // id -> taslak gövdesi (satır içi gösterim için)
let bekleyen = false;
let gecenSaniye = 0;
let taraniyor = false;
let hataMetni = null;

// ---------------------------------------------------------------- yardımcı

const kacir = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const ham = (m) => (m.ham_skor != null ? m.ham_skor : m.skor) || 0;

function tarih(iso) {
  const d = new Date(iso);
  return d.getDate() + ' ' + AYLAR[d.getMonth()].slice(0, 3);
}

function saat(iso) {
  const d = new Date(iso);
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

function gunFarki(iso) {
  const s = new Date(D.simdi), d = new Date(iso);
  return Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) -
    new Date(s.getFullYear(), s.getMonth(), s.getDate())) / 86400000);
}

function gunAdi(iso) {
  const f = gunFarki(iso);
  if (f === 0) return 'bugün';
  if (f === 1) return 'yarın';
  if (f === -1) return 'dün';
  return tarih(iso);
}

const kalanSaat = (iso) => Math.round((new Date(iso) - new Date(D.simdi)) / 3600000);

async function cagir(yol, govde) {
  const yanit = await fetch(yol, govde ? {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(govde)
  } : undefined);
  return yanit.json();
}

// Taslak dosyalarındaki YAML ön maddesini ve HTML yorumlarını ayıklar.
function taslakGovdesi(metin) {
  return String(metin || '')
    .replace(/^---[\s\S]*?---\n/, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .trim();
}

function kirp(metin, sinir) {
  const t = metin.replace(/\s+/g, ' ').trim();
  return t.length > sinir ? t.slice(0, sinir - 1).trimEnd() + '…' : t;
}

// ------------------------------------------------------------------ dialog

function modalAc(icerik) {
  document.getElementById('modal').innerHTML = icerik;
  document.getElementById('ortu').hidden = false;
}
function modalKapat() { document.getElementById('ortu').hidden = true; }

document.getElementById('ortu').addEventListener('click', (e) => {
  if (e.target.id === 'ortu') modalKapat();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modalKapat(); });

// ------------------------------------------------------------------ veriler

function bekleyenTaslaklar() {
  const liste = [];
  ((D.mail && D.mail.maddeler) || []).forEach(m => {
    if (m.durum === 'onay_bekliyor' && m.taslak) {
      liste.push({
        id: 'mail-' + m.id,
        kim: (m.gonderen || '').split('<')[0].trim(),
        konu: m.konu,
        acil: null,
        sira: -ham(m)
      });
    }
  });
  ((D.sosyal && D.sosyal.konusmalar) || []).forEach(k => {
    if (k.durum === 'onay_bekliyor' && k.taslak) {
      const kalan = kalanSaat(k.pencere_kapanis);
      liste.push({
        id: 'ig-' + k.id,
        kim: k.kisi,
        konu: k.ozet,
        acil: kalan > 0 ? (kalan < 12 ? 'cevap penceresi ' + kalan + ' saat sonra kapanıyor' : null)
                        : 'cevap penceresi kapandı',
        // Kapanmış pencere en aciliymiş gibi değil, en sonda durur: artık
        // cevaplanamıyor. Açık olanlarda az kalan önce gelir.
        sira: kalan > 0 ? kalan : 10000
      });
    }
  });
  return liste.sort((a, b) => a.sira - b.sira);
}

function acilMailler() {
  return ((D.mail && D.mail.maddeler) || [])
    .filter(m => ham(m) >= 70)
    .sort((a, b) => ham(b) - ham(a));
}

function bugununEtkinlikleri() {
  return ((D.ajanda && D.ajanda.etkinlikler) || [])
    .filter(e => gunFarki(e.baslangic) === 0)
    .sort((a, b) => a.baslangic.localeCompare(b.baslangic));
}

function sessizProjeler() {
  return (D.projeler || []).filter(p => {
    const sh = p.durum && p.durum.son_hareket;
    return sh && (new Date(D.simdi) - new Date(sh)) / 86400000 >= 14;
  });
}

// ------------------------------------------------------------------- künye

function cizKunye() {
  const mailler = (D.mail && D.mail.maddeler) || [];
  const konusmalar = (D.sosyal && D.sosyal.konusmalar) || [];
  const etkinlikler = (D.ajanda && D.ajanda.etkinlikler) || [];
  const onemliPosta = mailler.filter(m => ham(m) >= 40).length;

  let s = '<div class="marka"><span class="mim">V</span><span class="ad">Vellum</span></div>';

  s += '<div class="gizle-mobil"><div class="kunye-baslik">Künye</div><div class="kunye-grup">' +
    ajanSatiri('posta', 'n-mavi', 'Posta', onemliPosta) +
    ajanSatiri('mesaj', 'n-mavi', 'Mesaj', konusmalar.length) +
    ajanSatiri('ajanda', 'n-sari', 'Ajanda', etkinlikler.length) +
    '</div></div>';

  const bugun = bugununEtkinlikleri();
  s += '<div class="gizle-mobil"><div class="kunye-baslik">Bugün</div><div class="bugun">';
  if (bugun.length) {
    bugun.forEach(e => {
      const gecti = new Date(e.baslangic) < new Date(D.simdi);
      s += '<span class="' + (gecti ? 'gecti' : '') + '">' +
        '<b class="sa">' + saat(e.baslangic) + '</b> ' + kacir(e.baslik) + '</span>';
    });
  } else {
    s += '<span class="gecti">Bugün için kayıt yok.</span>';
  }
  s += '</div></div>';

  const okunan = (D.mail && D.mail.toplam_okunmamis || 0) +
    konusmalar.length + (D.sosyal && D.sosyal.elenen_spam || 0);
  const getirilen = acilMailler().length + bekleyenTaslaklar().length;
  s += '<div class="kunye-alt">Vellum son taramada ' + okunan + ' kayıt okudu, ' +
    getirilen + '’ini size getirdi.' +
    '<button class="geri defter" onclick="defterAc(\'projeler\')">Defteri aç →</button></div>';

  document.getElementById('kunye').innerHTML = s;
}

function ajanSatiri(hedef, nokta, ad, sayi) {
  return '<button class="ajan" onclick="defterAc(\'' + hedef + '\')">' +
    '<span class="nokta ' + nokta + '"></span>' + ad +
    '<span class="sayi">' + sayi + '</span></button>';
}

// ---------------------------------------------------------------- konuşma

function cizKonusma() {
  const simdi = new Date(D.simdi);
  const selam = simdi.getHours() < 11 ? 'Günaydın'
    : simdi.getHours() < 18 ? 'Merhaba' : 'İyi akşamlar';

  let s = '<div class="akis">';
  s += '<div class="zaman-etiketi"><span>' + GUNLER[simdi.getDay()] + ' ' + saat(D.simdi) +
    '</span><button class="geri" onclick="tara()"' + (taraniyor ? ' disabled' : '') + '>' +
    (taraniyor ? 'taranıyor…' : 'şimdi tara') + '</button></div>';

  if (hataMetni) { s += '<div class="hata">' + kacir(hataMetni) + '</div>'; hataMetni = null; }

  // Günün cümlesi: brifing varsa konuşmanın açılışı olur.
  if (D.bugunun_brifingi) {
    s += brifingiCiz(D.bugunun_brifingi);
  } else {
    s += '<p class="gun-cumlesi">' + selam + '. Bugün için henüz tarama yapılmadı.</p>' +
      '<p class="ses">Postayı, mesajları ve ajandayı taramamı istersen yukarıdaki ' +
      '“şimdi tara”ya bas — dört ajan çalışır, günün özetini buraya yazarım.</p>';
  }

  s += onaylariCiz();

  sohbetGecmisi.forEach(t => {
    s += t.rol === 'kullanici'
      ? '<p class="ben">' + kacir(t.metin) + '</p>'
      : '<p class="ses">' + kacir(t.metin) + '</p>';
  });
  if (bekleyen) {
    s += '<p class="ses dusunuyor">Düşünüyor… ' + gecenSaniye + ' sn</p>';
  }

  s += '</div>';

  s += '<div class="besteci"><div class="besteci-ic">' +
    '<input type="text" id="soru" placeholder="Vellum’a yazın…"' +
    (bekleyen ? ' disabled' : '') + ' onkeydown="if(event.key===\'Enter\')sor()">' +
    '<button class="btn btn-primary" onclick="sor()"' + (bekleyen ? ' disabled' : '') +
    '>Söyle</button></div>';
  if (!D.canli_gonderim) {
    s += '<p class="kapali-not">Canlı gönderim kapalı — onaylar yalnızca kaydediliyor, ' +
      'hiçbir yere mail veya mesaj gitmiyor.</p>';
  }
  s += '</div>';

  return s;
}

// Brifing markdown'ının ilk paragrafı gün cümlesi, gerisi kâtibin sesi.
function brifingiCiz(metin) {
  const satirlar = String(metin).split('\n')
    .map(x => x.replace(/^#+\s*/, '').replace(/\*\*/g, '').trim())
    .filter(x => x && !/^ONAY BEKLEYEN|^PROJE GEÇMİŞİNE|^SİSTEM NOTU/i.test(x));

  const govde = [];
  let ilk = '';
  satirlar.forEach(x => {
    if (!ilk && x.length > 20 && !/^\d+\s|^[-·]/.test(x)) { ilk = x; return; }
    govde.push(x.replace(/^[-·]\s*/, '• '));
  });
  if (!ilk) ilk = satirlar[0] || '';

  return '<p class="gun-cumlesi">' + kacir(ilk) + '</p>' +
    (govde.length ? '<p class="ses">' + kacir(govde.join('\n')) + '</p>' : '');
}

function onaylariCiz() {
  const liste = bekleyenTaslaklar();
  if (!liste.length) return '';

  let s = '<div class="onaylar"><div class="onaylar-baslik">Onayınızı bekleyen ' +
    liste.length + ' şey</div>';
  liste.forEach(t => {
    const govde = taslakMetinleri[t.id] || '';
    const ozet = govde ? kirp(govde, 150) : kirp(t.konu || '', 150);
    s += '<div class="onay-satir"><span class="onay-metin">' +
      '<span class="kaynak">' + kacir(t.kim) + '</span> — ' + kacir(ozet) +
      (t.acil ? ' <span class="acil">(' + kacir(t.acil) + ')</span>' : '') +
      '</span><span class="onay-dugmeler">' +
      '<button class="btn btn-primary" onclick="taslakOnayla(\'' + kacir(t.id) + '\')">Onayla</button>' +
      '<button class="btn btn-ghost" onclick="taslakAc(\'' + kacir(t.id) + '\',\'' +
      kacir(t.kim) + '\')">Değiştir</button></span></div>';
  });
  return s + '</div>';
}

// -------------------------------------------------------------------- defter

function cizDefter() {
  let s = '<div class="akis"><div class="defter-ust">' +
    '<h1>' + kacir(defterBasligi()) + '</h1>' +
    '<button class="geri" onclick="konusmayaDon()">← Konuşmaya dön</button></div>';

  if (hataMetni) { s += '<div class="hata">' + kacir(hataMetni) + '</div>'; hataMetni = null; }

  if (defterOdak === 'projeler') s += defterProjeler();
  else if (defterOdak === 'ajanda') s += defterAjanda();
  else if (defterOdak === 'arsiv') s += defterArsiv();
  else if (defterOdak === 'posta') s += defterPosta();
  else if (defterOdak === 'mesaj') s += defterMesaj();

  s += '<div class="etiketler" style="margin-top:30px">' +
    ['projeler', 'posta', 'mesaj', 'ajanda', 'arsiv'].map(x =>
      '<button class="etiket' + (defterOdak === x ? ' etkin' : '') +
      '" onclick="defterAc(\'' + x + '\')">' + defterBasligi(x) + '</button>').join('') +
    '</div>';

  return s + '</div>';
}

function defterBasligi(hangi) {
  const ad = { projeler: 'Projeler', ajanda: 'Ajanda', arsiv: 'Arşiv', posta: 'Posta', mesaj: 'Mesaj' };
  return ad[hangi || defterOdak] || 'Defter';
}

function defterProjeler() {
  const projeler = D.projeler || [];
  if (!projeler.length) return '<p class="bos">Kayıtlı proje yok.</p>';

  let s = '';
  projeler.forEach(p => {
    const d = p.durum || {};
    const acik = acikProje === p.ad;
    const maks = Math.max(1, ...(d.aktivite_12h || [0]));
    const serit = (d.aktivite_12h || []).map((v, i) =>
      '<i class="' + (i >= 10 && v ? 'son' : '') + '" style="height:' +
      Math.round((v / maks) * 100) + '%"></i>').join('');
    const sessizGun = d.son_hareket
      ? Math.floor((new Date(D.simdi) - new Date(d.son_hareket)) / 86400000) : null;

    s += '<div class="proje"><div class="proje-ust">' +
      '<button class="proje-ad" onclick="projeAc(\'' + kacir(p.ad) + '\')">' +
      kacir(p.ad) + '</button><span class="rozet' + (d.acik_blokajlar ? ' uyari' : '') + '">' +
      (d.acik_blokajlar ? d.acik_blokajlar + ' blokaj' : (d.olay_sayisi || 0) + ' olay') +
      (sessizGun >= 14 ? ' · ' + sessizGun + ' gündür sessiz' : '') +
      (p.bekleyen_olay ? ' · ' + p.bekleyen_olay + ' olay onay bekliyor' : '') +
      '</span></div>' +
      '<p class="proje-ozet">' + kacir(d.ozet || '') +
      (d.ozet_bayat ? ' <span class="vurgu">(özet güncellenmeli)</span>' : '') + '</p>' +
      '<div class="serit">' + serit + '</div>' +
      (acik ? cizelge(p) : '') + '</div>';
  });
  return s;
}

function cizelge(p) {
  let olaylar = p.olaylar || [];
  if (etiketSuzgeci) olaylar = olaylar.filter(o => (o.etiket || []).includes(etiketSuzgeci));

  const etiketler = (p.durum && p.durum.etiketler) || [];
  let s = '<div class="cizelge">';
  if (etiketler.length) {
    s += '<div class="etiketler" style="margin:0 0 12px">' +
      '<button class="etiket' + (etiketSuzgeci ? '' : ' etkin') +
      '" onclick="suz(null)">tümü</button>' +
      etiketler.map(e => '<button class="etiket' + (etiketSuzgeci === e ? ' etkin' : '') +
        '" onclick="suz(\'' + kacir(e) + '\')">' + kacir(e) + '</button>').join('') +
      '</div>';
  }

  let sonAy = null;
  olaylar.forEach(o => {
    const d = new Date(o.t);
    const ay = AYLAR[d.getMonth()] + ' ' + d.getFullYear();
    if (ay !== sonAy) { s += '<div class="ay">' + ay + '</div>'; sonAy = ay; }

    const sinif = o.onaylanmamis ? 'bekleyen'
      : o.kilometre_tasi ? 'kt'
      : o.tip === 'blokaj' ? 'blokaj'
      : ['blokaj_cozuldu', 'adim_tamamlandi', 'teslim'].includes(o.tip) ? 'cozum' : '';

    s += '<div class="olay ' + sinif + '">' +
      '<div class="olay-baslik">' + kacir(o.baslik) + '</div>' +
      '<div class="olay-meta">' + tarih(o.t) +
      (o.detay ? ' · ' + kacir(o.detay) : '') +
      (o.kaynak ? ' · <span class="kaynak">' + kacir(o.kaynak) + '</span>' : '') +
      (o.kilometre_tasi ? ' · kilometre taşı' : '') +
      (o.onaylanmamis ? ' · onay bekliyor' : '') + '</div>' +
      (o.onaylanmamis ? '<div class="olay-kararlar">' +
        '<button class="btn btn-secondary" onclick="olayKarari(\'' + kacir(p.ad) + '\',\'' +
        kacir(o.t) + '\',\'onayla\')">Geçmişe ekle</button>' +
        '<button class="btn btn-ghost" onclick="olayKarari(\'' + kacir(p.ad) + '\',\'' +
        kacir(o.t) + '\',\'yoksay\')">Yoksay</button></div>' : '') +
      '</div>';
  });
  if (!olaylar.length) s += '<p class="bos">Bu etikette olay yok.</p>';
  return s + '</div>';
}

function defterPosta() {
  const mailler = ((D.mail && D.mail.maddeler) || []).slice().sort((a, b) => ham(b) - ham(a));
  const dusuk = mailler.filter(m => ham(m) < 40).length;
  const gosterilecek = mailler.filter(m => ham(m) >= 40);
  if (!gosterilecek.length) return '<p class="bos">Öne çıkan mail yok.</p>';

  let s = '<div class="liste">';
  gosterilecek.forEach(m => {
    s += '<div class="liste-satir"><div class="govde">' +
      '<p>' + kacir(m.ozet) + '</p>' +
      '<p class="alt">' + kacir((m.gonderen || '').split('<')[0].trim()) +
      (m.aksiyon ? ' · ' + kacir(m.aksiyon) : '') +
      (m.proje ? ' · ' + kacir(m.proje) : '') + '</p></div>' +
      '<span class="rozet">' + ham(m) + '</span></div>';
  });
  s += '</div>';
  if (dusuk) s += '<p class="bos" style="margin-top:16px">' + dusuk +
    ' düşük öncelikli mail dokunulmadan bırakıldı.</p>';
  return s;
}

function defterMesaj() {
  const k = (D.sosyal && D.sosyal.konusmalar) || [];
  if (!k.length) return '<p class="bos">Konuşma yok.</p>';
  let s = '<div class="liste">';
  k.forEach(x => {
    const kalan = kalanSaat(x.pencere_kapanis);
    s += '<div class="liste-satir"><div class="govde">' +
      '<p>' + kacir(x.kisi) + ' — ' + kacir(x.ozet) + '</p>' +
      '<p class="alt' + (kalan > 0 && kalan < 12 ? ' vurgu' : '') + '">' +
      (kalan > 0 ? 'cevap penceresi ' + kalan + ' saat sonra kapanıyor'
                 : 'cevap penceresi kapandı') + '</p></div></div>';
  });
  s += '</div>';
  const spam = (D.sosyal && D.sosyal.elenen_spam) || 0;
  if (spam) s += '<p class="bos" style="margin-top:16px">' + spam + ' spam elendi.</p>';
  return s;
}

function defterAjanda() {
  const e = (D.ajanda && D.ajanda.etkinlikler) || [];
  const yok = (D.ajanda && D.ajanda.takvimde_yok) || [];
  if (!e.length && !yok.length) return '<p class="bos">Ajanda boş.</p>';

  let s = '<div class="liste">';
  e.forEach(x => {
    const hazir = (x.hazirlik || []).filter(h => h.durum === 'bekliyor');
    s += '<div class="liste-satir"><div class="govde">' +
      '<p>' + gunAdi(x.baslangic) + ' ' + saat(x.baslangic) + ' — ' + kacir(x.baslik) + '</p>' +
      (x.ana_konu ? '<p class="alt">' + kacir(x.ana_konu) + '</p>' : '') +
      (hazir.length ? '<p class="alt">Öncesinde: ' +
        hazir.map(h => kacir(h.madde)).join(' · ') + '</p>' : '') +
      '</div></div>';
  });
  s += '</div>';

  if (yok.length) {
    s += '<div class="ay">Takvimde yok</div><div class="liste">';
    yok.forEach(x => {
      s += '<div class="liste-satir"><div class="govde"><p>' + kacir(x.ozet) + ' — ' +
        gunAdi(x.onerilen_zaman) + ' ' + saat(x.onerilen_zaman) + '</p>' +
        '<p class="alt kaynak">' + kacir(x.kaynak) + '</p></div></div>';
    });
    s += '</div>';
  }
  return s;
}

function defterArsiv() {
  const a = D.arsiv || [];
  if (!a.length) return '<p class="bos">Arşivde kayıt yok.</p>';
  let s = '<div class="liste">';
  a.forEach(ad => {
    s += '<div class="liste-satir"><div class="govde"><p>' +
      kacir(ad.replace('.md', '')) + '</p></div>' +
      '<button class="btn btn-ghost" onclick="arsivAc(\'' + kacir(ad) + '\')">Aç</button></div>';
  });
  return s + '</div>';
}

// ------------------------------------------------------------------ eylemler

async function taslakAc(id, kime) {
  const r = await cagir('/api/taslak/' + encodeURIComponent(id));
  if (r.hata) {
    return modalAc('<h3 class="dialog-title">Taslak açılamadı</h3>' +
      '<p class="dialog-body">' + kacir(r.hata) + '</p>' +
      '<div class="dialog-actions"><button class="btn btn-secondary" onclick="modalKapat()">Kapat</button></div>');
  }
  modalAc('<h3 class="dialog-title">' + kacir(kime) + '</h3>' +
    '<pre>' + kacir(taslakGovdesi(r.metin)) + '</pre>' +
    (D.canli_gonderim ? '' :
      '<p class="dialog-body">Gmail bağlı değil — onayladığında taslak onaylandı olarak ' +
      'işaretlenir, hiçbir yere gönderilmez.</p>') +
    '<div class="dialog-actions">' +
    '<button class="btn btn-secondary" onclick="modalKapat()">Kapat</button>' +
    '<button class="btn btn-primary" onclick="modalKapat();taslakOnayla(\'' +
    kacir(id) + '\')">Onayla</button></div>');
}

async function taslakOnayla(id) {
  const r = await cagir('/api/onay', { id: id });
  if (r.hata) hataMetni = r.hata;
  else sohbetGecmisi.push({ rol: 'asistan', metin: r.mesaj || 'Onaylandı.' });
  await yenile();
}

async function olayKarari(proje, t, karar) {
  const r = await cagir('/api/olay', { proje: proje, t: t, karar: karar });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function arsivAc(ad) {
  const r = await cagir('/api/arsiv/' + encodeURIComponent(ad));
  modalAc('<h3 class="dialog-title">' + kacir(ad.replace('.md', '')) + '</h3>' +
    '<pre>' + kacir(r.metin || r.hata) + '</pre>' +
    '<div class="dialog-actions"><button class="btn btn-secondary" onclick="modalKapat()">Kapat</button></div>');
}

async function sor() {
  const kutu = document.getElementById('soru');
  if (!kutu || bekleyen) return;
  const soru = kutu.value.trim();
  if (!soru) return;

  const gecmis = sohbetGecmisi.slice();
  sohbetGecmisi.push({ rol: 'kullanici', metin: soru });
  bekleyen = true;
  gecenSaniye = 0;
  ciz();
  odaklan();

  // Tüm paneli saniyede bir çizmek titremeye yol açıyor; yalnız bu düğüm güncellenir.
  const sayac = setInterval(() => {
    gecenSaniye += 1;
    const d = document.querySelector('.dusunuyor');
    if (d) d.textContent = 'Düşünüyor… ' + gecenSaniye + ' sn';
  }, 1000);

  let r;
  try {
    r = await cagir('/api/sohbet', { soru: soru, gecmis: gecmis });
  } catch (e) {
    r = { hata: 'Sunucuya ulaşılamadı: ' + e.message };
  }
  clearInterval(sayac);
  bekleyen = false;
  sohbetGecmisi.push({
    rol: 'asistan',
    metin: r.cevap || ('Olmadı: ' + (r.hata || 'bilinmeyen hata'))
  });
  ciz();
  odaklan();
}

async function tara() {
  if (taraniyor) return;
  taraniyor = true;
  ciz();
  const r = await cagir('/api/tarama', {});
  taraniyor = false;
  if (r.hata) hataMetni = r.hata;
  await yenile();
}

function odaklan() {
  const kutu = document.getElementById('soru');
  if (kutu && !bekleyen) kutu.focus();
  const son = document.querySelector('.akis > :last-child');
  if (son) son.scrollIntoView({ block: 'nearest' });
}

// -------------------------------------------------------------------- kabuk

function defterAc(hangi) {
  gorunum = 'defter';
  defterOdak = hangi;
  acikProje = null;
  etiketSuzgeci = null;
  ciz();
  window.scrollTo(0, 0);
}

function konusmayaDon() { gorunum = 'konusma'; ciz(); odaklan(); }
function projeAc(ad) { acikProje = acikProje === ad ? null : ad; etiketSuzgeci = null; ciz(); }
function suz(e) { etiketSuzgeci = e; ciz(); }

function ciz() {
  cizKunye();
  document.getElementById('sutun').innerHTML =
    gorunum === 'defter' ? cizDefter() : cizKonusma();
}

// Onay satırında taslak metnini gösterebilmek için gövdelerini önden okur.
async function taslaklariGetir() {
  const isler = bekleyenTaslaklar()
    .filter(t => !(t.id in taslakMetinleri))
    .map(async t => {
      try {
        const r = await cagir('/api/taslak/' + encodeURIComponent(t.id));
        taslakMetinleri[t.id] = r.metin ? taslakGovdesi(r.metin) : '';
      } catch (e) {
        taslakMetinleri[t.id] = '';
      }
    });
  if (isler.length) await Promise.all(isler);
}

async function yenile() {
  D = await cagir('/api/durum');
  ciz();
  await taslaklariGetir();
  ciz();
  odaklan();
}

yenile();
