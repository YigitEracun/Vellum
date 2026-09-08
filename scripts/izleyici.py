# -*- coding: utf-8 -*-
"""Canlı mail izleyicisi — gün içinde gelen önemli maili bildirir.

Model çağırmaz. Yeni maili kural motoruyla puanlar, eşiği geçerse masaüstü
bildirimi gönderir ve `state/bildirimler.jsonl` dosyasına satır ekler. Özet ve
taslak, siz panelden isteyince üretilir — böylece gün boyu izleme bedava kalır.

`imaplib` bu Python sürümünde IDLE desteklemediği için yoklama kullanılır; IMAP
sorgusu ücretsiz olduğundan tek maliyeti birkaç saniyelik bağlantıdır.

Kullanım:
    python scripts/izleyici.py            sürekli izler
    python scripts/izleyici.py --tek      bir tur çalışır ve çıkar (sınama için)
"""

import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))
sys.path.insert(0, os.path.join(KOK, "scripts"))

import gmail_fetch  # noqa: E402
import skorlama  # noqa: E402

ARALIK = 60          # saniye
ESIK = 40            # ham skor: bunun üstü bildirilir
BILDIRIM_DOSYASI = os.path.join(KOK, "state", "bildirimler.jsonl")
SON_UID_DOSYASI = os.path.join(KOK, "state", "raw", "son_uid.txt")


# ----------------------------------------------------------------- bildirim

# PowerShell'in kendi bildirim API'si; ek modül gerektirmez. AppId olarak
# sistemde kayıtlı PowerShell kimliği kullanılır, aksi halde bildirim çıkmaz.
_TOAST_PS = r'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] | Out-Null
$sablon = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$metinler = $sablon.GetElementsByTagName("text")
$metinler.Item(0).AppendChild($sablon.CreateTextNode($env:VELLUM_BASLIK)) | Out-Null
$metinler.Item(1).AppendChild($sablon.CreateTextNode($env:VELLUM_GOVDE)) | Out-Null
$bildirim = [Windows.UI.Notifications.ToastNotification]::new($sablon)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
).Show($bildirim)
'''


def _toast(baslik, govde):
    """Windows'un kendi bildirim kutusu. Kart açılamazsa yedek yol."""
    ortam = dict(os.environ, VELLUM_BASLIK=baslik[:120], VELLUM_GOVDE=govde[:250])
    try:
        s = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _TOAST_PS],
            env=ortam, capture_output=True, timeout=20)
        if s.returncode != 0:
            return False, (s.stderr or b"").decode("utf-8", "replace").strip()[:200]
        return True, ""
    except Exception as hata:
        return False, str(hata)


def bildir(baslik, govde, skor="", kimden="", konu=""):
    """Broadsheet kartını açar. Kart çizilemezse Windows bildirimine düşer.

    Kart ayrı bir süreçte açılır: Tkinter'ın çağrıları tek iş parçacığında
    kalmalı, sunucunun içinden pencere açmak kırılgan olurdu. Süreç beklenmez —
    kart 8 saniye yaşar, izleyici bu sırada yoluna devam eder.
    """
    kart = os.path.join(KOK, "scripts", "kart.py")
    yorumlayici = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(yorumlayici):
        yorumlayici = sys.executable
    try:
        subprocess.Popen([yorumlayici, kart, "--skor", str(skor),
                          "--kimden", kimden or "", "--konu", konu or baslik],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as hata:
        tamam, ikinci = _toast(baslik, govde)
        return tamam, ("kart acilamadi (%s); toast: %s" % (hata, ikinci or "gonderildi"))


# -------------------------------------------------------------------- durum

def son_uid_oku():
    if not os.path.exists(SON_UID_DOSYASI):
        return 0
    try:
        return int(io.open(SON_UID_DOSYASI, encoding="utf-8").read().strip() or 0)
    except ValueError:
        return 0


def son_uid_yaz(uid):
    os.makedirs(os.path.dirname(SON_UID_DOSYASI), exist_ok=True)
    io.open(SON_UID_DOSYASI, "w", encoding="utf-8").write(str(uid))


def bildirim_ekle(kayit):
    os.makedirs(os.path.dirname(BILDIRIM_DOSYASI), exist_ok=True)
    with io.open(BILDIRIM_DOSYASI, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


# ------------------------------------------------------------ sisteme dusur

def sisteme_dusur(yeniler):
    """Yeni maili ham veriye, kalıcı arşive ve digest'e işler.

    Bildirim tek başına yetmez: mail geldiği anda sistemin içinde de olmalı ki
    Posta bölümünde görünsün, tıklanıp okunabilsin, bir sonraki tarama onu
    yeniden çekmek zorunda kalmasın.

    Model çağrılmaz — yalnızca kural motoru. Özet ve taslak, tarama sırasında
    ya da siz panelden isteyince üretilir.
    """
    yol = os.path.join(KOK, "state", "raw", "gmail.json")
    try:
        ham = json.load(io.open(yol, encoding="utf-8"))
    except (IOError, ValueError):
        return
    if not isinstance(ham.get("mailler"), list):
        return

    varolan = {str(m.get("id")) for m in ham["mailler"]}
    eklenen = [m for m in yeniler if str(m.get("id")) not in varolan]
    if not eklenen:
        return

    ham["mailler"] = eklenen + ham["mailler"]
    ham["cekildi"] = datetime.now(gmail_fetch.TZ).isoformat()
    with io.open(yol, "w", encoding="utf-8") as f:
        json.dump(ham, f, ensure_ascii=False, indent=2)

    try:
        gmail_fetch.arsivle(ham)          # kalıcı arşiv: aynı UID iki kez yazılmaz
        skorlama.digest_guncelle()        # Posta listesi anında güncellensin
    except Exception as hata:
        print("sisteme dusurme kismi hata:", hata)


# --------------------------------------------------------------------- tur

def tur(skorlayici=None, sessiz=False):
    """Bir yoklama turu: yeni mailleri çeker, puanlar, eşiği geçeni bildirir.

    Dönen: (yeni mail sayısı, bildirilen kayıtlar)
    """
    s = skorlayici or skorlama.Skorlayici()
    onceki = son_uid_oku()
    yeniler = gmail_fetch.cek_uid_ustu(onceki)
    if not yeniler:
        return 0, []

    son_uid_yaz(max(int(m["id"]) for m in yeniler))
    sisteme_dusur(yeniler)

    bildirilenler = []
    for m in yeniler:
        r = s.skorla(m)
        if r["ham_skor"] < ESIK:
            continue
        kayit = {
            "id": m["id"], "gonderen": m.get("gonderen"), "konu": m.get("konu"),
            "tarih": m.get("tarih"), "ham_skor": r["ham_skor"],
            "sinyaller": r["sinyaller"], "goruldu": False,
            "bildirildi": datetime.now(gmail_fetch.TZ).isoformat(),
        }
        bildirim_ekle(kayit)
        bildirilenler.append(kayit)
        if not sessiz:
            tamam, hata = bildir(
                "Vellum — önemli mail (%d)" % r["ham_skor"],
                "%s\n%s" % (m.get("gonderen", ""), m.get("konu", "")),
                skor=r["ham_skor"], kimden=m.get("gonderen", ""),
                konu=m.get("konu", ""))
            if not tamam:
                print("bildirim gonderilemedi:", hata)
    return len(yeniler), bildirilenler


def main():
    tek = "--tek" in sys.argv
    print("izleyici basladi (aralik %d sn, esik %d). son gorulen uid: %d"
          % (ARALIK, ESIK, son_uid_oku()))
    while True:
        try:
            sayi, bildirilen = tur()
            if sayi:
                print("%s  %d yeni mail, %d bildirim"
                      % (datetime.now().strftime("%H:%M:%S"), sayi, len(bildirilen)))
                for b in bildirilen:
                    print("   %4d  %s — %s" % (b["ham_skor"], b["gonderen"], b["konu"]))
        except Exception as hata:
            print("tur hatasi (izleyici devam ediyor):", hata)
        if tek:
            return
        time.sleep(ARALIK)


if __name__ == "__main__":
    main()
