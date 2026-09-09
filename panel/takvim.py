# -*- coding: utf-8 -*-
"""Takvim etkinlikleri — append-only depo ve türetme.

`state/takvim.jsonl` yalnızca satır ekleyerek büyür. Bir etkinlik silinmez:
düzeltme aynı `id` ile yeni satır, kaldırma `iptal: true` satırıdır. Projenin
olay günlüğüyle aynı mantık — "bu toplantı neden vardı" sorusu cevaplanabilir
kalır.

Kaynak iki türlüdür: mailden çıkarılan etkinlikler (`kaynak: "mail:<id>"`) ve
elle eklenenler (`kaynak: "elle"`). Google Takvim bağlandığında üçüncü bir
kaynak olarak aynı depoya değil, ayrı okunup görünümde birleştirilecek.
"""

import io
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = timezone(timedelta(hours=3))
DOSYA = os.path.join(KOK, "state", "takvim.jsonl")

TURLER = ("mulakat", "toplanti", "gorusme", "son_tarih", "diger")


def simdi():
    return datetime.now(TZ)


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


def _yaz(kayit):
    os.makedirs(os.path.dirname(DOSYA), exist_ok=True)
    with io.open(DOSYA, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def turet():
    """Satırlardan güncel etkinlik listesini türetir.

    Aynı `id` için sonraki satır öncekini gölgeler; `iptal` işaretli olanlar
    listeye girmez. Dosyanın kendisi hiç değişmez.
    """
    son = {}
    for k in _oku_satirlar():
        kimlik = k.get("id")
        if not kimlik:
            continue
        onceki = son.get(kimlik) or {}
        birlesik = dict(onceki)
        birlesik.update(k)
        son[kimlik] = birlesik
    canli = [e for e in son.values() if not e.get("iptal") and e.get("baslangic")]
    canli.sort(key=lambda e: e["baslangic"])
    return canli


def _gun(iso):
    """ISO metninden gün anahtarı (YYYY-AA-GG). Saat taşımayan değerleri de kabul eder."""
    return (iso or "")[:10]


def etkinlikler(baslangic=None, bitis=None):
    """Verilen gün aralığındaki etkinlikler (sınırlar dahil)."""
    hepsi = turet()
    if baslangic:
        hepsi = [e for e in hepsi if _gun(e["baslangic"]) >= _gun(baslangic)]
    if bitis:
        hepsi = [e for e in hepsi if _gun(e["baslangic"]) <= _gun(bitis)]
    return hepsi


def pencere(geri=60, ileri=120):
    """Panelin ay değiştirebilmesi için yeterli aralık."""
    s = simdi()
    return etkinlikler((s - timedelta(days=geri)).isoformat(),
                       (s + timedelta(days=ileri)).isoformat())


def kaynak_var_mi(kaynak):
    """Bu kaynaktan (örn. mail:6550) daha önce etkinlik yazılmış mı.

    İptal edilmiş olsa bile True döner: kullanıcı bir etkinliği kaldırdıysa,
    sonraki tarama onu geri getirmemeli.
    """
    return any(k.get("kaynak") == kaynak for k in _oku_satirlar())


def ekle(baslik, baslangic, saatli=True, yer=None, tur="diger",
         kaynak="elle", kimlik=None):
    """Yeni etkinlik ekler ve kaydı döner."""
    baslik = (baslik or "").strip()
    if not baslik:
        raise ValueError("Etkinliğin başlığı olmalı.")
    if not baslangic:
        raise ValueError("Etkinliğin başlangıcı olmalı.")
    kayit = {
        "t": simdi().isoformat(),
        "id": kimlik or ("evt_" + uuid.uuid4().hex[:8]),
        "baslik": baslik,
        "baslangic": baslangic,
        "saatli": bool(saatli),
        "yer": yer or None,
        "tur": tur if tur in TURLER else "diger",
        "kaynak": kaynak,
        "iptal": False,
    }
    _yaz(kayit)
    return kayit


def iptal_et(kimlik):
    """Etkinliği kaldırır. Özgün satır durur, üstüne iptal satırı yazılır."""
    if not any(k.get("id") == kimlik for k in _oku_satirlar()):
        return False
    _yaz({"t": simdi().isoformat(), "id": kimlik, "iptal": True})
    return True


def mailden_ekle(mail_id, etkinlik):
    """mail-agent'ın ürettiği etkinliği takvime düşürür.

    Aynı mail iki taramada da görülse etkinlik bir kez girer. Ajanın uydurmasına
    karşı en temel kontroller burada: başlık ve geçerli bir başlangıç şart.
    """
    if not isinstance(etkinlik, dict):
        return None
    kaynak = "mail:%s" % mail_id
    if kaynak_var_mi(kaynak):
        return None
    baslangic = (etkinlik.get("baslangic") or "").strip()
    try:
        datetime.strptime(baslangic[:10], "%Y-%m-%d")
    except ValueError:
        return None      # "gelecek hafta" gibi bir metin takvime giremez

    if len(baslangic) == 10:
        # Yalnızca gün verilmiş (2026-09-13): gün boyu etkinlik say.
        # fromisoformat bunu kabul eder, o yüzden ayrımı uzunluktan yapıyoruz.
        baslangic += "T09:00:00+03:00"
        etkinlik = dict(etkinlik, saatli=False)
    else:
        try:
            datetime.fromisoformat(baslangic.replace("Z", "+00:00"))
        except ValueError:
            return None
    return ekle(
        baslik=etkinlik.get("baslik") or "(başlıksız)",
        baslangic=baslangic,
        saatli=etkinlik.get("saatli", True),
        yer=etkinlik.get("yer"),
        tur=etkinlik.get("tur") or "diger",
        kaynak=kaynak,
    )
