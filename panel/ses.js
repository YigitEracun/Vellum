// Sesli mod: mikrofonla sor, sesli cevap al.
//
// Akış tek yönlü ve kısa: mikrofon → metin → /api/sohbet → /api/seslendir →
// <audio>. Sohbet turu sunucuda zaten kaydediliyor (state/sohbet.jsonl), o
// yüzden burada ayrı bir kayıt tutulmuyor — yazılı moda dönünce konuşma orada.
//
// Dinleme bas-konuş. Sürekli dinleme hem mahremiyet sorunudur hem de televizyon
// sesiyle tetiklenir.

const Ses = (function () {
  const TANIYICI = window.SpeechRecognition || window.webkitSpeechRecognition;

  let taniyici = null;
  let dinliyor = false;
  let calan = null;          // <audio>
  let sesBaglami = null, cozumleyici = null, kaynak = null, mikKaynak = null;
  let olcumKaresi = null;
  let mikAkisi = null;

  let durum = 'bosta';       // bosta | dinliyor | dusunuyor | konusuyor
  let balon = '';            // balonda yazan metin
  let uyari = '';            // kullanıcıya gösterilecek tek satırlık sorun
  let ciz = function () {};  // panel çizimini tetikleyen geri çağrı

  function baglaCizim(f) { ciz = f; }

  function hal() {
    return { durum, balon, uyari, destekli: !!TANIYICI };
  }

  function durumaGec(d) {
    durum = d;
    Avatar.durum(d);
    ciz();
  }

  // ------------------------------------------------------------- dinleme

  function taniyiciKur() {
    const t = new TANIYICI();
    t.lang = 'tr-TR';
    t.interimResults = true;
    t.continuous = false;
    t.maxAlternatives = 1;

    t.onresult = function (o) {
      let metin = '';
      for (let i = 0; i < o.results.length; i++) metin += o.results[i][0].transcript;
      balon = metin;
      ciz();
      if (o.results[o.results.length - 1].isFinal) gonder(metin);
    };
    t.onerror = function (o) {
      dinliyor = false;
      mikrofonuBirak();
      uyari = o.error === 'not-allowed'
        ? 'Mikrofon izni verilmedi. Tarayıcının adres çubuğundaki kilitten açabilirsiniz.'
        : (o.error === 'network'
            ? 'Konuşma tanıma internete bağlanamadı.'
            : 'Ses alınamadı (' + o.error + ').');
      durumaGec('bosta');
    };
    t.onend = function () {
      dinliyor = false;
      mikrofonuBirak();
      if (durum === 'dinliyor') durumaGec('bosta');
    };
    return t;
  }

  async function dinlemeyeBasla() {
    if (!TANIYICI) {
      uyari = 'Bu tarayıcıda konuşma tanıma yok. Chrome ya da Edge gerekiyor.';
      return ciz();
    }
    if (dinliyor) return;
    sustur();
    uyari = '';
    balon = '';
    try {
      taniyici = taniyici || taniyiciKur();
      taniyici.start();
      dinliyor = true;
      durumaGec('dinliyor');
      mikrofonuDinle();   // küre sesimizle oynasın
    } catch (e) {
      // start() arka arkaya çağrılırsa atar; kullanıcıya gösterecek bir şey yok.
      dinliyor = false;
    }
  }

  function dinlemeyiBitir() {
    if (taniyici && dinliyor) {
      try { taniyici.stop(); } catch (e) {}
    }
  }

  // Mikrofonun anlık şiddetini küreye besler. Tanıma zaten mikrofonu açıyor;
  // bu ayrı akış yalnızca görsel geri bildirim için.
  async function mikrofonuDinle() {
    if (!navigator.mediaDevices || mikAkisi) return;
    try {
      mikAkisi = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      return;   // izin yoksa küre sabit durur, mod yine çalışır
    }
    const b = baglam();
    mikKaynak = b.createMediaStreamSource(mikAkisi);
    mikKaynak.connect(cozumleyici);
    olc();
  }

  function mikrofonuBirak() {
    if (mikKaynak) { try { mikKaynak.disconnect(); } catch (e) {} mikKaynak = null; }
    if (mikAkisi) {
      mikAkisi.getTracks().forEach(function (p) { p.stop(); });
      mikAkisi = null;
    }
    Avatar.seviye(0);
  }

  // --------------------------------------------------------------- cevap

  async function gonder(metin) {
    metin = (metin || '').trim();
    if (!metin) return durumaGec('bosta');
    durumaGec('dusunuyor');
    balon = metin;
    ciz();

    let cevap;
    try {
      const r = await cagir('/api/sohbet', {
        soru: metin, gecmis: sohbetGecmisi.slice(), ses: true,
      });
      cevap = r.hata ? null : (r.cevap || '');
      if (r.hata) uyari = r.hata;
    } catch (e) {
      uyari = 'Sunucuya ulaşılamadı.';
    }
    if (!cevap) return durumaGec('bosta');

    // Yazılı mod da bu turu görsün diye yerel geçmişe düşülür; sunucu zaten
    // diske yazdı.
    sohbetGecmisi.push({ rol: 'kullanici', metin: metin });
    sohbetGecmisi.push({ rol: 'asistan', metin: cevap });

    balon = cevap;
    durumaGec('konusuyor');
    await seslendir(cevap);
  }

  async function seslendir(metin) {
    let yol = null;
    try {
      const r = await cagir('/api/seslendir', { metin: metin });
      yol = r.yol;
      if (!yol && r.not) uyari = r.not;
    } catch (e) {
      uyari = 'Ses üretilemedi.';
    }
    if (!yol) {
      // Ses yoksa balon yazılı kalır; konuşma kaybolmaz.
      return durumaGec('bosta');
    }
    await cal(yol);
  }

  function cal(yol) {
    return new Promise(function (bitti) {
      sustur();
      calan = new Audio(yol);
      calan.addEventListener('ended', function () { bittiSay(); bitti(); });
      calan.addEventListener('error', function () { bittiSay(); bitti(); });
      calan.play().then(sesiOlc).catch(function () {
        // Tarayıcı otomatik oynatmayı engelledi. Mikrofona basmak normalde izin
        // sayılır; sayılmadıysa sessiz kalmak yerine söylensin, yoksa kullanıcı
        // sesin neden gelmediğini anlayamaz.
        uyari = 'Tarayıcı sesi engelledi. Sayfaya bir kez tıklayıp tekrar deneyin.';
        bittiSay();
        bitti();
      });
    });
  }

  function bittiSay() {
    Avatar.seviye(0);
    if (durum === 'konusuyor') durumaGec('bosta');
  }

  function sustur() {
    if (calan) {
      try { calan.pause(); } catch (e) {}
      calan = null;
    }
    if (kaynak) { try { kaynak.disconnect(); } catch (e) {} kaynak = null; }
    if (olcumKaresi) { cancelAnimationFrame(olcumKaresi); olcumKaresi = null; }
    Avatar.seviye(0);
  }

  // -------------------------------------------------------------- olcum

  function baglam() {
    if (!sesBaglami) {
      const B = window.AudioContext || window.webkitAudioContext;
      sesBaglami = new B();
      cozumleyici = sesBaglami.createAnalyser();
      cozumleyici.fftSize = 256;
    }
    if (sesBaglami.state === 'suspended') sesBaglami.resume();
    return sesBaglami;
  }

  function sesiOlc() {
    const b = baglam();
    try {
      kaynak = b.createMediaElementSource(calan);
      kaynak.connect(cozumleyici);
      cozumleyici.connect(b.destination);
    } catch (e) {
      return;   // aynı öğe iki kez bağlanamaz; ses yine çalar, küre sabit kalır
    }
    olc();
  }

  function olc() {
    const veri = new Uint8Array(cozumleyici.frequencyBinCount);
    function tur() {
      olcumKaresi = requestAnimationFrame(tur);
      cozumleyici.getByteTimeDomainData(veri);
      let toplam = 0;
      for (let i = 0; i < veri.length; i++) {
        const s = (veri[i] - 128) / 128;
        toplam += s * s;
      }
      const guc = Math.sqrt(toplam / veri.length);      // RMS
      Avatar.seviye(Math.min(1, guc * 3.2));
    }
    tur();
  }

  // --------------------------------------------------------------- disari

  function kapat() {
    dinlemeyiBitir();
    sustur();
    mikrofonuBirak();
    durum = 'bosta';
    balon = '';
  }

  return {
    hal, baglaCizim, dinlemeyeBasla, dinlemeyiBitir, kapat, sustur,
    gonder,   // yazarak da denenebilsin
  };
})();
