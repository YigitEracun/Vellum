# -*- coding: utf-8 -*-
"""Kullanıcı hafızası — kalıcı, append-only olgu deposu.

Sistem kullanıcıyı kullandıkça tanır: mesleği, ilgi alanları, gittiği yerler,
sık görüştüğü kişiler. Öğrenilen her şey `state/hafiza.jsonl` içinde birer satır
olarak durur; satır silinmez, unutma da bir satırdır. Takvim ve proje olay
günlüğüyle aynı mantık — "ne zamandan beri böyle biliyorsun" sorusu
cevaplanabilir kalır.

Neden `state/konular.json` değil: orası bir **ayar** dosyası, kullanıcının
bilinçli tercihleri, üzerine yazılır. Burası bir **geçmiş**. İkisi aynı dosyada
olsaydı otomatik çıkarım, elle girilmiş tercihi ezerdi.

İki yerden yazılır: sohbette asistanın `hatirla` aracı ve taramadan sonra çalışan
modelsiz sayım (`panel/sayim.py`). İki yerde okunur: skorlama (kelime ve kişi
ağırlıkları) ve asistanın sistem istemi (`ozet`).
"""

import io
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = timezone(timedelta(hours=3))
DOSYA = os.path.join(KOK, "state", "hafiza.jsonl")

TURLER = ("meslek", "ilgi", "yer", "kisi", "alistigi")
KAYNAKLAR = ("sohbet", "sayim", "elle")

# Ağırlık sınırları. Tek bir olgu ne bir maili gömebilmeli ne de tepeye
# çıkarabilmeli; toplam katkı da TAVAN ile sınırlı.
EN_AZ, EN_COK = -40, 40
TAVAN = 40

# Bayatlama: olgu silinmez ama doğrulanmazsa etkisi söner. Meslek değiştiren
# bir kullanıcının eski mesleği brifingini yönetmeye devam etmemeli.
YARILANMA = 90     # gün — ağırlık yarıya iner
SONME = 180        # gün — çeyreğine iner

OZET_SINIR = 40    # modele verilecek azami satır


def simdi():
    return datetime.now(TZ)


# --------------------------------------------------------------------- depo

def _oku_satirlar():
    if not os.path.exists(DOSYA):
        return []
    satirlar = []
    for satir in io.open(DOSYA, encoding="utf-8", errors="replace"):
        satir = satir.strip()
        if not satir:
            continue
        try:
            satirlar.append(json.loads(satir))
        except ValueError:
            continue   # bozuk satır depoyu kilitlemesin
    return satirlar


def _ekle(kayit):
    os.makedirs(os.path.dirname(DOSYA), exist_ok=True)
    with io.open(DOSYA, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def turet():
    """Satırlardan bugünkü olguları çıkarır.

    Aynı `id` için sonraki satır öncekini gölgeler; `unut` işaretlileri düşer.
    Dosyanın kendisi hiç değişmez.
    """
    son = {}
    for k in _oku_satirlar():
        kimlik = k.get("id")
        if not kimlik:
            continue
        birlesik = dict(son.get(kimlik) or {})
        birlesik.update(k)
        son[kimlik] = birlesik
    canli = [o for o in son.values()
             if not o.get("unut") and o.get("anahtar")]
    canli.sort(key=lambda o: (-int(o.get("gorulme") or 1),
                              o.get("anahtar") or ""))
    return canli


def _anahtar_ara(anahtar, tur=None):
    """Aynı olgu daha önce öğrenilmiş mi. Anahtar karşılaştırması küçük harf."""
    a = (anahtar or "").strip().lower()
    for o in turet():
        if (o.get("anahtar") or "").lower() == a and (tur is None or o.get("tur") == tur):
            return o
    return None


VARSAYILAN_AGIRLIK = {
    "meslek": 25,     # mesleğe dair mail neredeyse her zaman işe yarar
    "ilgi": 15,       # hobinin maili önemli ama işten sonra gelir
    "yer": 15,
    "kisi": 20,
    "alistigi": 10,
}


def yaz(tur, anahtar, deger, kaynak="sohbet", kelimeler=None, adres=None,
        agirlik=None):
    """Yeni olgu yazar; aynı anahtar zaten varsa onu pekiştirir.

    Pekiştirme yeni bir satırdır: `gorulme` artar, `son_gorulme` tazelenir,
    açıklama güncellenir. Böylece "kaç kez doğrulandı" sorusu cevaplanır ve
    bayatlama saati sıfırlanır.
    """
    anahtar = (anahtar or "").strip()
    if not anahtar:
        raise ValueError("Olgunun anahtarı olmalı.")
    if tur not in TURLER:
        raise ValueError("Geçersiz tür: %s" % tur)
    if kaynak not in KAYNAKLAR:
        kaynak = "sohbet"

    # Anahtarın kendisi de aranacak kelimelerden biridir: "mimarlık" olgusu
    # mailde geçen "mimarlık" sözcüğünü de yakalamalı.
    kelimeler = [k.strip().lower() for k in (kelimeler or []) if k and k.strip()]
    kelimeler.append(anahtar.lower())

    varolan = _anahtar_ara(anahtar, tur)
    an = simdi().isoformat()
    if agirlik is None:
        agirlik = varolan.get("agirlik") if varolan else VARSAYILAN_AGIRLIK.get(tur, 20)

    kayit = {
        "t": an,
        "id": varolan["id"] if varolan else ("h_" + uuid.uuid4().hex[:8]),
        "tur": tur,
        "anahtar": anahtar,
        "deger": (deger or "").strip(),
        "kaynak": kaynak,
        "kelimeler": sorted(set(kelimeler + list(
            (varolan or {}).get("kelimeler") or []))),
        "adres": (adres or "").strip().lower() or None,
        "agirlik": max(EN_AZ, min(EN_COK, int(agirlik))),
        "gorulme": int((varolan or {}).get("gorulme") or 0) + 1,
        "son_gorulme": an,
    }
    _ekle(kayit)
    return kayit


def unut(kimlik):
    """Olguyu düşürür. Özgün satır durur, üstüne unutma satırı yazılır."""
    if not any(o.get("id") == kimlik for o in _oku_satirlar()):
        return False
    _ekle({"t": simdi().isoformat(), "id": kimlik, "unut": True})
    return True


def agirlik_degistir(kimlik, agirlik):
    """Kullanıcı bir olgunun ağırlığını elle ayarlar."""
    mevcut = next((o for o in turet() if o.get("id") == kimlik), None)
    if not mevcut:
        return False
    kayit = dict(mevcut)
    kayit["t"] = simdi().isoformat()
    kayit["agirlik"] = max(EN_AZ, min(EN_COK, int(agirlik)))
    kayit["kaynak"] = "elle"     # elle ayarlanan ağırlığı sayım ezmesin
    _ekle(kayit)
    return True


# ---------------------------------------------------------------- bayatlama

def _gun_farki(iso):
    if not iso:
        return 0
    try:
        return max(0, (simdi() - datetime.fromisoformat(iso)).days)
    except ValueError:
        return 0


def guncel_agirlik(olgu):
    """Bayatlamayı uygulanmış ağırlık.

    Elle ayarlanan ağırlık bayatlamaz: kullanıcı bilerek söylemiştir.
    """
    agirlik = int(olgu.get("agirlik") or 0)
    if olgu.get("kaynak") == "elle":
        return agirlik
    yas = _gun_farki(olgu.get("son_gorulme") or olgu.get("t"))
    if yas >= SONME:
        agirlik = agirlik // 4
    elif yas >= YARILANMA:
        agirlik = agirlik // 2
    return agirlik


# ----------------------------------------------------------------- okuyanlar

def skorlama_girdisi():
    """Kural motorunun kullanacağı biçim.

    `kelimeler`: metinde aranacak gövdeler ve ağırlıkları.
    `kisiler`:  adres -> ağırlık.
    Ağırlığı sıfıra düşmüş (tamamen bayatlamış) olgular hiç gönderilmez.
    """
    kelimeler, kisiler = [], {}
    for o in turet():
        ag = guncel_agirlik(o)
        if not ag:
            continue
        if o.get("adres"):
            kisiler[o["adres"]] = max(kisiler.get(o["adres"], 0), ag)
        for k in o.get("kelimeler") or []:
            kelimeler.append({"kelime": k, "agirlik": ag,
                              "anahtar": o.get("anahtar"), "id": o.get("id")})
    return {"kelimeler": kelimeler, "kisiler": kisiler}


_BASLIK = {
    "meslek": "İşi",
    "ilgi": "İlgi alanları",
    "yer": "Yerler",
    "kisi": "Sık görüştüğü kişiler",
    "alistigi": "Alışkanlıkları",
}


def ozet():
    """Modele verilecek kısa metin. Ham satırlar değil, yalnızca özü gider."""
    olgular = [o for o in turet() if guncel_agirlik(o)]
    if not olgular:
        return ""
    satirlar = ["Kullanıcı hakkında bildiklerin (kullandıkça öğrenildi):"]
    for tur in TURLER:
        grup = [o for o in olgular if o.get("tur") == tur]
        if not grup:
            continue
        satirlar.append("%s:" % _BASLIK.get(tur, tur))
        for o in grup[:12]:
            metin = o.get("deger") or o.get("anahtar")
            if o.get("adres"):
                metin += " (%s)" % o["adres"]
            satirlar.append("- " + metin)
    satirlar.append(
        "Bunları sohbette doğal biçimde kullan, listeyi kullanıcıya okuma. "
        "Yanlış bir şey olduğunu söylerse unut aracıyla düş."
    )
    return "\n".join(satirlar[:OZET_SINIR])


def gruplu():
    """Panelin Hafıza sekmesi için: türlere göre, güncel ağırlıklarıyla."""
    cikti = []
    olgular = turet()
    for tur in TURLER:
        grup = [dict(o, guncel_agirlik=guncel_agirlik(o),
                     bayat=guncel_agirlik(o) != int(o.get("agirlik") or 0))
                for o in olgular if o.get("tur") == tur]
        if grup:
            cikti.append({"tur": tur, "baslik": _BASLIK.get(tur, tur),
                          "olgular": grup})
    return cikti
