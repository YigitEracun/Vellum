---
description: Proje geçmişini göster (proje adı argümanı)
---

Argüman verilmemişse `projects/` altındaki tüm projeleri listele: ad, canlı özet,
son hareket, açık blokaj sayısı. Sessizleşenleri (14 gün ve üzeri hareketsiz) ayrıca belirt.

Argüman verilmişse o projenin:

1. `durum.json` içindeki özeti ve sonraki adımı
2. `olaylar.jsonl` içindeki olayları **tersten** (yeniden eskiye), aya göre gruplayarak
3. Kilometre taşlarını vurgulayarak, onaylanmamış olayları "(onay bekliyor)" notuyla
4. `kararlar/` altında kayıt varsa özetle

Kullanıcı "neden şöyle yapmıştık" diye sorarsa önce `kararlar/`, sonra `karar_alindi`
tipindeki olaylara bak. Cevabı uydurma — kayıt yoksa "bu kayıtlarda yok" de.
