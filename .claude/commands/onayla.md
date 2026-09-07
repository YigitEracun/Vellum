---
description: Taslağı gönder (id argümanı gerekir)
---

Argüman: taslak id'si. Verilmemişse `/kuyruk` çıktısını göster ve dur.

Sırayla:

1. Taslağın **tam metnini** kullanıcıya göster — kime gideceği, konusu, gövdesi.
2. Açık onay iste. "Gönderiyorum" deyip gönderme; kullanıcının onay vermesini bekle.
3. Onay geldikten sonra gönder.
4. Gönderim başarılıysa:
   - Taslağın durumunu `gonderildi` yap
   - Madde bir projeye bağlıysa `projects/<proje>/olaylar.jsonl` dosyasının sonuna satır
     **ekle** (`tip: "not"`, `onaylanmamis: false`, kaynağı belirt)
   - `durum.json` yeniden türetilsin diye `proje-agent` çalıştır
5. Gönderim başarısızsa ne olduğunu açıkça söyle. Sessizce yeniden deneme.

Kullanıcı onay vermezse hiçbir dosyaya dokunma.
