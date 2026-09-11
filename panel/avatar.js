// Sesli modun görsel yüzü. Panele üç şey açar, gerisi buranın içinde kalır:
//
//   Avatar.baslat(kap, ayar)   sahneyi bir kez kurar
//   Avatar.durum(d)            'bosta' | 'dinliyor' | 'dusunuyor' | 'konusuyor'
//   Avatar.seviye(0..1)        anlık ses şiddeti
//
// İki gövdesi var. Varsayılan olan burada çizilen küre: çevrimdışı çalışır,
// rozet göstermez, kimseye bağımlı değildir. Spline sahnesinin yayın bağlantısı
// verilirse (ayar.spline) onun yerine o yüklenir — panel farkı bilmez, çünkü
// dışarı açılan üç fonksiyon aynıdır.

const Avatar = (function () {
  let kap = null;
  let tuval = null, ctx = null, olcek = 1;
  let kare = null;            // requestAnimationFrame kimliği
  let sahneTuru = 'tuval';    // 'tuval' | 'spline'
  let spline = null;

  let durumAdi = 'bosta';
  let hedefSeviye = 0, anlikSeviye = 0;
  let baslangic = performance.now();

  // Göz kırpma: rastgele ama seyrek. Sabit aralık makine gibi duruyor.
  let sonrakiKirpma = 2000 + Math.random() * 3000;
  let kirpmaBaslangici = -1;

  const RENKLER = {
    bosta:      { ic: '#0f6cbd', dis: '#cfe4fa' },
    dinliyor:   { ic: '#0e700e', dis: '#cfe8cf' },
    dusunuyor:  { ic: '#7f6000', dis: '#f5e6b8' },
    konusuyor:  { ic: '#0f6cbd', dis: '#ebf3fc' },
  };

  function baslat(hedefKap, ayar) {
    kap = hedefKap;
    ayar = ayar || {};
    if (ayar.spline) return splineKur(ayar.spline);
    return tuvalKur();
  }

  // ---------------------------------------------------------------- spline

  function splineKur(url) {
    sahneTuru = 'spline';
    const viewer = document.createElement('spline-viewer');
    viewer.setAttribute('url', url);
    viewer.style.width = '100%';
    viewer.style.height = '100%';
    kap.innerHTML = '';
    kap.appendChild(viewer);
    spline = viewer;
    // Sahne yüklenemezse (ağ yok, bağlantı bozuk) kendi küremize düşeriz;
    // sesli mod sahnesiz de çalışmalı.
    viewer.addEventListener('error', tuvalKur);
    setTimeout(function () {
      if (sahneTuru === 'spline' && !viewer.shadowRoot) tuvalKur();
    }, 8000);
  }

  // ----------------------------------------------------------------- tuval

  function tuvalKur() {
    sahneTuru = 'tuval';
    spline = null;
    tuval = document.createElement('canvas');
    tuval.className = 'avatar-tuval';
    kap.innerHTML = '';
    kap.appendChild(tuval);
    ctx = tuval.getContext('2d');
    olcekle();
    window.addEventListener('resize', olcekle);
    dongu();
  }

  function olcekle() {
    if (!tuval) return;
    olcek = window.devicePixelRatio || 1;
    const k = kap.getBoundingClientRect();
    tuval.width = Math.max(1, Math.round(k.width * olcek));
    tuval.height = Math.max(1, Math.round(k.height * olcek));
    tuval.style.width = k.width + 'px';
    tuval.style.height = k.height + 'px';
  }

  function dongu() {
    kare = requestAnimationFrame(dongu);
    // Sekme arkada dururken boşuna çizme; GPU'yu sesli mod açıkken bile yakmaz.
    if (document.hidden || !kap || kap.hidden) return;
    ciz(performance.now() - baslangic);
  }

  function ciz(t) {
    if (!ctx) return;
    const g = tuval.width, y = tuval.height;
    const merkezX = g / 2, merkezY = y / 2;
    const taban = Math.min(g, y) * 0.20;
    const renk = RENKLER[durumAdi] || RENKLER.bosta;

    // Seviye ani zıplamasın: kulağa duyulan yumuşaklık göze de lazım.
    anlikSeviye += (hedefSeviye - anlikSeviye) * 0.22;

    ctx.clearRect(0, 0, g, y);

    // Nefes: boştayken tek hareket bu. Konuşurken sesin şiddeti devralır.
    const nefes = Math.sin(t / 1400) * 0.025;
    const r = taban * (1 + nefes + anlikSeviye * 0.42);

    // Dışarı yayılan halkalar — ses yükseldikçe belirginleşir.
    for (let i = 0; i < 3; i++) {
      const faz = ((t / 2600) + i / 3) % 1;
      const halkaR = r * (1 + faz * 1.5);
      const gorunurluk = (1 - faz) * (0.10 + anlikSeviye * 0.35);
      if (gorunurluk <= 0.01) continue;
      ctx.beginPath();
      ctx.arc(merkezX, merkezY, halkaR, 0, Math.PI * 2);
      ctx.strokeStyle = renk.ic;
      ctx.globalAlpha = gorunurluk;
      ctx.lineWidth = 2 * olcek;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Hâle
    const hale = ctx.createRadialGradient(merkezX, merkezY, r * 0.6,
                                          merkezX, merkezY, r * 2.2);
    hale.addColorStop(0, renk.dis);
    hale.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.globalAlpha = 0.55;
    ctx.beginPath();
    ctx.arc(merkezX, merkezY, r * 2.2, 0, Math.PI * 2);
    ctx.fillStyle = hale;
    ctx.fill();
    ctx.globalAlpha = 1;

    // Gövde
    const govde = ctx.createLinearGradient(merkezX - r, merkezY - r,
                                           merkezX + r, merkezY + r);
    govde.addColorStop(0, renk.ic);
    govde.addColorStop(1, renk.dis);
    ctx.beginPath();
    ctx.arc(merkezX, merkezY, r, 0, Math.PI * 2);
    ctx.fillStyle = govde;
    ctx.fill();

    if (durumAdi === 'dusunuyor') dusunmeYayi(merkezX, merkezY, r, t, renk);
    gozler(merkezX, merkezY, r, t);
  }

  function dusunmeYayi(x, y, r, t, renk) {
    const aci = (t / 600) % (Math.PI * 2);
    ctx.beginPath();
    ctx.arc(x, y, r * 1.28, aci, aci + Math.PI * 0.5);
    ctx.strokeStyle = renk.ic;
    ctx.lineWidth = 3 * olcek;
    ctx.lineCap = 'round';
    ctx.stroke();
  }

  function gozler(x, y, r, t) {
    if (kirpmaBaslangici < 0 && t > sonrakiKirpma) kirpmaBaslangici = t;
    let acilik = 1;
    if (kirpmaBaslangici >= 0) {
      const gecen = t - kirpmaBaslangici;
      if (gecen > 160) {
        kirpmaBaslangici = -1;
        sonrakiKirpma = t + 2500 + Math.random() * 4000;
      } else {
        acilik = Math.abs(gecen - 80) / 80;   // kapan ve aç
      }
    }
    // Konuşurken hafif kısılır; "ifade" hissi buradan geliyor.
    if (durumAdi === 'konusuyor') acilik *= 1 - anlikSeviye * 0.3;

    const ayrik = r * 0.38, gozR = r * 0.115;
    const yuk = Math.max(gozR * 0.22, gozR * 2 * acilik);
    ctx.fillStyle = '#ffffff';
    [-1, 1].forEach(function (yon) {
      ctx.beginPath();
      const gx = x + yon * ayrik, gy = y - r * 0.06;
      if (ctx.roundRect) {
        ctx.roundRect(gx - gozR, gy - yuk / 2, gozR * 2, yuk, gozR);
      } else {
        ctx.ellipse(gx, gy, gozR, yuk / 2, 0, 0, Math.PI * 2);
      }
      ctx.fill();
    });
  }

  // ------------------------------------------------------------------ yüz

  function durum(d) {
    durumAdi = d || 'bosta';
    if (d !== 'konusuyor' && d !== 'dinliyor') hedefSeviye = 0;
    if (spline && spline.emitEvent) {
      // Spline sahnesinde durum adıyla aynı olay varsa tetiklenir; yoksa
      // sessizce yutulur — sahne kimin hazırladığına göre farklı isimlendirir.
      try { spline.emitEvent('mouseDown', durumAdi); } catch (e) {}
    }
  }

  function seviye(x) {
    hedefSeviye = Math.max(0, Math.min(1, x || 0));
  }

  function durdur() {
    if (kare) cancelAnimationFrame(kare);
    kare = null;
  }

  return { baslat, durum, seviye, durdur, tur: () => sahneTuru };
})();
