# Mail önem skorlaması

0–100 arası skor. Taban 30, aşağıdaki sinyaller eklenir/çıkarılır.

| Sinyal | Etki |
|---|---|
| Gönderen `kisiler.md` VIP listesinde | +40 |
| Doğrudan sana yazılmış (To: sadece sen) | +20 |
| CC / toplu gönderim | −15 |
| İçinde tarih veya son tarih geçiyor | +25 |
| Para, fatura, sözleşme, hukuki konu | +30 |
| Thread'de son mesaj karşı taraftan, sıra sende | +20 |
| Soru işareti içeren doğrudan soru var | +15 |
| Bülten / pazarlama / otomatik bildirim | −50 |
| Gönderen `kisiler.md` gürültü listesinde | −40 |
| 30 günden eski | −10 |

## Ham skor ve gösterilen skor

Sinyallerin toplamı 100'ü aşabilir. **Ham toplamı `ham_skor` alanında sakla**, gösterilen
`skor` alanını 0–100 aralığına kırp.

**Sıralama daima `ham_skor`'a göre yapılır.** Aksi halde üst uçtaki maddeler 100'e sıkışır
ve aralarında ayrım kalmaz — 140 puanlık bir sözleşme maili ile 105 puanlık bir fatura
maili aynı görünür.

## Eşikler

| Ham skor | Davranış |
|---|---|
| ≥ 70 | Brifingin başında, ŞİMDİ bölümünde, aksiyon maddesi olarak |
| 40–69 | BİLGİN OLSUN bölümünde tek satır |
| < 40 | Yalnızca toplam sayı olarak ("47 düşük öncelikli mail") |

## Kalibrasyon dönemi

İlk iki hafta hiçbir mail arşivlenmez, etiketlenmez, okundu işaretlenmez. Yalnızca skorlanır.
Kullanıcı bir skoru düzelttiğinde bu dosyaya veya `kisiler.md`'ye yansıtılır ve düzeltmenin
tarihi not düşülür.

## Düzeltme geçmişi

<!-- Kullanıcı skor düzelttikçe buraya eklenir. Örnek:
2026-09-01 — muhasebe@ mailleri sürekli düşük skorlanıyordu, VIP listesine eklendi.
-->
