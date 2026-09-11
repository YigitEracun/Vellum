// Vellum — 1c "Tek Ağız".
// Arayüz bir gösterge tablosu değil, bir konuşma. Ajanlar görünmez; künye
// onların orada olduğunu söyler. Gösterge tablosu Defter görünümünde durur.

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz',
  'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const GUNLER = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];

let D = null;                 // /api/durum çıktısı
// Tek ana ekran var: sesli mod. Yazılı sohbet sayfası kaldırıldı — aynı
// konuşmayı iki yerde göstermek ikisini de yarım bırakıyordu. Geçmiş turlar
// Defter'in Sohbet sekmesinde duruyor.
let gorunum = 'ses';          // 'ses' | 'defter'
let defterOdak = 'projeler';  // 'projeler' | 'takvim' | 'konular' | 'hafiza' | 'posta' | 'mesaj' | 'sohbet' | 'arsiv'
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

// Künyedeki "Bugün" bloğu Takvim'den beslenir. Eskiden ayrı bir Ajanda
// kaynağına bakıyordu; o sayfa kaldırıldı, tek takvim kaldı.
function bugununEtkinlikleri() {
  return (D.takvim || [])
    .filter(e => e.baslangic && gunFarki(e.baslangic) === 0)
    .sort((a, b) => a.baslangic.localeCompare(b.baslangic));
}

function hafizaSayisi() {
  return (D.hafiza || []).reduce((n, g) => n + g.olgular.length, 0);
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
  const onemliPosta = mailler.filter(m => ham(m) >= 40).length;

  let s = '<div class="marka"><span class="mim">V</span><span class="ad">Vellum</span></div>';

  // Künye: üç toplayıcı ajan. Nokta "bu ajan orada" demek, o yüzden yalnızca
  // ajanlarda var. Defter'in ajan olmayan sayfaları altta ayrı grupta durur.
  s += '<div class="gizle-mobil gezinme"><div class="kunye-baslik">Künye</div><div class="kunye-grup">' +
    ajanSatiri('posta', 'n-mavi', 'Posta', onemliPosta) +
    ajanSatiri('mesaj', 'n-mavi', 'Mesaj', konusmalar.length) +
    '<button class="ajan' + (gorunum === 'ses' ? ' etkin' : '') +
    '" onclick="sesliModaGec()">' +
    '<span class="nokta n-yok"></span>Sesli mod<span class="sayi">🎙</span></button>' +
    '</div></div>';

  const bekleyenEtkinlik = (D.takvim || []).filter(e =>
    (e.baslangic || '') >= D.simdi.slice(0, 10)).length;
  s += '<div class="gizle-mobil gezinme"><div class="kunye-baslik">Defter</div><div class="kunye-grup">' +
    ajanSatiri('projeler', null, 'Projeler', (D.projeler || []).length) +
    ajanSatiri('takvim', null, 'Takvim', bekleyenEtkinlik) +
    ajanSatiri('konular', null, 'Konular',
      ((D.konular && D.konular.kendi) || []).length) +
    ajanSatiri('hafiza', null, 'Hafıza', hafizaSayisi()) +
    ajanSatiri('sohbet', null, 'Sohbet', sohbetGecmisi.length) +
    ajanSatiri('arsiv', null, 'Arşiv', (D.arsiv || []).length) +
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
    (gorunum === 'defter'
      ? '<button class="geri defter" onclick="sesliModaGec()">← Vellum’a dön</button>'
      : '<button class="geri defter" onclick="defterAc(\'projeler\')">Defteri aç →</button>') +
    '</div>';

  document.getElementById('kunye').innerHTML = s;
}

// `nokta` yoksa yerine görünmez bir dolgu konur: noktasız satırların metni de
// noktalılarla aynı hizada başlar.
function ajanSatiri(hedef, nokta, ad, sayi) {
  const etkin = gorunum === 'defter' && defterOdak === hedef;
  return '<button class="ajan' + (etkin ? ' etkin' : '') +
    '" onclick="defterAc(\'' + hedef + '\')">' +
    '<span class="nokta ' + (nokta || 'n-yok') + '"></span>' + ad +
    '<span class="sayi">' + sayi + '</span></button>';
}

// Canlı izleyicinin gün içinde yakaladığı mailler. Kural motoru puanladı, model
// çalışmadı — özet istendiğinde üretilir, kredi ancak o zaman harcanır.
function bildirimleriCiz() {
  const liste = D.bildirimler || [];
  if (!liste.length) return '';
  const satirlar = liste.map(b =>
    '<p class="bildirim">' +
      '<span class="skor">' + (b.ham_skor || 0) + '</span> ' +
      '<b>' + kacir(kisalt(b.gonderen, 34)) + '</b> — ' + kacir(b.konu || '') +
      ' <button class="baglanti" onclick="bildirimOzeti(\'' + kacir(b.id) + '\')">özetle</button>' +
    '</p>').join('');
  return '<div class="bildirim-kutusu">' +
    '<p class="bildirim-baslik">Gün içinde ' + liste.length + ' önemli mail</p>' +
    satirlar + '</div>';
}

function kisalt(metin, n) {
  metin = String(metin || '');
  return metin.length > n ? metin.slice(0, n - 1) + '…' : metin;
}

// Özet istemek Çekirdek'e bir soru sormaktır: kredi burada, sizin isteğinizle harcanır.
function bildirimOzeti(id) {
  const b = (D.bildirimler || []).find(x => String(x.id) === String(id));
  if (!b) return;
  const istek = '"' + (b.konu || '') + '" konulu maili özetle ve ne yapmam ' +
    'gerektiğini söyle (id: ' + b.id + ').';
  // Sesli moddaki şeritten de tıklanabiliyor; orada yazı kutusu yerine
  // doğrudan sesli akışa verilir, cevap sesli gelir.
  if (gorunum === 'ses') return Ses.gonder(istek);
  const kutu = document.getElementById('soru');
  if (kutu) kutu.value = istek;
  sor();
}

// Süren taramanın canlı hâli. Durum sunucudan geldiği için sayfa yenilense de,
// başka bir sekmeden bakılsa da görünür.
function taramaCiz() {
  const t = D.tarama;
  if (!t || !t.suruyor) return '';
  const gecen = Math.max(0, Math.round((new Date() - new Date(t.baslangic)) / 1000));
  const adimlar = (t.adimlar || []).map(x => '<span class="adim">' + kacir(x) + '</span>').join('');
  return '<div class="tarama-canli">' +
    '<p class="tarama-baslik">Tarama sürüyor — <span class="sure">' + gecen + ' sn</span></p>' +
    (adimlar ? '<div class="adimlar">' + adimlar + '</div>' : '') +
    '</div>';
}

// Tarama sürerken sunucuyu yokla. Tüm paneli saniyede bir çizmek titriyor:
// sayaç her saniye tek düğümde güncellenir, durum birkaç saniyede bir çekilir.
let nabiz = null;
function nabziBaslat() {
  if (nabiz) return;
  let sayac = 0;
  nabiz = setInterval(async () => {
    // Süre daima başlangıç damgasından hesaplanır; sayfa sonradan açılsa da doğru.
    const d = document.querySelector('.tarama-canli .sure');
    if (d && D.tarama && D.tarama.baslangic) {
      d.textContent = Math.round((new Date() - new Date(D.tarama.baslangic)) / 1000) + ' sn';
    }
    if (++sayac % 3) return;                  // 3 saniyede bir sunucuya sor
    const yeni = await cagir('/api/durum').catch(() => null);
    if (!yeni) return;
    const bitti = !yeni.tarama || !yeni.tarama.suruyor;
    D = yeni;
    if (bitti) { nabziDurdur(); await yenile(); } else { ciz(); }
  }, 1000);
}
function nabziDurdur() { clearInterval(nabiz); nabiz = null; }

// Brifingin ne zaman üretildiği. Ham veri brifingten yeniyse brifing bayattır:
// o zamandan beri yeni mail gelmiş ama özet onu görmemiş demektir.
function brifingDamgasi() {
  if (!D.brifing_zamani) return '';
  const bayat = D.ham_cekildi && new Date(D.ham_cekildi) > new Date(D.brifing_zamani);
  return '<p class="brifing-damga">' + saat(D.brifing_zamani) + ' brifingi' +
    (bayat ? ' <span class="bayat">· veri ' + saat(D.ham_cekildi) +
      '\'te tazelendi, bu özet onu görmedi</span>' : '') + '</p>';
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
    '<button class="geri" onclick="sesliModaGec()">← Vellum’a dön</button></div>';

  if (hataMetni) { s += '<div class="hata">' + kacir(hataMetni) + '</div>'; hataMetni = null; }

  if (defterOdak === 'projeler') s += defterProjeler();
  else if (defterOdak === 'arsiv') s += defterArsiv();
  else if (defterOdak === 'posta') s += defterPosta();
  else if (defterOdak === 'mesaj') s += defterMesaj();
  else if (defterOdak === 'takvim') s += defterTakvim();
  else if (defterOdak === 'konular') s += defterKonular();
  else if (defterOdak === 'hafiza') s += defterHafiza();
  else if (defterOdak === 'sohbet') s += defterSohbet();

  // Gezinme künyeye taşındı; alttaki etiket şeridi kaldırıldı.
  return s + '</div>';
}

function defterBasligi(hangi) {
  const ad = { projeler: 'Projeler', takvim: 'Takvim', konular: 'Konular',
    arsiv: 'Arşiv', posta: 'Posta', mesaj: 'Mesaj', sohbet: 'Sohbet', hafiza: 'Hafıza' };
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

// Çekilen her mail listelenir — düşük skorlular da. Skor neyin öne çıkacağını
// belirler, neyin görüneceğini değil: elenen bir maili gözden geçirebilmek
// skorlamayı düzeltmenin tek yolu.
function defterPosta() {
  const mailler = ((D.mail && D.mail.maddeler) || []).slice().sort((a, b) => ham(b) - ham(a));
  if (!mailler.length) return '<p class="bos">Henüz mail çekilmedi.</p>';

  const onemli = mailler.filter(m => ham(m) >= 40);
  const dusuk = mailler.filter(m => ham(m) < 40);

  const satir = m =>
    '<div class="liste-satir okunur" onclick="mailAc(\'' + kacir(String(m.id)) + '\')">' +
      '<div class="govde">' +
        '<p>' + kacir(m.ozet || m.konu || '(konusuz)') + '</p>' +
        '<p class="alt">' + kacir((m.gonderen || '').split('<')[0].trim()) +
          (m.aksiyon ? ' · ' + kacir(m.aksiyon) : '') +
          (m.proje ? ' · ' + kacir(m.proje) : '') + '</p>' +
      '</div><span class="rozet">' + ham(m) + '</span></div>';

  let s = '';
  if (onemli.length) s += '<div class="liste">' + onemli.map(satir).join('') + '</div>';
  else s += '<p class="bos">Öne çıkan mail yok.</p>';

  if (dusuk.length) {
    s += '<p class="ayrac">' + dusuk.length + ' düşük öncelikli mail</p>' +
      '<div class="liste sonuk">' + dusuk.map(satir).join('') + '</div>';
  }
  return s;
}

// Mailin tam gövdesi. Ham veri sunucuda; pencereden düşmüşse arşivden gelir.
async function mailAc(id) {
  const r = await cagir('/api/mail/' + encodeURIComponent(id));
  if (r.hata) {
    return modalAc('<h3 class="dialog-title">Mail açılamadı</h3>' +
      '<p class="dialog-body">' + kacir(r.hata) + '</p>' +
      '<div class="dialog-actions"><button class="btn btn-secondary" onclick="modalKapat()">Kapat</button></div>');
  }
  const m = r.mail;
  const madde = ((D.mail && D.mail.maddeler) || []).find(x => String(x.id) === String(id)) || {};
  const kunye = [
    ['Kimden', m.gonderen], ['Kime', (m.alici || []).join(', ')],
    ['CC', (m.cc || []).join(', ')], ['Tarih', m.tarih ? gunAdi(m.tarih) + ' ' + saat(m.tarih) : ''],
    ['Ekler', (m.ekler || []).join(', ')],
    ['Skor', madde.ham_skor != null ? madde.ham_skor + '  ·  ' + (madde.sinyaller || []).join(', ') : ''],
  ].filter(x => x[1]).map(x =>
    '<p class="kunye-satir"><span>' + x[0] + '</span>' + kacir(String(x[1])) + '</p>').join('');

  modalAc('<h3 class="dialog-title">' + kacir(m.konu || '(konusuz)') + '</h3>' +
    '<div class="mail-kunye">' + kunye + '</div>' +
    '<pre class="mail-govde">' + kacir(m.govde || '(gövde boş)') + '</pre>' +
    '<div class="dialog-actions">' +
      '<button class="btn btn-secondary" onclick="modalKapat()">Kapat</button>' +
      '<button class="btn btn-primary" onclick="modalKapat();mailOzeti(\'' + kacir(String(id)) + '\')">Özetle</button>' +
    '</div>');
}

// Özet istemek Çekirdek'e soru sormaktır: kredi burada, sizin isteğinizle harcanır.
function mailOzeti(id) {
  const m = ((D.mail && D.mail.maddeler) || []).find(x => String(x.id) === String(id)) || {};
  const kutu = document.getElementById('soru');
  if (kutu) kutu.value = '"' + (m.konu || '') + '" konulu maili (id: ' + id +
    ') özetle ve ne yapmam gerektiğini söyle.';
  sor();
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

// ----------------------------------------------------------------- konular

// Ağırlık kullanıcıya sayı olarak sorulmaz. Değerler eşiklerden türetildi:
// taban puan 30, "bilgi" eşiği 40, "aksiyon" eşiği 70. Yani +45 tek başına bir
// maili brifingin başına çıkarır; +25 ancak size doğrudan yazılmışsa çıkarır.
const ONCELIKLER = [
  { deger: 45, ad: 'Çok önemli', not: 'tek başına brifingin başına çıkarır' },
  { deger: 25, ad: 'Önemli', not: 'size yazılmışsa öne çıkar' },
  { deger: 10, ad: 'Biraz önemli', not: 'sıralamada azıcık yukarı taşır' },
  { deger: -25, ad: 'Önemsiz', not: 'listenin altına iter' },
  { deger: -45, ad: 'Gürültü', not: 'brifinge hiç girmez' },
];

// Kayıtlı değer listede yoksa (elle girilmiş eski bir sayı) en yakınına yuvarlanır.
function oncelikAdi(deger) {
  let en = ONCELIKLER[0];
  for (const o of ONCELIKLER) {
    if (Math.abs(o.deger - deger) < Math.abs(en.deger - deger)) en = o;
  }
  return en.ad;
}

// Önem skorlamasının içerik sözlüğü. Ortak sözlük projeyle gelir ve salt
// okunurdur; kullanıcının kendi konuları yereldir ve git dışında durur.
function defterKonular() {
  const k = D.konular || { ortak: [], kendi: [] };
  let s = '<p class="ses">Vellum bir maili şu kelimelere bakarak öne çıkarır. ' +
    'Aşağıya kendi konularınızı ekleyin — bir firma adı, bir proje, bir kişi. ' +
    'Kendi konularınız bu bilgisayarda kalır, sürüm kontrolüne girmez.</p>';

  s += '<p class="ayrac">Kendi konularınız</p>';
  if (k.kendi.length) {
    s += '<div class="liste">';
    k.kendi.forEach(x => {
      s += '<div class="liste-satir"><div class="govde">' +
        '<p><b>' + kacir(x.kelime) + '</b> <span class="rozet-kucuk' +
        (x.agirlik < 0 ? ' dusuk' : '') + '">' + kacir(oncelikAdi(x.agirlik)) +
        '</span></p>' +
        '<p class="alt kaynak">' +
        (x.dokundu ? 'son taramada ' + x.dokundu + ' maile dokundu'
                   : 'son taramada hiçbir maile dokunmadı') + '</p></div>' +
        '<button class="baglanti" onclick="konuSil(\'' + kacir(x.kelime) + '\')">kaldır</button>' +
        '</div>';
    });
    s += '</div>';
  } else {
    s += '<p class="bos">Henüz kendi konunuz yok.</p>';
  }

  s += '<div class="etkinlik-form">' +
    '<input type="text" id="yeni-konu" placeholder="Kelime ya da kısa öbek" ' +
    'onkeydown="if(event.key===\'Enter\')konuEkle()">' +
    '<select id="yeni-oncelik">' +
    ONCELIKLER.map(o => '<option value="' + o.deger + '"' +
      (o.deger === 25 ? ' selected' : '') + '>' + o.ad + '</option>').join('') +
    '</select>' +
    '<button class="btn btn-primary" onclick="konuEkle()">Ekle</button></div>';
  s += '<p class="bos" style="margin-top:6px">' +
    ONCELIKLER.map(o => '<b>' + o.ad + '</b> — ' + o.not).join(' · ') + '</p>';
  s += '<p class="bos" style="margin-top:8px">Türkçe ekler kendiliğinden eşleşir: ' +
    '“fatura” yazmanız yeter, “faturanız” da yakalanır. Kısa kelimeler ' +
    'alakasız maillere yapışır — gövdeyi uzun tutun.</p>';

  // Kişi listeleri de kişisel veri: config/ değil, yerel dosyada durur.
  s += '<p class="ayrac">Kişiler</p>' +
    '<p class="bos">VIP listesindekilerden gelen her mail öne çıkar, ' +
    'gürültü listesindekiler geri düşer. ' +
    (k.yazistiklarim ? 'Ayrıca daha önce yazıştığınız <b>' + k.yazistiklarim +
      '</b> adres kendiliğinden öne alınıyor — VIP listesi boş olsa bile gerçek ' +
      'muhataplarınız kaybolmaz.' : '') + '</p>';

  const kisiListesi = (baslik, liste, sinif) => {
    let g = '<p class="ayrac-ince">' + baslik + '</p>';
    if (!liste.length) return g + '<p class="bos">Boş.</p>';
    g += '<div class="liste ' + (sinif || '') + '">';
    liste.forEach(a => {
      g += '<div class="liste-satir"><div class="govde"><p>' + kacir(a) + '</p></div>' +
        '<button class="baglanti" onclick="kisiSil(\'' + kacir(a) + '\')">kaldır</button></div>';
    });
    return g + '</div>';
  };
  s += kisiListesi('VIP', k.vip || []) +
       kisiListesi('Gürültü', k.gurultu || [], 'sonuk');

  s += '<div class="etkinlik-form">' +
    '<input type="text" id="yeni-kisi" placeholder="ornek@firma.com" ' +
    'onkeydown="if(event.key===\'Enter\')kisiEkle(\'vip\')">' +
    '<button class="btn btn-primary" onclick="kisiEkle(\'vip\')">VIP</button>' +
    '<button class="btn btn-secondary" onclick="kisiEkle(\'gurultu\')">Gürültü</button>' +
    '</div>';

  s += '<p class="ayrac">Ortak sözlük</p>' +
    '<p class="bos">Projeyle gelen varsayılan kategoriler. Kullanmadığınızı kapatın.</p>' +
    '<div class="liste">';
  k.ortak.forEach(x => {
    s += '<div class="liste-satir' + (x.kapali ? ' sonuk-satir' : '') + '"><div class="govde">' +
      '<p><b>' + kacir(x.kategori) + '</b> <span class="rozet-kucuk' +
      (x.agirlik < 0 ? ' dusuk' : '') + '">' + kacir(oncelikAdi(x.agirlik)) +
      '</span> · ' + x.govde_sayisi + ' kelime</p>' +
      '<p class="alt kaynak">' + kacir(x.ornekler.join(' · ')) + '…</p></div>' +
      '<button class="baglanti" onclick="kategoriDegistir(\'' + kacir(x.kategori) +
      '\',' + (x.kapali ? 'false' : 'true') + ')">' +
      (x.kapali ? 'aç' : 'kapat') + '</button></div>';
  });
  s += '</div>';
  return s;
}

async function konuEkle() {
  const kelime = (document.getElementById('yeni-konu') || {}).value || '';
  const agirlik = (document.getElementById('yeni-oncelik') || {}).value || '25';
  if (!kelime.trim()) return;
  const r = await cagir('/api/konu-ekle', { kelime: kelime.trim(), agirlik: Number(agirlik) });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function konuSil(kelime) {
  const r = await cagir('/api/konu-sil', { kelime: kelime });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function kisiEkle(liste) {
  const adres = (document.getElementById('yeni-kisi') || {}).value || '';
  if (!adres.trim()) return;
  const r = await cagir('/api/kisi-ekle', { adres: adres.trim(), liste: liste });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function kisiSil(adres) {
  const r = await cagir('/api/kisi-sil', { adres: adres });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function kategoriDegistir(kategori, kapat) {
  const r = await cagir('/api/kategori', { kategori: kategori, kapat: kapat });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

// ------------------------------------------------------------------ takvim

// Gösterilen ay ve açık gün; ciz() bunları okur.
let takvimAy = null;          // {yil, ay} — null ise bu ay
let acikGun = null;           // 'YYYY-AA-GG'

const gunAnahtari = (d) => d.getFullYear() + '-' +
  String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');

function takvimEtkinlikleri() {
  return (D.takvim || []).slice().sort((a, b) => a.baslangic.localeCompare(b.baslangic));
}

function gununEtkinlikleri(anahtar) {
  return takvimEtkinlikleri().filter(e => (e.baslangic || '').slice(0, 10) === anahtar);
}

function defterTakvim() {
  const bugunD = new Date(D.simdi);
  const yil = takvimAy ? takvimAy.yil : bugunD.getFullYear();
  const ay = takvimAy ? takvimAy.ay : bugunD.getMonth();

  // Pazartesi ile başlayan ızgara: JS'te 0 pazar, bizde 0 pazartesi olmalı.
  const ilk = new Date(yil, ay, 1);
  const dolgu = (ilk.getDay() + 6) % 7;
  const gunSayisi = new Date(yil, ay + 1, 0).getDate();
  const bugunAnahtar = gunAnahtari(bugunD);

  let s = '<div class="takvim-baslik">' +
    '<button class="geri" onclick="ayKaydir(-1)">‹</button>' +
    '<span class="takvim-ay">' + AYLAR[ay] + ' ' + yil + '</span>' +
    '<button class="geri" onclick="ayKaydir(0)">bugün</button>' +
    '<button class="geri" onclick="ayKaydir(1)">›</button></div>';

  s += '<div class="takvim">';
  ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].forEach(g => {
    s += '<div class="takvim-gunadi">' + g + '</div>';
  });
  for (let i = 0; i < dolgu; i++) s += '<div class="takvim-hucre bos-hucre"></div>';

  for (let g = 1; g <= gunSayisi; g++) {
    const anahtar = yil + '-' + String(ay + 1).padStart(2, '0') + '-' + String(g).padStart(2, '0');
    const liste = gununEtkinlikleri(anahtar);
    const sinif = ['takvim-hucre'];
    if (anahtar === bugunAnahtar) sinif.push('bugun');
    if (anahtar < bugunAnahtar) sinif.push('gecmis');
    if (anahtar === acikGun) sinif.push('acik');
    if (liste.length) sinif.push('dolu');

    s += '<div class="' + sinif.join(' ') + '" onclick="gunAc(\'' + anahtar + '\')">' +
      '<span class="takvim-gun">' + g + '</span>';
    liste.slice(0, 2).forEach(e => {
      s += '<span class="takvim-etkinlik">' +
        (e.saatli === false ? '' : '<b>' + saat(e.baslangic) + '</b> ') +
        kacir(kisalt(e.baslik, 18)) + '</span>';
    });
    if (liste.length > 2) {
      s += '<span class="takvim-daha">+' + (liste.length - 2) + ' daha</span>';
    }
    s += '</div>';
  }
  s += '</div>';

  s += gunPaneli(acikGun || bugunAnahtar);
  return s;
}

// Seçili günün etkinlikleri ve ekleme formu.
function gunPaneli(anahtar) {
  const liste = gununEtkinlikleri(anahtar);
  const [y, a, g] = anahtar.split('-');
  let s = '<div class="gun-paneli"><p class="ayrac">' +
    Number(g) + ' ' + AYLAR[Number(a) - 1] + ' ' + y + '</p>';

  if (liste.length) {
    s += '<div class="liste">';
    liste.forEach(e => {
      const kaynak = e.kaynak && e.kaynak.startsWith('mail:')
        ? 'mail ' + e.kaynak.slice(5) + '’den çıkarıldı' : 'elle eklendi';
      s += '<div class="liste-satir"><div class="govde">' +
        '<p>' + (e.saatli === false ? '<b>gün boyu</b> ' : '<b>' + saat(e.baslangic) + '</b> ') +
        kacir(e.baslik) + (e.yer ? ' · ' + kacir(e.yer) : '') + '</p>' +
        '<p class="alt kaynak">' + kacir(kaynak) +
        (e.tur && e.tur !== 'diger' ? ' · ' + kacir(e.tur) : '') + '</p></div>' +
        '<button class="baglanti" onclick="etkinlikKaldir(\'' + kacir(e.id) + '\')">kaldır</button>' +
        '</div>';
    });
    s += '</div>';
  } else {
    s += '<p class="bos">Bu güne kayıt yok.</p>';
  }

  s += '<div class="etkinlik-form">' +
    '<input type="text" id="yeni-baslik" placeholder="Ne var?" ' +
    'onkeydown="if(event.key===\'Enter\')etkinlikEkle(\'' + anahtar + '\')">' +
    '<input type="time" id="yeni-saat" value="09:00">' +
    '<button class="btn btn-primary" onclick="etkinlikEkle(\'' + anahtar + '\')">Ekle</button>' +
    '</div></div>';
  return s;
}

function ayKaydir(yon) {
  const b = new Date(D.simdi);
  if (yon === 0) { takvimAy = null; acikGun = gunAnahtari(b); return ciz(); }
  const yil = takvimAy ? takvimAy.yil : b.getFullYear();
  const ay = (takvimAy ? takvimAy.ay : b.getMonth()) + yon;
  const d = new Date(yil, ay, 1);
  takvimAy = { yil: d.getFullYear(), ay: d.getMonth() };
  ciz();
}

function gunAc(anahtar) { acikGun = anahtar; ciz(); }

async function etkinlikEkle(anahtar) {
  const baslik = (document.getElementById('yeni-baslik') || {}).value || '';
  const saatDegeri = (document.getElementById('yeni-saat') || {}).value || '09:00';
  if (!baslik.trim()) return;
  const r = await cagir('/api/etkinlik-ekle', {
    baslik: baslik.trim(),
    baslangic: anahtar + 'T' + saatDegeri + ':00+03:00',
    saatli: true, tur: 'diger'
  });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  acikGun = anahtar;
  await yenile();
}

async function etkinlikKaldir(id) {
  const r = await cagir('/api/etkinlik-iptal', { id: id });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

// Vellum'un kullanıcı hakkında öğrendikleri. Hiçbir ağırlık sessiz uygulanmaz:
// ne öğrendiği burada yazılı, mailin sinyal satırında da "hafiza:..." görünür.
function defterHafiza() {
  const gruplar = D.hafiza || [];
  let s = '<p class="ses">Vellum sizi kullandıkça tanıyor: konuşurken ' +
    'söyledikleriniz ve verinin kendisinden sayılanlar buraya düşüyor. ' +
    'Öğrendiği her şey maillerin önem sırasına da giriyor — yanlış olanı ' +
    'kaldırın, önemini değiştirmek isterseniz önceliğini seçin. ' +
    'Bu liste bu bilgisayarda kalır, sürüm kontrolüne girmez.</p>';

  if (!gruplar.length) {
    return s + '<p class="bos">Henüz bir şey öğrenilmedi. Sesli modda ' +
      'kendinizden söz edin — mesleğiniz, sık görüştüğünüz kişiler, ' +
      'ilgilendiğiniz konular — ya da bir tarama yapın.</p>';
  }

  gruplar.forEach(g => {
    s += '<p class="ayrac">' + kacir(g.baslik) + '</p><div class="liste">';
    g.olgular.forEach(o => {
      const ag = o.guncel_agirlik;
      s += '<div class="liste-satir"><div class="govde">' +
        '<p><b>' + kacir(o.anahtar) + '</b> ' +
        '<span class="rozet-kucuk' + (ag < 0 ? ' dusuk' : '') + '">' +
        kacir(oncelikAdi(ag)) + '</span></p>' +
        '<p class="alt kaynak">' + kacir(o.deger || '') + '</p>' +
        '<p class="alt kaynak">' +
        (o.kaynak === 'sayim' ? 'verinizden sayıldı'
          : o.kaynak === 'elle' ? 'önemini siz belirlediniz' : 'konuşurken öğrenildi') +
        ' · ' + (o.gorulme || 1) + ' kez doğrulandı' +
        (o.bayat ? ' · uzun süredir tazelenmedi, etkisi azaldı' : '') +
        (o.adres ? ' · ' + kacir(o.adres) : '') +
        '</p></div>' +
        '<span class="onay-dugmeler">' +
        '<select onchange="hafizaAgirlik(\'' + kacir(o.id) + '\', this.value)">' +
        ONCELIKLER.map(x => '<option value="' + x.deger + '"' +
          (x.deger === enYakinOncelik(ag) ? ' selected' : '') + '>' +
          x.ad + '</option>').join('') + '</select>' +
        '<button class="baglanti" onclick="hafizaUnut(\'' + kacir(o.id) + '\')">unut</button>' +
        '</span></div>';
    });
    s += '</div>';
  });
  return s;
}

function enYakinOncelik(deger) {
  return ONCELIKLER.reduce((a, b) =>
    Math.abs(b.deger - deger) < Math.abs(a.deger - deger) ? b : a).deger;
}

async function hafizaUnut(id) {
  const r = await cagir('/api/hafiza-unut', { id: id });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

async function hafizaAgirlik(id, agirlik) {
  const r = await cagir('/api/hafiza-agirlik', { id: id, agirlik: Number(agirlik) });
  if (r.hata) { hataMetni = r.hata; return ciz(); }
  await yenile();
}

// Konuşma geçmişi. Sesli ekranda balon yalnızca son turu gösterir; "dün ne
// konuşmuştuk" sorusunun cevabı burada durur. Kayıt zaten sunucuda tutuluyor
// (state/sohbet.jsonl), bu sayfa onu okur.
function defterSohbet() {
  if (!sohbetGecmisi.length) {
    return '<p class="bos">Henüz konuşma yok. Sesli moddan bir şey sorun.</p>';
  }
  let s = '<div class="akis">';
  sohbetGecmisi.forEach(t => {
    s += t.rol === 'kullanici'
      ? '<p class="ben">' + kacir(t.metin) + '</p>'
      : '<p class="ses">' + kacir(t.metin) + '</p>';
  });
  return s + '</div>';
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

async function tara() {
  if (taraniyor) return;
  taraniyor = true;
  // Durumu hemen çek ki "tarama sürüyor" bloğu beklemeden görünsün.
  cagir('/api/durum').then(d => { if (d) { D = d; ciz(); nabziBaslat(); } });
  ciz();
  const r = await cagir('/api/tarama', {});
  taraniyor = false;
  nabziDurdur();
  if (r.hata) hataMetni = r.hata;
  await yenile();
}

// -------------------------------------------------------------------- kabuk

function defterAc(hangi) {
  gorunum = 'defter';
  defterOdak = hangi;
  acikProje = null;
  etiketSuzgeci = null;
  sesliModdanCik();
  ciz();
  window.scrollTo(0, 0);
}

function projeAc(ad) { acikProje = acikProje === ad ? null : ad; etiketSuzgeci = null; ciz(); }
function suz(e) { etiketSuzgeci = e; ciz(); }

function ciz() {
  cizKunye();
  const sesli = gorunum === 'ses';
  document.getElementById('sutun').hidden = sesli;
  document.getElementById('ses-ekran').hidden = !sesli;
  document.getElementById('ses-yan').hidden = !sesli;
  document.querySelector('.tabaka').classList.toggle('uc-kolon', sesli);
  if (sesli) { sahneHazirla(); cizSesYan(); return cizSes(); }
  document.getElementById('sutun').innerHTML = cizDefter();
}

// ------------------------------------------------------------------ sesli mod

// Sahne bir kez kurulur ve modlar arasında yaşamaya devam eder; her girişte
// yeniden yüklemek hem yavaş hem de boşuna.
let sahneKuruldu = false;

function sahneHazirla() {
  if (sahneKuruldu) return;
  Avatar.baslat(document.getElementById('ses-sahne'));
  Ses.baglaCizim(cizSes);
  sahneKuruldu = true;
}

function sesliModaGec() {
  gorunum = 'ses';
  ciz();
  window.scrollTo(0, 0);
}

function sesliModdanCik() {
  if (typeof Ses !== 'undefined') Ses.kapat();
}

function cizSes() {
  const h = Ses.hal();
  const bos = !h.balon;
  const benim = h.durum === 'dinliyor' || h.durum === 'dusunuyor';

  const yazilar = {
    bosta: 'Konuşmak için mikrofona basılı tutun.',
    dinliyor: 'Dinliyorum…',
    dusunuyor: 'Düşünüyorum…',
    konusuyor: 'Konuşuyor…',
  };

  let s = '<div class="ses-balon' + (benim ? ' benim' : '') + (bos ? ' bos' : '') + '">' +
    (bos ? 'Bugün ne konuşalım?' : kacir(h.balon)) + '</div>';
  s += '<div class="ses-durum">' + yazilar[h.durum] + '</div>';
  s += '<div class="ses-dugmeler">' +
    '<button class="mikrofon' + (h.durum === 'dinliyor' ? ' acik' : '') + '"' +
    (h.destekli ? '' : ' disabled') +
    ' title="Basılı tutun, konuşun, bırakın"' +
    ' onmousedown="Ses.dinlemeyeBasla()" onmouseup="Ses.dinlemeyiBitir()"' +
    ' onmouseleave="Ses.dinlemeyiBitir()"' +
    ' ontouchstart="event.preventDefault();Ses.dinlemeyeBasla()"' +
    ' ontouchend="Ses.dinlemeyiBitir()">🎙</button>' +
    '<button class="btn" onclick="defterAc(\'sohbet\')">Geçmiş</button>' +
    '</div>';

  // Konuşamayacağınız yerde de sorulabilsin: aynı akış, elle yazılmış soru.
  const mesgul = h.durum === 'dusunuyor' || h.durum === 'konusuyor';
  s += '<div class="ses-yazi">' +
    '<input type="text" id="ses-soru" placeholder="Ya da yazın…"' +
    (mesgul ? ' disabled' : '') +
    ' onkeydown="if(event.key===\'Enter\')sesliSor()">' +
    '<button class="btn btn-primary" onclick="sesliSor()"' +
    (mesgul ? ' disabled' : '') + '>Söyle</button></div>';

  if (h.uyari) s += '<div class="ses-uyari">' + kacir(h.uyari) + '</div>';

  document.getElementById('ses-yuz').innerHTML = s;
  const kutu = document.getElementById('ses-soru');
  if (kutu && !mesgul && sesKutusuOdakli) kutu.focus();
}

// Kutu her çizimde yeniden kuruluyor; odak ancak kullanıcı oraya bir kez
// dokunduysa geri verilir, yoksa sayfa açılır açılmaz imleç kutuya zıplar.
let sesKutusuOdakli = false;

function sesliSor() {
  const kutu = document.getElementById('ses-soru');
  if (!kutu) return;
  const soru = kutu.value.trim();
  if (!soru) return;
  kutu.value = '';
  sesKutusuOdakli = true;
  Ses.gonder(soru);
}

// Sağ şerit: tarama ve günün önemli mailleri. Yalnızca sesli modda çizilir —
// konuşma ekranında bunlar akışın içinde zaten var.
function cizSesYan() {
  let s = '';
  if (hataMetni) { s += '<div class="hata">' + kacir(hataMetni) + '</div>'; hataMetni = null; }

  // Brifing eskiden konuşma sayfasının açılışıydı; o sayfa kaldırıldı, günün
  // özeti buraya taşındı. Uzunsa kırpılır, tamamı pencerede açılır.
  s += '<div class="yan-baslik">Bugün</div>';
  if (D.bugunun_brifingi) {
    s += brifingDamgasi() +
      '<p class="yan-brifing">' + kacir(kirp(D.bugunun_brifingi
        .replace(/^#+\s*/gm, '').replace(/\*\*/g, ''), 320)) + '</p>' +
      '<div><button class="baglanti" onclick="brifingiAc()">tamamını oku</button></div>';
  } else {
    s += '<p class="yan-bos">Bugün için henüz tarama yapılmadı.</p>';
  }

  s += '<div class="yan-baslik">Tarama</div>';
  s += '<div><button class="btn btn-primary" onclick="tara()"' +
    (taraniyor ? ' disabled' : '') + '>' +
    (taraniyor ? 'taranıyor…' : 'şimdi tara') + '</button></div>';
  s += taramaCiz();
  if (D.brifing_zamani) s += brifingDamgasi();

  s += '<div class="yan-baslik">Önemli mailler</div>';
  const bildirimler = bildirimleriCiz();
  s += bildirimler || '<p class="yan-bos">Gün içinde eşiği geçen mail olmadı.</p>';

  const onaylar = onaylariCiz();
  if (onaylar) s += '<div class="yan-baslik">Onayınızı bekleyen</div>' + onaylar;

  document.getElementById('ses-yan').innerHTML = s;
}

function brifingiAc() {
  modalAc('<h2>' + kacir(brifingDamgasiMetni()) + '</h2><pre>' +
    kacir(D.bugunun_brifingi || '') + '</pre>' +
    '<div class="dialog-actions"><button class="btn" onclick="modalKapat()">Kapat</button></div>');
}

function brifingDamgasiMetni() {
  return D.brifing_zamani ? saat(D.brifing_zamani) + ' brifingi' : 'Bugünün brifingi';
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

// Sohbet sunucuda saklanıyor (state/sohbet.jsonl), tarayıcı belleğinde değil.
// Sayfa yenilense, sekme değişse de konuşma yerinde kalır. Cevap beklenirken
// dokunulmaz: o an yerel dizide henüz sunucuya yazılmamış bir tur vardır.
function sohbetiYukle() {
  if (bekleyen) return;
  if (D && Array.isArray(D.sohbet)) sohbetGecmisi = D.sohbet.slice();
}

async function yenile() {
  D = await cagir('/api/durum');
  sohbetiYukle();
  ciz();
  await taslaklariGetir();
  ciz();
  // Bu sekme taramayı başlatmamış olsa da (başka sekme, sayfa yenilendi)
  // süren bir tarama varsa takibe al.
  if (D && D.tarama && D.tarama.suruyor) nabziBaslat();
}


// --------------------------------------------------- arka plan yenilemesi

// Canlı izleyici yeni maili sisteme düşürüyor ama açık duran sayfa bunu
// göremiyordu; kullanıcı yeni maili görmek için tarama yapmak zorunda kalıyordu.
// Panel artık sunucuyu kendisi yokluyor. Sunucu yerel, model çağrılmıyor —
// yoklamanın maliyeti yok.
const ARKA_PLAN_ARALIGI = 20000;

// Her yoklamada tüm paneli çizmek titretir. Ucuz bir imza karşılaştırılır;
// `simdi` alanı bilerek dışarıda: her yoklamada değişir, tek başına tetiklememeli.
function veriImzasi(d) {
  if (!d) return '';
  const maddeler = (d.mail && d.mail.maddeler) || [];
  const enYuksek = maddeler.reduce((a, m) => Math.max(a, ham(m)), 0);
  return [
    d.ham_cekildi, d.brifing_zamani, maddeler.length, enYuksek,
    (d.bildirimler || []).length,
    (d.sohbet || []).length,
    (d.takvim || []).length,
    ((d.konular && d.konular.kendi) || []).length,
    ((d.sosyal && d.sosyal.konusmalar) || []).length,
    (d.projeler || []).length,
  ].join('|');
}

// Kullanıcının elinden iş almayacağız: yazarken, okurken ya da bir işlem
// beklerken yenileme bir sonraki tura bırakılır.
function yenilemeUygunMu() {
  if (bekleyen || taraniyor) return false;
  if (document.hidden) return false;
  const ortu = document.getElementById('ortu');
  if (ortu && !ortu.hidden) return false;            // açık pencere kapanmasın
  const sesKutu = document.getElementById('ses-soru');
  if (sesKutu && (sesKutu.value.trim() || document.activeElement === sesKutu)) return false;
  // Sesli modda konuşma sürerken çizim balonu tazeler; ses kesilmez ama
  // kullanıcının okuduğu satırı ortasından değiştirmenin anlamı yok.
  if (typeof Ses !== 'undefined' && Ses.hal().durum !== 'bosta') return false;
  return true;
}

async function arkaPlanYoklamasi() {
  if (!yenilemeUygunMu()) return;
  const yeni = await cagir('/api/durum').catch(() => null);
  if (!yeni) return;
  if (veriImzasi(yeni) === veriImzasi(D)) { D = yeni; return; }

  const konum = window.scrollY;
  D = yeni;
  sohbetiYukle();
  ciz();
  await taslaklariGetir();
  ciz();
  window.scrollTo(0, konum);   // imleci ve konumu kullanıcıdan habersiz oynatma
  if (D.tarama && D.tarama.suruyor) nabziBaslat();
}

setInterval(arkaPlanYoklamasi, ARKA_PLAN_ARALIGI);
// Sekmeye dönüldüğünde beklemeden tazele.
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) arkaPlanYoklamasi();
});

yenile();
