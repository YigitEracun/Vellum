---
description: Onay bekleyen taslakları listele
---

`state/inbox-digest.json` ve `state/social-queue.json` içinde `durum` alanı `onay_bekliyor`
olan maddeleri bul. Her biri için göster:

- Kimden geldiği ve ne istediği (tek satır)
- Instagram ise kalan cevap penceresi — 6 saatten azsa vurgula
- Taslağın tam metni

Sonda: "Onaylamak için `/onayla <id>`, değiştirmek için `/duzelt <id> <ne değişsin>`."

Hiçbir şey gönderme. Bu komut yalnızca gösterir.
