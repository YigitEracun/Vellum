# Mail önem skorlaması

0–100 arası skor. Taban 30, aşağıdaki sinyaller eklenir/çıkarılır.

**Bu rubriği `panel/skorlama.py` uygular — model değil.** Kurallar deterministik olduğu için
hesabı modele yaptırmak hem pahalı hem yavaştı: 32 maili skorlatmak tek turda 104.000 giriş
tokenı demekti. Model artık yalnızca eşiği geçen birkaç maile özet ve taslak yazar. Bu dosya
belgedir, kod uygulayıcıdır — birini değiştirirken diğerini de güncelleyin.

| Sinyal | Etki |
|---|---|
| Gönderen `kisiler.md` VIP listesinde | +40 |
| Doğrudan sana yazılmış (To: sende) | +20 |
| Yalnızca CC'desin | −15 |
| İçinde tarih veya son tarih geçiyor | +25 |
| Para, fatura, sözleşme, hukuki konu | +30 |
| Soru işareti içeren doğrudan soru var | +15 |
| Bülten / pazarlama / otomatik bildirim | −50 |
| Gönderen `kisiler.md` gürültü listesinde | −40 |
| İş başvurusu **onayı** ("başvurunuz alındı") | −40 |
| Şirketten **ilerleme** (mülakat, teklif, sonuç) | +45 |

## İki tür otomatik mail

Ayrım önemlidir, yoksa mülakat davetleri bültenlerle birlikte elenir:

- **Bülten** — `List-Unsubscribe` veya `List-Id` başlığı taşır. Pazarlama listesi. Gerçek bir
  mülakat daveti asla abonelikten çıkma bağlantısıyla gelmez.
- **İşlem maili** — `noreply@` türü adresten gelen bildirim. Başvuru sistemleri (ATS) mülakat
  davetini de böyle gönderir, o yüzden içeriğine bakılır.

## İçerik sinyalleri yalnızca size yazılmış maillerde sayılır

Pazarlama metni her zaman tarih ("son 3 gün"), fiyat ("199 TL") ve soru ("kaçırmak ister
misiniz?") taşır. Bunlar sayılırsa toplu gönderim cezasını geri kapatır ve bir indirim maili
"aksiyon" olarak brifingin başına çıkar — ölçtük, çıkıyordu. Bu yüzden toplu gönderimde
tarih/para/soru sinyalleri **hesaplanmaz**; VIP'ten geliyorsa ya da başvuru ilerlemesiyse
hesaplanır.

## Kullanıcı kimliği koda gömülmez

"Doğrudan sana yazılmış" ve "CC" sinyalleri kullanıcının adresini bilmeyi gerektirir. Bu adres
çalışma anında `secrets/.env` içindeki `GMAIL_ADRES` dosyasından okunur. Adres çözülemezse bu
iki sinyal tahmin edilmez, atlanır — böylece program başka bir hesapla kurulduğunda
kendiliğinden o kullanıcıya göre çalışır.

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
