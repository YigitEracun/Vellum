# -*- coding: utf-8 -*-
"""Veriden sayarak öğrenme — model çağırmaz, para harcamaz.

Hafızanın iki kaynağından biri. Diğeri (sohbet) çıkarım yapar; bu modül
yalnızca sayar: kiminle kaç kez yazışıldı, hangi ad kaç kez tekrarlandı.
Sayı çıkarım değildir, o yüzden doğrudan uygulanabilir.

Kasten dar tutuldu. Mail gövdelerinden serbest anahtar kelime madenciliği
yapmıyoruz: Türkçe ek sorununu bir kez yaşadık ve serbest madencilik çöp
üretir. Yalnızca (1) yazışma sıklığı ve (2) eşiği geçmiş maillerin
konularında tekrar eden özel adlar sayılır.

Taramanın sonunda çalışır (`panel/sunucu.py`).
"""

import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kisi esikleri
EN_AZ_YAZISMA = 3      # bu kadar yazışmadan azı tesadüf sayılır
DOYUM = 20             # bu sayıdan sonra ağırlık artmaz

# Ad esikleri
EN_AZ_TEKRAR = 3       # ad en az bu kadar mailde geçmeli
EN_AZ_GONDERICI = 2    # ve en az bu kadar farklı göndericiden
AD_ESIGI = 40          # yalnızca bu ham skoru geçen maillerin konuları
AD_AGIRLIK = 10        # sabit ve düşük: tahminin en zayıf olduğu yer burası

# Konu satırında sık geçen ama kimseye ait olmayan büyük harfli sözcükler.
_ELENEN_ADLAR = {
    "Re", "Fwd", "Fw", "Ynt", "Ilet", "İlet", "Merhaba", "Selam", "Sayın",
    "Bilgi", "Hakkında", "Konulu", "Acil", "Önemli", "Toplantı", "Görüşme",
    "Mülakat", "Davet", "Teklif", "Fatura", "Sipariş", "Kargo", "Hesap",
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
    "Eylül", "Ekim", "Kasım", "Aralık",
}

_BUYUK_HARF = "A-ZÇĞİÖŞÜ"
_AD_DESEN = re.compile(r"\b[%s][a-zçğıöşü]{2,}\b" % _BUYUK_HARF)
_OTOMATIK = re.compile(
    r"(noreply|no-reply|donotreply|bounce|mailer|notification|bildirim|"
    r"bulten|newsletter|info@|destek@|support@)", re.I)


def _adres(metin):
    e = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", metin or "")
    return e.group(0).lower() if e else ""


def kisiler(gonderilen, maddeler):
    """Sık yazışılan kişiler.

    `gonderilen`: {adres: kaç kez siz yazdınız} — gönderilenler klasöründen.
    `maddeler`:   digest kayıtları — gelen tarafı buradan sayılır.

    Giden yazışma gelenden ağır basar: bir bültenden yüz mail almak o adresi
    önemli yapmaz, ama ona bir kez yazmış olmanız yapar. O yüzden gelen taraf
    yarım puanla sayılır ve otomatik adresler hiç sayılmaz.
    """
    sayac = {}
    for adres, n in (gonderilen or {}).items():
        a = (adres or "").lower()
        if a and not _OTOMATIK.search(a):
            sayac[a] = sayac.get(a, 0) + int(n)

    for m in maddeler or []:
        if m.get("toplu"):
            continue
        a = _adres(m.get("gonderen", ""))
        if not a or _OTOMATIK.search(a):
            continue
        # Gelen tarafı yalnızca daha önce yazıştığınız adresler için sayılır:
        # tek taraflı gelen yığın, ilişkiyi göstermez.
        if a in sayac:
            sayac[a] += 0.5

    import hafiza
    taban = hafiza.VARSAYILAN_AGIRLIK["kisi"]
    cikti = []
    for adres, n in sayac.items():
        if n < EN_AZ_YAZISMA:
            continue
        # taban .. taban+5 arası, doyuma doğru.
        oran = min(1.0, (n - EN_AZ_YAZISMA) / float(DOYUM))
        cikti.append({
            "adres": adres,
            "sayi": round(n, 1),
            "agirlik": int(round(taban + 5 * oran)),
        })
    cikti.sort(key=lambda k: -k["sayi"])
    return cikti


def adlar(maddeler):
    """Eşiği geçen maillerin konularında tekrar eden özel adlar.

    Tek bir göndericinin imzasındaki sözcük "önemli kavram" değildir; o yüzden
    farklı gönderici şartı var.
    """
    gorulme = {}
    for m in maddeler or []:
        if m.get("toplu"):
            continue
        try:
            skor = int(m.get("ham_skor") or m.get("skor") or 0)
        except (TypeError, ValueError):
            skor = 0
        if skor < AD_ESIGI:
            continue
        gonderen = _adres(m.get("gonderen", ""))
        for ad in set(_AD_DESEN.findall(m.get("konu") or "")):
            if ad in _ELENEN_ADLAR:
                continue
            kayit = gorulme.setdefault(ad, {"sayi": 0, "gonderenler": set()})
            kayit["sayi"] += 1
            if gonderen:
                kayit["gonderenler"].add(gonderen)

    cikti = [{"ad": ad, "sayi": k["sayi"],
              "gonderici": len(k["gonderenler"]), "agirlik": AD_AGIRLIK}
             for ad, k in gorulme.items()
             if k["sayi"] >= EN_AZ_TEKRAR and len(k["gonderenler"]) >= EN_AZ_GONDERICI]
    cikti.sort(key=lambda k: -k["sayi"])
    return cikti


def calistir(gonderilen=None, maddeler=None):
    """Sayımı yapar ve sonucu hafızaya yazar. Taramanın sonunda çağrılır.

    Elle ayarlanmış ağırlığa dokunmaz: `hafiza.yaz` var olan olgunun ağırlığını
    korur, sayım yalnızca `gorulme` sayacını ve tazeliği günceller.
    """
    import hafiza

    if gonderilen is None:
        gonderilen = _gonderilenleri_oku()
    if maddeler is None:
        maddeler = _digest_oku()

    yazilan = 0
    for k in kisiler(gonderilen, maddeler):
        ad = k["adres"].split("@")[0]
        hafiza.yaz("kisi", ad, "%s ile sık yazışıyor (%s yazışma)"
                   % (ad, k["sayi"]), kaynak="sayim", adres=k["adres"],
                   agirlik=k["agirlik"])
        yazilan += 1
    for a in adlar(maddeler):
        hafiza.yaz("ilgi", a["ad"],
                   "Maillerde tekrar eden bir ad (%d kez, %d göndericiden)"
                   % (a["sayi"], a["gonderici"]),
                   kaynak="sayim", kelimeler=[a["ad"]], agirlik=a["agirlik"])
        yazilan += 1
    return yazilan


def _gonderilenleri_oku():
    """state/raw/yazistiklarim.json — sayaç varsa onu, yoksa listeyi kullanır."""
    import io
    import json
    yol = os.path.join(KOK, "state", "raw", "yazistiklarim.json")
    if not os.path.exists(yol):
        return {}
    try:
        d = json.load(io.open(yol, encoding="utf-8"))
    except ValueError:
        return {}
    sayilar = d.get("sayilar")
    if isinstance(sayilar, dict) and sayilar:
        return sayilar
    # Eski biçim: yalnızca adres listesi. Her adres bir kez sayılır; eşiği
    # geçmezler ama dosya bir sonraki çekimde sayaçlı hâle gelir.
    return {a: 1 for a in (d.get("adresler") or [])}


def _digest_oku():
    import io
    import json
    yol = os.path.join(KOK, "state", "inbox-digest.json")
    if not os.path.exists(yol):
        return []
    try:
        return (json.load(io.open(yol, encoding="utf-8")) or {}).get("maddeler", [])
    except ValueError:
        return []
