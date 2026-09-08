# -*- coding: utf-8 -*-
"""Vellum bildirim kartı — Broadsheet dizgisinde masaüstü pop-up'ı.

Windows'un kendi bildirim kutusu yerine kendi penceremizi çizeriz: kağıt zemin,
Source Serif, camgöbeği şerit. Panelle aynı dili konuşur.

Ayrı bir süreç olarak çalışır. Tkinter'ın tüm çağrıları tek bir iş parçacığında
kalmak zorunda; sunucunun içinden çağırmak yerine kısa ömürlü bir süreç açmak
hem daha sağlam hem daha basit — kart kapanınca süreç de biter.

Kullanım (izleyici bunu kendi çağırır):
    python scripts/kart.py --skor 100 --kimden "İK <ik@x.com>" --konu "Mülakat daveti"
"""

import argparse
import sys
import webbrowser

# Broadsheet paleti — panel/_ds/broadsheet/styles.css ile aynı değerler.
KAGIT = "#f8f4f4"
MUREKKEP = "#2d2b2b"
SOLGUN = "#605d5d"
CAMGOBEGI = "#006786"
MAGENTA = "#d6006c"
CIZGI = "#d7d3d3"

PANEL_ADRESI = "http://127.0.0.1:8787"
SURE_MS = 8000          # kart ekranda ne kadar kalır
GENISLIK, YUKSEKLIK = 380, 132
KENAR_BOSLUGU = 24      # ekran kenarına uzaklık


def yazitipi(kok, boyut, kalin=False):
    """Source Serif varsa onu, yoksa sistemin serif yazıtipini kullanır."""
    from tkinter import font
    mevcut = set(font.families(kok))
    for ad in ("Source Serif 4", "Source Serif Pro", "Georgia", "Times New Roman"):
        if ad in mevcut:
            return (ad, boyut, "bold" if kalin else "normal")
    return ("TkDefaultFont", boyut, "bold" if kalin else "normal")


def kisalt(metin, n):
    metin = " ".join((metin or "").split())
    return metin if len(metin) <= n else metin[:n - 1] + "…"


def goster(skor, kimden, konu, sure_ms=SURE_MS, adres=PANEL_ADRESI):
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

    # Solda camgöbeği şerit — panelde de kutular böyle işaretleniyor.
    tk.Frame(govde, bg=CAMGOBEGI, width=3).place(x=0, y=0, relheight=1)

    ic = tk.Frame(govde, bg=KAGIT)
    ic.place(x=17, y=13, width=GENISLIK - 36, height=YUKSEKLIK - 28)

    ust = tk.Frame(ic, bg=KAGIT)
    ust.pack(fill="x")
    tk.Label(ust, text="VELLUM", bg=KAGIT, fg=SOLGUN,
             font=yazitipi(kok, 8, True)).pack(side="left")
    tk.Label(ust, text="ÖNEMLİ MAİL", bg=KAGIT, fg=SOLGUN,
             font=yazitipi(kok, 8)).pack(side="left", padx=(8, 0))
    tk.Label(ust, text=str(skor), bg=KAGIT, fg=MAGENTA,
             font=yazitipi(kok, 9, True)).pack(side="right")

    tk.Label(ic, text=kisalt(konu, 62), bg=KAGIT, fg=MUREKKEP, justify="left",
             anchor="w", wraplength=GENISLIK - 44,
             font=yazitipi(kok, 12, True)).pack(fill="x", pady=(9, 0))
    tk.Label(ic, text=kisalt(kimden, 52), bg=KAGIT, fg=SOLGUN, anchor="w",
             font=yazitipi(kok, 9)).pack(fill="x", pady=(4, 0))
    tk.Label(ic, text="panele git →", bg=KAGIT, fg=CAMGOBEGI, anchor="w",
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
    a.add_argument("--skor", default="")
    a.add_argument("--kimden", default="")
    a.add_argument("--konu", default="")
    a.add_argument("--sure", type=int, default=SURE_MS)
    d = a.parse_args()
    try:
        goster(d.skor, d.kimden, d.konu, d.sure)
    except Exception as hata:
        print("kart gosterilemedi:", hata, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
