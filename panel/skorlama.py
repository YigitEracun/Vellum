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

PARA_DESEN = re.compile(
    r"\b(fatura|ödeme|odeme|ücret|ucret|tutar|bedel|sözleşme|sozlesme|kontrat|"
    r"teklif|fiyat|bütçe|butce|hukuk|avukat|ihtar|icra|vergi|maaş|maas|"
    r"invoice|payment|contract|billing|receipt|refund)\b", re.I)

# İş başvurusu: yalnızca "başvurun alındı" türü onaylar gürültü sayılır; şirketten
# gelen ilerleme (mülakat, teklif, sonuç) önemlidir. Ayrım gönderene değil konuya bakar.
BASVURU_ONAYI = re.compile(
    r"(başvurunuz|basvurunuz|başvurun|basvurun).{0,30}"
    r"(alınmış|alindi|alındı|iletil|ulaştı|ulasti)|"
    r"thank you for (applying|your application)|"
    r"we (have )?received your application|"
    r"application (received|submitted)|"
    r"köszönjük.{0,40}jelentkezés|"
    r"indeed (başvuru|apply|application)", re.I)

BASVURU_ILERLEME = re.compile(
    r"\b(mülakat|mulakat|görüşme|gorusme|interview|"
    r"iş teklifi|is teklifi|job offer|offer letter|"
    r"next step|move forward|shortlist|"
    r"değerlendirme sonucu|degerlendirme sonucu|olumlu|"
    r"seni?zi? (görmek|gormek) ister)\b", re.I)

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
    """config/kisiler.md içindeki VIP ve gürültü adreslerini okur."""
    yol = os.path.join(KOK, "config", "kisiler.md")
    if not os.path.exists(yol):
        return [], []
    metin = io.open(yol, encoding="utf-8", errors="replace").read()
    # Yorum satırlarındaki örnekler listeye girmemeli.
    temiz = re.sub(r"<!--.*?-->", "", metin, flags=re.S)
    return (_adresleri_ayikla(_bolum(temiz, "VIP")),
            _adresleri_ayikla(_bolum(temiz, "Gürültü")))


def _adres(metin):
    e = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", metin or "")
    return e.group(0).lower() if e else ""


class Skorlayici(object):
    """Rubriği uygular. Kullanıcı ve listeler dışarıdan verilebilir (test için)."""

    def __init__(self, kullanici=None, vip=None, gurultu=None):
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

        ilerleme = False
        if BASVURU_ONAYI.search(metin):
            # Başvuru onayı: geldiğini bilmek yeterli, aksiyon gerektirmez.
            ekle("basvuru-onayi", -40)
        elif not bulten and (BASVURU_ILERLEME.search(konu) or
                             BASVURU_ILERLEME.search(govde[:400])):
            # Bültenin gövdesinde geçen "interview" kelimesi mülakat daveti değildir.
            ekle("basvuru-ilerleme", +45)
            ilerleme = True

        # İçerik sinyalleri yalnızca size yazılmış maillerde anlamlı. Bültende geçen
        # tarih sizin son tarihiniz, geçen fiyat sizin faturanız değildir — pazarlama
        # metni bunların hepsini taşır ve toplu gönderim cezasını geri kapatırdı.
        icerik_sayilir = not (bulten or islem) or gonderen in self.vip or ilerleme
        if icerik_sayilir:
            if TARIH_DESEN.search(metin):
                ekle("tarih", +25)
            if PARA_DESEN.search(metin):
                ekle("para-sozlesme", +30)
            if SORU_DESEN.search(konu) or SORU_DESEN.search(govde[:600]):
                ekle("soru", +15)

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
