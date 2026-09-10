# -*- coding: utf-8 -*-
"""Vellum bildirim kartı — Fluent 2 dizgisinde masaüstü pop-up'ı.

Windows'un kendi bildirim kutusu yerine kendi penceremizi çizeriz: beyaz yüzey,
Segoe UI, solda marka şeridi — panelle aynı Fluent 2 dilini konuşur.

Not: Tkinter'da `overrideredirect` pencerenin köşesi yuvarlatılamaz, o yüzden kart
dik köşeli kalır. Fluent'in geri kalanı (renk, tipografi, boşluk) uygulanır.

Ayrı bir süreç olarak çalışır. Tkinter'ın tüm çağrıları tek bir iş parçacığında
kalmak zorunda; sunucunun içinden çağırmak yerine kısa ömürlü bir süreç açmak
hem daha sağlam hem daha basit — kart kapanınca süreç de biter.

Kullanım (izleyici bunu kendi çağırır):
    python scripts/kart.py --ust "ÖNEMLİ MAİL" --baslik "Mülakat daveti" \
                           --alt "İK <ik@x.com>" --rozet 120
    python scripts/kart.py --ust "HATIRLATMA" --baslik "Mülakat" --alt "Yarın 14:00'te"
"""

import argparse
import sys
import webbrowser

# Fluent 2 paleti — panel/_ds/fluent2/tokens.css ile aynı değerler.
KAGIT = "#ffffff"      # colorNeutralBackground1
MUREKKEP = "#242424"   # colorNeutralForeground1
SOLGUN = "#616161"     # colorNeutralForeground3
MARKA = "#0f6cbd"      # colorBrandBackground
MARKA_KOYU = "#0f548c"
CIZGI = "#d1d1d1"      # colorNeutralStroke1

PANEL_ADRESI = "http://127.0.0.1:8787"
SURE_MS = 8000          # kart ekranda ne kadar kalır
GENISLIK, YUKSEKLIK = 380, 132
KENAR_BOSLUGU = 24      # ekran kenarına uzaklık


def yazitipi(kok, boyut, kalin=False):
    """Segoe UI varsa onu, yoksa sistemin sans yazıtipini kullanır."""
    from tkinter import font
    mevcut = set(font.families(kok))
    for ad in ("Segoe UI Variable Text", "Segoe UI", "Segoe UI Semibold", "Arial"):
        if ad in mevcut:
            return (ad, boyut, "bold" if kalin else "normal")
    return ("TkDefaultFont", boyut, "bold" if kalin else "normal")


def kisalt(metin, n):
    metin = " ".join((metin or "").split())
    return metin if len(metin) <= n else metin[:n - 1] + "…"


def goster(baslik, alt="", ust="ÖNEMLİ MAİL", rozet="",
           sure_ms=SURE_MS, adres=PANEL_ADRESI):
    """Kartı çizer. `ust` künye satırı, `rozet` sağdaki vurgu (skor ya da tür)."""
    import tkinter as tk

    kok = tk.Tk()
    kok.withdraw()
    kart = tk.Toplevel(kok)
    kart.overrideredirect(True)          # başlık çubuğu yok
    kart.attributes("-topmost", True)
    kart.configure(bg=CIZGI)             # 1 px çerçeve görevi görür

    ekran_g = kart.winfo_screenwidth()
    ekran_y = kart.winfo_screenheight()
    x = ekran_g - GENISLIK - KENAR_BOSLUGU
    hedef_y = ekran_y - YUKSEKLIK - 64   # görev çubuğunun üstü
    kart.geometry("%dx%d+%d+%d" % (GENISLIK, YUKSEKLIK, x, ekran_y))

    govde = tk.Frame(kart, bg=KAGIT)
    govde.place(x=1, y=1, width=GENISLIK - 2, height=YUKSEKLIK - 2)

    # Solda marka şeridi — Fluent MessageBar ile aynı işaret.
    tk.Frame(govde, bg=MARKA, width=4).place(x=0, y=0, relheight=1)

    ic = tk.Frame(govde, bg=KAGIT)
    ic.place(x=17, y=13, width=GENISLIK - 36, height=YUKSEKLIK - 28)

    ust_metni = ust.upper() if ust else "VELLUM"
    ust = tk.Frame(ic, bg=KAGIT)
    ust.pack(fill="x")
    tk.Label(ust, text="VELLUM", bg=KAGIT, fg=SOLGUN,
             font=yazitipi(kok, 8, True)).pack(side="left")
    tk.Label(ust, text=ust_metni, bg=KAGIT, fg=SOLGUN,
             font=yazitipi(kok, 8)).pack(side="left", padx=(8, 0))
    if rozet:
        tk.Label(ust, text=str(rozet), bg=KAGIT, fg=MARKA_KOYU,
                 font=yazitipi(kok, 9, True)).pack(side="right")

    tk.Label(ic, text=kisalt(baslik, 62), bg=KAGIT, fg=MUREKKEP, justify="left",
             anchor="w", wraplength=GENISLIK - 44,
             font=yazitipi(kok, 12, True)).pack(fill="x", pady=(9, 0))
    tk.Label(ic, text=kisalt(alt, 52), bg=KAGIT, fg=SOLGUN, anchor="w",
             font=yazitipi(kok, 9)).pack(fill="x", pady=(4, 0))
    tk.Label(ic, text="panele git →", bg=KAGIT, fg=MARKA, anchor="w",
             font=yazitipi(kok, 9)).pack(fill="x", pady=(7, 0))

    def kapat(_=None):
        try:
            kok.destroy()
        except Exception:
            pass

    def ac(_=None):
        webbrowser.open(adres)
        kapat()

    for w in [kart, govde, ic, ust] + list(ic.winfo_children()) + list(ust.winfo_children()):
        w.bind("<Button-1>", ac)
        w.bind("<Button-3>", kapat)      # sağ tık: sessizce kapat

    # Sağ alttan yukarı kayarak girer.
    def kaydir(y):
        if y <= hedef_y:
            kart.geometry("%dx%d+%d+%d" % (GENISLIK, YUKSEKLIK, x, hedef_y))
            return
        kart.geometry("%dx%d+%d+%d" % (GENISLIK, YUKSEKLIK, x, y))
        kart.after(10, kaydir, y - 14)

    kaydir(ekran_y)
    kok.after(sure_ms, kapat)
    kok.mainloop()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--baslik", default="")
    a.add_argument("--alt", default="")
    a.add_argument("--ust", default="ÖNEMLİ MAİL")
    a.add_argument("--rozet", default="")
    a.add_argument("--sure", type=int, default=SURE_MS)
    d = a.parse_args()
    try:
        goster(d.baslik, d.alt, d.ust, d.rozet, d.sure)
    except Exception as hata:
        print("kart gosterilemedi:", hata, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
