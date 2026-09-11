# -*- coding: utf-8 -*-
"""Mail önem skorlaması — kural motoru.

`config/onem-kurallari.md` rubriğini deterministik uygular. Model çağırmaz: rubrik
zaten bir kural tablosu, onu modele hesaplatmak hem pahalı hem yavaş. Model yalnızca
eşiği geçen birkaç mail için, özet ve taslak yazmak üzere çalışır.

Kullanıcı kimliği koda gömülmez: `secrets/.env` içindeki GMAIL_ADRES ve
`config/kisiler.md` takma ad listesi çalışma anında okunur. Kimlik çözülemezse
"doğrudan sana yazılmış" ve "CC" sinyalleri tahmin edilmez, atlanır.
"""

import io
import json
import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABAN = 30
ESIK_AKSIYON = 70      # brifingin başında, aksiyon maddesi
ESIK_BILGI = 40        # "bilgin olsun" satırı; altı yalnızca sayı

# Hafızanın bir maile toplam katkısı. Yanlış öğrenilmiş tek bir olgu ne bir
# maili gömebilmeli ne de tepeye çıkarabilmeli.
HAFIZA_TAVANI = 40

# Toplu gönderim yapan adreslerin deseni. List-Unsubscribe başlığı kesin sinyaldir;
# bu desenler onu taşımayan otomatik göndericileri de yakalar.
OTOMATIK_DESEN = re.compile(
    r"(no-?reply|donotreply|do-not-reply|notification[s]?@|updates?-|mailer|"
    r"bounce|postmaster|newsletter|duyuru@|bulten@|alerts?@|welcome@)", re.I)

TARIH_DESEN = re.compile(
    r"\b(\d{1,2}[./]\d{1,2}([./]\d{2,4})?|\d{1,2}:\d{2})\b|"
    r"\b(pazartesi|salı|çarşamba|perşembe|cuma|cumartesi|pazar|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"son tarih|deadline|bugün|yarın|hafta içinde|kadar)\b", re.I)

# --------------------------------------------------------- ek duyarlı eşleşme

# Türkçe sondan eklemelidir: "fatura" yazan bir sözlük, gerçek metindeki
# "faturanız"ı kaçırır. Kapanış \b eşleşmeyi keser — ölçtük, kaçırıyordu.
#
# Çözüm `\w*` değil: o zaman "kaza" → "kazandınız" gibi yanlış pozitifler açılır
# (üstelik "kazandınız" tam da pazarlama dilidir). Bunun yerine gerçek çekim
# eklerinin açık bir listesi kullanılır. "nız" ektir, "ndınız" değildir.
_EKLER = (
    "ları", "leri", "lara", "lere", "larda", "lerde", "lardan", "lerden",
    "nız", "niz", "nuz", "nüz", "nızı", "nizi", "nuzu", "nüzü",
    "nızın", "nizin", "nuzun", "nüzün", "nıza", "nize", "nuza", "nüze",
    "nın", "nin", "nun", "nün", "ndan", "nden", "nda", "nde", "na", "ne",
    "sı", "si", "su", "sü", "sına", "sine", "sını", "sini", "sında", "sinde",
    "yı", "yi", "yu", "yü", "ya", "ye", "yla", "yle",
    "lar", "ler", "ım", "im", "um", "üm", "ımız", "imiz",
    "dan", "den", "tan", "ten", "da", "de", "ta", "te",
    "a", "e", "ı", "i", "u", "ü", "la", "le", "ce", "ca",
    # Fiil çekimleri: "alındı", "iletilmiştir", "ulaşacak". Sözlükte gövde
    # "alın" yazar, ekler burada karşılanır.
    "dı", "di", "du", "dü", "tı", "ti", "tu", "tü",
    "dık", "dik", "duk", "dük",
    "mış", "miş", "muş", "müş", "mıştır", "miştir", "muştur", "müştür",
    "dır", "dir", "dur", "dür", "dı̇r",
    "acak", "ecek", "acaktır", "ecektir",
    "ıyor", "iyor", "uyor", "üyor",
    "malı", "meli", "malıdır", "melidir",
    "ıldı", "ildi", "uldu", "üldü", "ılmış", "ilmiş",
    "ınız", "iniz", "unuz", "ünüz",
    "s",                                   # İngilizce çoğul
)
# Uzundan kısaya: regex ilk eşleşeni alır, "nızı" varken "a" ile durmasın.
_EK_KALIBI = "(?:%s)?" % "|".join(sorted(_EKLER, key=len, reverse=True))


def kalip_kur(govdeler):
    """Gövde listesinden ek duyarlı bir regex kurar.

    Gövde birden çok kelimeden oluşuyorsa ("son tarih") yalnızca sonuncusuna ek
    eklenir; araya giren boşluklar esnetilir.

    `...` yazımı araya kelime girebileceğini söyler: "başvurunuz ... iletil"
    kalıbı "Başvurunuz Başarıyla İletilmiştir" cümlesini de yakalar.
    """
    parcalar = []
    for g in govdeler:
        g = (g or "").strip()
        if not g:
            continue
        kelimeler = [(k if k == "..." else re.escape(k)) for k in g.split()]
        kelimeler[-1] += _EK_KALIBI
        desen = ""
        for i, k in enumerate(kelimeler):
            if k == "...":
                continue
            if i and kelimeler[i - 1] == "...":
                desen += r".{0,30}"
            elif i:
                desen += r"\s+"
            desen += k
        parcalar.append(desen)
    if not parcalar:
        return None
    # Kapanış \b şart: onsuz "kaza" gövdesi "kazandınız" içinde eşleşir. Ek
    # listesi ancak sonu da bağlanınca ayırt edici olur — "nız" ek olduğu için
    # "faturanız" geçer, "ndınız" ek olmadığı için "kazandınız" geçmez.
    return re.compile(r"\b(?:%s)\b" % "|".join(parcalar), re.I)

# İş başvurusu kuralları artık config/anahtar-kelimeler.md içinde:
# is-basvurusu-onayi (negatif) ve is-basvurusu-ilerleme (pozitif) kategorileri.

SORU_DESEN = re.compile(r"\?")


def _env_oku(yol):
    """basit .env okuyucu (beyin.py ile aynı biçim)."""
    d = {}
    if not os.path.exists(yol):
        return d
    for satir in io.open(yol, encoding="utf-8", errors="replace"):
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        deger = deger.strip()
        if len(deger) > 1 and deger[0] == deger[-1] and deger[0] in "\"'":
            deger = deger[1:-1]
        d[ad.strip()] = deger
    return d


def kullanici_adresleri():
    """Kullanıcının adreslerini çalışma anında toplar. Hiçbiri koda gömülü değildir.

    Sıra: ortam değişkeni → secrets/.env → .env → config/kisiler.md takma adlar.
    """
    adresler = []
    k = os.environ.get("GMAIL_ADRES")
    if not k:
        for yol in (os.path.join(KOK, "secrets", ".env"), os.path.join(KOK, ".env")):
            k = _env_oku(yol).get("GMAIL_ADRES")
            if k:
                break
    if k:
        adresler.append(k.strip().lower())
    return [a for a in adresler if a]


def _bolum(metin, baslik):
    """kisiler.md içinden bir başlığın altındaki satırları döner."""
    kalip = re.compile(r"^##\s*%s.*?$(.*?)(?=^##\s|\Z)" % baslik, re.I | re.M | re.S)
    e = kalip.search(metin)
    return e.group(1) if e else ""


def _adresleri_ayikla(metin):
    """Yorum içindekiler dahil tüm mail adreslerini toplar (liste yorumla doldurulabilir)."""
    return [a.lower() for a in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", metin)]


def kisi_listeleri():
    """VIP ve gürültü adresleri: config şablonu + kullanıcının kendi listesi.

    Kişi adları ve adresleri kişisel veridir; `config/kisiler.md` git tarafından
    izlendiği için oraya yazılan gerçek adresler repoya girerdi. Kullanıcının
    girdileri `state/konular.json` içinde durur ve panelden yönetilir. Dosya
    şablon olarak kalır — elle düzenlemek isteyen oraya da yazabilir.
    """
    vip, gurultu = [], []
    yol = os.path.join(KOK, "config", "kisiler.md")
    if os.path.exists(yol):
        metin = io.open(yol, encoding="utf-8", errors="replace").read()
        # Yorum satırlarındaki örnekler listeye girmemeli.
        temiz = re.sub(r"<!--.*?-->", "", metin, flags=re.S)
        vip = _adresleri_ayikla(_bolum(temiz, "VIP"))
        gurultu = _adresleri_ayikla(_bolum(temiz, "Gürültü"))

    yerel = kullanici_konulari()
    vip += [str(a).lower() for a in (yerel.get("vip") or [])]
    gurultu += [str(a).lower() for a in (yerel.get("gurultu") or [])]
    return sorted(set(vip)), sorted(set(gurultu))


def yazistiklarim():
    """Daha önce mail yazdığınız adresler. Önbellekten okunur, IMAP'e gidilmez.

    Dosyayı `scripts/gmail_fetch.yazistiklarim()` günde bir tazeler; skorlama
    anlık ve çevrimdışı kalmalı.
    """
    yol = os.path.join(KOK, "state", "raw", "yazistiklarim.json")
    if not os.path.exists(yol):
        return []
    try:
        d = json.load(io.open(yol, encoding="utf-8"))
    except ValueError:
        return []
    return [a.lower() for a in (d.get("adresler") or [])]


# ------------------------------------------------------------------- sözlük

SOZLUK_DOSYASI = os.path.join(KOK, "config", "anahtar-kelimeler.md")
KONULAR_DOSYASI = os.path.join(KOK, "state", "konular.json")


def ortak_sozluk():
    """config/anahtar-kelimeler.md — projeyle gelen varsayılan sözlük.

    Biçim: `## kategori +30` başlığı, altında her satır bir gövde.
    """
    if not os.path.exists(SOZLUK_DOSYASI):
        return {}
    metin = re.sub(r"<!--.*?-->", "", io.open(
        SOZLUK_DOSYASI, encoding="utf-8", errors="replace").read(), flags=re.S)
    kategoriler = {}
    ad = None
    for satir in metin.splitlines():
        basliksa = re.match(r"^##\s+([a-z0-9\-]+)\s+([+-]?\d+)\s*$", satir.strip(), re.I)
        if basliksa:
            ad = basliksa.group(1).lower()
            kategoriler[ad] = {"agirlik": int(basliksa.group(2)), "govdeler": []}
            continue
        if satir.startswith("#"):
            ad = None                      # biçim başlıkları kategori değildir
            continue
        s = satir.strip()
        if ad and s and not s.startswith(("|", ">", "-", "*", "`")):
            kategoriler[ad]["govdeler"].append(s)
    return {a: k for a, k in kategoriler.items() if k["govdeler"]}


def kullanici_konulari():
    """state/konular.json — panelden girilen konular. Kişisel, git dışı."""
    if not os.path.exists(KONULAR_DOSYASI):
        return {}
    try:
        d = json.load(io.open(KONULAR_DOSYASI, encoding="utf-8"))
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def sozluk():
    """Ortak sözlük + kullanıcının konuları. Çakışmada kullanıcı kazanır.

    Kullanıcı bir kategoriyi kapatmışsa (`kapali` listesi) o kategori hiç
    uygulanmaz — ortak dosya değiştirilmez, karar yerel dosyada durur.
    """
    birlesik = {a: dict(k) for a, k in ortak_sozluk().items()}
    yerel = kullanici_konulari()

    for konu in yerel.get("konular") or []:
        if not isinstance(konu, dict):
            continue
        kelime = (konu.get("kelime") or "").strip()
        if not kelime:
            continue
        ad = (konu.get("kategori") or "kendi-konularim").lower()
        agirlik = konu.get("agirlik")
        k = birlesik.setdefault(ad, {"agirlik": 30, "govdeler": []})
        k["govdeler"] = list(k["govdeler"]) + [kelime]
        if isinstance(agirlik, int):
            k["agirlik"] = agirlik

    for ad in yerel.get("kapali") or []:
        birlesik.pop(str(ad).lower(), None)
    return birlesik


def _kaliplar():
    """Sözlüğü derlenmiş kalıplara çevirir. Her çağrıda yeniden kurulur:
    kullanıcı panelden kelime eklediğinde bir sonraki skorlama görsün."""
    return [(ad, k["agirlik"], kalip_kur(k["govdeler"]))
            for ad, k in sorted(sozluk().items())]


def _adres(metin):
    e = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", metin or "")
    return e.group(0).lower() if e else ""


# --------------------------------------------------------------------- hafıza

def _hafiza_kur(girdi=None):
    """Hafıza olgularını kalıplara çevirir.

    Aynı ağırlıktaki kelimeler tek kalıpta toplanır; her olgu için ayrı regex
    derlemek 50 olguda 50 tarama demekti. Hafıza yoksa ya da modül bulunmuyorsa
    boş döner — skorlama hafızasız da çalışmalı.
    """
    if girdi is None:
        try:
            import hafiza
            girdi = hafiza.skorlama_girdisi()
        except Exception:
            girdi = {"kelimeler": [], "kisiler": {}}

    kovalar = {}
    for k in girdi.get("kelimeler") or []:
        anahtar = k.get("anahtar") or k.get("kelime")
        kova = kovalar.setdefault((int(k.get("agirlik") or 0), anahtar), [])
        kova.append(k.get("kelime"))

    kaliplar = []
    for (agirlik, anahtar), govdeler in sorted(kovalar.items()):
        govdeler = [g for g in govdeler if g]
        if not govdeler or not agirlik:
            continue
        # Ek duyarlı kalıp: "mimar" olgusu "mimarın", "mimarlığı" da yakalar.
        kaliplar.append((anahtar, agirlik, kalip_kur(govdeler)))
    return kaliplar, dict(girdi.get("kisiler") or {})


class Skorlayici(object):
    """Rubriği uygular. Kullanıcı ve listeler dışarıdan verilebilir (test için)."""

    def __init__(self, kullanici=None, vip=None, gurultu=None, hafiza_girdisi=None):
        if kullanici is None:
            benim = kullanici_adresleri()
        elif isinstance(kullanici, str):
            benim = [kullanici.lower()]
        else:
            benim = [k.lower() for k in kullanici]
        self.benim = [b for b in benim if b]
        if vip is None or gurultu is None:
            v, g = kisi_listeleri()
            vip = v if vip is None else vip
            gurultu = g if gurultu is None else gurultu
        self.vip = [a.lower() for a in vip]
        self.gurultu = [a.lower() for a in gurultu]
        # Sözlük her örnekte bir kez derlenir; panelden kelime eklendiğinde
        # sonraki skorlama yeni Skorlayici ile kurulur ve değişikliği görür.
        self.kaliplar = _kaliplar()
        self.yazistiklarim = set(yazistiklarim())
        # Hafıza: sistemin kullanıcı hakkında öğrendikleri. Boş olduğunda
        # skorlar hafıza öncesiyle birebir aynı kalır.
        self.hafiza_kaliplari, self.hafiza_kisileri = _hafiza_kur(hafiza_girdisi)

    def skorla(self, m):
        """Bir ham mail kaydını puanlar. Dönen alanlar digest şemasıyla uyumludur."""
        sinyaller = []
        puan = TABAN
        gonderen = _adres(m.get("gonderen", ""))
        konu = m.get("konu") or ""
        govde = m.get("govde") or ""
        metin = konu + "\n" + govde

        def ekle(ad, etki):
            nonlocal puan
            puan += etki
            sinyaller.append("%s %+d" % (ad, etki))

        if gonderen and gonderen in self.vip:
            ekle("vip", +40)
        if gonderen and gonderen in self.gurultu:
            ekle("gurultu-listesi", -40)
        # Kelimeden güçlü bir sinyal: bu adrese daha önce siz yazdınız.
        # VIP'in (+40) hemen altında — VIP açık tercihtir, bu türetilmiş bir
        # tahmindir. Boş bir VIP listesinde bile gerçek muhataplar öne çıkar.
        if gonderen and gonderen in self.yazistiklarim and gonderen not in self.vip:
            ekle("yazistiginiz-kisi", +35)

        # Kimlik bilinmiyorsa tahmin yürütme: bu iki sinyali hiç hesaplama.
        if self.benim:
            alici = [_adres(a) for a in (m.get("alici") or [])]
            cc = [_adres(a) for a in (m.get("cc") or [])]
            if any(b in alici for b in self.benim):
                ekle("dogrudan-size", +20)
            elif any(b in cc for b in self.benim):
                ekle("cc", -15)

        # İki tür otomatik mail vardır ve ayrımı önemlidir:
        #   bulten  — List-Unsubscribe/List-Id taşır. Pazarlama listesi. Bir mülakat
        #             daveti asla abonelikten çıkma bağlantısıyla gelmez.
        #   islem   — noreply adresinden gelen bildirim. Başvuru sistemleri (ATS)
        #             mülakat davetini de böyle gönderir; içeriğine bakılmalı.
        bulten = bool(m.get("toplu"))
        islem = bool(gonderen and OTOMATIK_DESEN.search(gonderen))
        if bulten or islem:
            ekle("toplu-gonderim", -50)

        # Sözlükteki negatif kategoriler (başvuru onayı gibi) her koşulda sayılır:
        # bunlar önemi düşüren sinyaller, bültende de geçerlidir.
        eksiler = [(ad, ag, k) for ad, ag, k in self.kaliplar if ag < 0]
        artilar = [(ad, ag, k) for ad, ag, k in self.kaliplar if ag > 0]

        dusuruldu = False
        for ad, agirlik, kalip in eksiler:
            if kalip and kalip.search(metin):
                ekle(ad, agirlik)
                dusuruldu = True

        # İlerleme sinyali bülteni kurtarır: bültenin gövdesinde geçen "interview"
        # mülakat daveti değildir, o yüzden bültende hiç aranmaz.
        ilerleme = False
        if not dusuruldu and not bulten:
            for ad, agirlik, kalip in artilar:
                if ad.startswith("is-basvurusu") and kalip and (
                        kalip.search(konu) or kalip.search(govde[:400])):
                    ekle(ad, agirlik)
                    ilerleme = True

        # İçerik sinyalleri yalnızca size yazılmış maillerde anlamlı. Bültende geçen
        # tarih sizin son tarihiniz, geçen fiyat sizin faturanız değildir — pazarlama
        # metni bunların hepsini taşır ve toplu gönderim cezasını geri kapatırdı.
        icerik_sayilir = not (bulten or islem) or gonderen in self.vip or ilerleme
        if icerik_sayilir:
            if TARIH_DESEN.search(metin):
                ekle("tarih", +25)
            for ad, agirlik, kalip in artilar:
                if ad.startswith("is-basvurusu"):
                    continue          # yukarıda ele alındı
                if kalip and kalip.search(metin):
                    ekle(ad, agirlik)
            if SORU_DESEN.search(konu) or SORU_DESEN.search(govde[:600]):
                ekle("soru", +15)

        # Hafıza en sonda: sistemin kullanıcı hakkında öğrendikleri. Diğer
        # sinyallerden sonra gelir çünkü onların hepsi ya açık tercih ya da
        # doğrudan davranış; hafıza türetilmiş bir tahmin.
        hafiza_toplam = 0

        def hafiza_ekle(ad, etki):
            """Tavanı aşmayacak kadarını uygular; aşarsa kırpar."""
            nonlocal hafiza_toplam
            kalan = HAFIZA_TAVANI - abs(hafiza_toplam)
            if kalan <= 0:
                return
            etki = max(-kalan, min(kalan, etki))
            hafiza_toplam += etki
            ekle(ad, etki)

        # Sık yazışılan kişi: VIP (+40) ve yazistiginiz-kisi (+35) zaten
        # sayıldıysa tekrarlamaz — aynı ilişki iki kez ödüllendirilmemeli.
        if (gonderen and gonderen in self.hafiza_kisileri
                and gonderen not in self.vip
                and gonderen not in self.yazistiklarim):
            hafiza_ekle("sik-yazisilan", self.hafiza_kisileri[gonderen])

        # İçerik sinyalleriyle aynı kural: bültende geçen "mimarlık" sizin
        # işiniz değil, pazarlama metnidir.
        if icerik_sayilir:
            for anahtar, agirlik, kalip in self.hafiza_kaliplari:
                if kalip and kalip.search(metin):
                    hafiza_ekle("hafiza:" + anahtar, agirlik)

        return {
            "ham_skor": puan,
            "skor": max(0, min(100, puan)),
            "sinyaller": sinyaller,
            "kategori": self.kategori(puan),
        }

    @staticmethod
    def kategori(ham):
        if ham >= ESIK_AKSIYON:
            return "aksiyon"
        if ham >= ESIK_BILGI:
            return "bilgi"
        return "gurultu"


def _json_oku(gorece, varsayilan=None):
    yol = os.path.join(KOK, gorece)
    if not os.path.exists(yol):
        return varsayilan
    try:
        return json.load(io.open(yol, encoding="utf-8"))
    except ValueError:
        return varsayilan


def digest_guncelle(skorlayici=None):
    """gmail.json'u skorlayıp inbox-digest.json'u yazar ve modele gidecekleri döner.

    Model çağırmaz — bu yüzden hem tarama hem canlı izleyici kullanabilir.
    Önceki taramada üretilmiş özet/aksiyon/taslak korunur; yeniden özetlenmez.

    Dönen: (digest, modele gidecek maddeler). gmail.json yoksa (None, []).
    """
    ham = _json_oku("state/raw/gmail.json")
    if not ham:
        return None, []

    # Modelin ürettiği zenginleştirme ayrı ve kalıcı bir dosyada durur; digest her
    # taramada kuraldan yeniden türetilip bununla birleştirilir. Ajanın 19 KB'lik
    # digest'i baştan yazmasına gerek kalmaz — o tek başına ~5 bin çıktı tokenıydı.
    ozetler = _json_oku("state/ozetler.json") or {}
    eski = {str(m.get("id")): m
            for m in (_json_oku("state/inbox-digest.json") or {}).get("maddeler", [])}
    digest = digest_uret(ham, skorlayici)
    for m in digest["maddeler"]:
        kaynaklar = [eski.get(str(m["id"])), ozetler.get(str(m["id"]))]
        for e in kaynaklar:
            if not isinstance(e, dict):
                continue
            for alan in ("ozet", "aksiyon", "son_tarih", "taslak", "proje"):
                if e.get(alan):
                    m[alan] = e[alan]

    yol = os.path.join(KOK, "state", "inbox-digest.json")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with io.open(yol, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)

    brifing_girdisi_yaz(digest)

    bekleyen = [m for m in digest["maddeler"]
                if m["ham_skor"] >= ESIK_BILGI and not m.get("ozet")]
    return digest, bekleyen


def brifing_girdisi_yaz(digest):
    """Modelin okuyacağı süzülmüş görünümü yazar.

    Digest'in tamamı panelin veri kaynağıdır — kullanıcı elenen maili de görebilmeli.
    Ama Çekirdek ve proje-agent'ın 30 tane iş ilanı bültenini okumasına gerek yok;
    onlar yalnızca eşiği geçenleri görür. Elenenler tek bir sayı olarak geçer.
    """
    onemli = [m for m in digest["maddeler"] if m["ham_skor"] >= ESIK_BILGI]
    girdi = {
        "guncelleme": digest.get("guncelleme"),
        "toplam_okunmamis": digest.get("toplam_okunmamis"),
        "taranan_mail": len(digest["maddeler"]),
        "elenen_dusuk_oncelikli": len(digest["maddeler"]) - len(onemli),
        "maddeler": [{k: m.get(k) for k in
                      ("id", "gonderen", "konu", "tarih", "ham_skor", "kategori",
                       "ozet", "aksiyon", "son_tarih", "taslak", "proje")}
                     for m in onemli],
    }
    yol = os.path.join(KOK, "state", "brifing-girdisi.json")
    with io.open(yol, "w", encoding="utf-8") as f:
        json.dump(girdi, f, ensure_ascii=False, indent=2)
    return girdi


def digest_uret(ham_veri, skorlayici=None):
    """Ham gmail.json verisinden kural tabanlı inbox-digest.json gövdesi üretir."""
    s = skorlayici or Skorlayici()
    maddeler = []
    for m in ham_veri.get("mailler", []):
        r = s.skorla(m)
        maddeler.append({
            "id": m.get("id"),
            "gonderen": m.get("gonderen"),
            "konu": m.get("konu"),
            "tarih": m.get("tarih"),
            "thread_id": m.get("thread_id"),
            "ekler": m.get("ekler") or [],
            "skor": r["skor"],
            "ham_skor": r["ham_skor"],
            "sinyaller": r["sinyaller"],
            "kategori": r["kategori"],
            "ozet": None,        # modelin dolduracağı alanlar
            "aksiyon": None,
            "son_tarih": None,
            "taslak": None,
        })
    maddeler.sort(key=lambda x: -x["ham_skor"])
    return {
        "guncelleme": ham_veri.get("cekildi"),
        "toplam_okunmamis": ham_veri.get("toplam_okunmamis"),
        "maddeler": maddeler,
    }
