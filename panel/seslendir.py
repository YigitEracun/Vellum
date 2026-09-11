# -*- coding: utf-8 -*-
"""Metni sese çevirir — edge-tts ile, diske cacheleyerek.

Ses Microsoft'un Türkçe neural sesiyle üretilir. Anahtar istemez, para istemez;
karşılığında internet ister. Aynı cümle iki kez söylenirse ikincisinde ağa hiç
gidilmez: üretilen mp3 `state/ses/<hash>.mp3` olarak durur.

Sessizlik hata değildir. edge-tts kurulu değilse, ağ yoksa, servis bir gün
kapanırsa `seslendir()` None döner ve panel sesi olmadan çalışmaya devam eder —
konuşma balonu yazmayı sürdürür. Sesin kaybolması konuşmayı kaybetmekten iyidir.

Kullanım:  python panel/seslendir.py "Merhaba, ben Vellum."
"""

import asyncio
import hashlib
import io
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLASOR = os.path.join(KOK, "state", "ses")

SES = "tr-TR-AhmetNeural"   # alternatifi: tr-TR-EmelNeural (kadın)
HIZ = "+8%"                 # varsayılan tempo biraz ağır kalıyor
TAVAN = 1200                # bir seferde okunacak azami karakter


# ------------------------------------------------------------------ metin

_BAGLANTI = re.compile(r"https?://\S+")
_KOD = re.compile(r"`{1,3}[^`]*`{1,3}", re.S)
_VURGU = re.compile(r"(\*{1,3}|_{1,3}|~~)")
_BASLIK = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_MADDE = re.compile(r"^\s{0,3}[-*+•]\s+", re.M)
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️]"
)
_BOSLUK = re.compile(r"[ \t]+")


def okunacak_hale_getir(metin):
    """Markdown işaretlerini ayıklar — neural ses 'yıldız yıldız' okumasın.

    Bağlantılar tamamen atılır: bir URL'nin sesli okunuşu kimsenin işine
    yaramaz, üstelik uzun olduğu için cümlenin ritmini bozar.
    """
    if not metin:
        return ""
    t = _KOD.sub(" ", metin)
    t = _BAGLANTI.sub(" ", t)
    t = _BASLIK.sub("", t)
    t = _MADDE.sub("", t)
    t = _VURGU.sub("", t)
    t = _EMOJI.sub(" ", t)
    t = t.replace("—", ", ").replace("–", ", ")
    t = _BOSLUK.sub(" ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    satirlar = [s.strip() for s in t.split("\n")]
    return "\n".join(s for s in satirlar if s).strip()


def anahtar(metin, ses=None, hiz=None):
    """Cache adı. Ses ve hız da girer: ses değişince eski mp3 kullanılmasın."""
    imza = "%s|%s|%s" % (ses or SES, hiz or HIZ, metin)
    return hashlib.sha1(imza.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------ uretim


def _uret(metin, yol, ses, hiz):
    """edge-tts'i çağırıp mp3'ü yazar. Hata yukarı taşınır."""
    import edge_tts   # burada import ediliyor: kurulu degilse panel yine acilsin

    async def calis():
        parcalar = []
        iletisim = edge_tts.Communicate(metin, ses, rate=hiz)
        async for olay in iletisim.stream():
            if olay["type"] == "audio":
                parcalar.append(olay["data"])
        return b"".join(parcalar)

    veri = asyncio.run(calis())
    if not veri:
        raise RuntimeError("edge-tts bos ses dondurdu")
    gecici = yol + ".yaziliyor"
    with open(gecici, "wb") as d:
        d.write(veri)
    os.replace(gecici, yol)   # yarim dosya cache'e girmesin


def seslendir(metin, ses=None, hiz=None):
    """Metni mp3'e çevirir, dosya yolunu döner. Üretilemezse None.

    Cache'te varsa ağa hiç gidilmez.
    """
    okunacak = okunacak_hale_getir(metin)
    if not okunacak:
        return None
    okunacak = okunacak[:TAVAN]

    ad = anahtar(okunacak, ses, hiz) + ".mp3"
    yol = os.path.join(KLASOR, ad)
    if os.path.exists(yol) and os.path.getsize(yol) > 0:
        return yol

    os.makedirs(KLASOR, exist_ok=True)
    try:
        _uret(okunacak, yol, ses or SES, hiz or HIZ)
    except Exception as hata:
        # Ses gelmemesi panelin isini bozmaz; ne oldugu gorulsun diye yazilir.
        sys.stderr.write("seslendirme basarisiz: %s: %s\n"
                         % (type(hata).__name__, hata))
        return None
    return yol


def dosya_yolu(ad):
    """Cache'teki bir mp3'ün tam yolu. Klasör dışına çıkan ad kabul edilmez."""
    temiz = os.path.basename(ad or "")
    if not re.fullmatch(r"[0-9a-f]{6,40}\.mp3", temiz):
        return None
    yol = os.path.join(KLASOR, temiz)
    return yol if os.path.isfile(yol) else None


def main(argv):
    metin = " ".join(argv[1:]) or "Merhaba, ben Vellum."
    yol = seslendir(metin)
    if not yol:
        print("ses uretilemedi")
        return 1
    print(yol, os.path.getsize(yol), "bayt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
