# RTOR CLIENT — Renjin Torrent

The RTOR client integrated into the public sites.

- Version: **RTOR 0.2.3** — LIVE on all three peers (Moto, Pixel, Neo). The main
  /rtor/client/ page still shows 0.2.2 — switch it to 0.2.3.
- Installed: Moto over wireless debugging, starts on its own, Files at the top.
  Signed with the new RTOR release key, no Face ID step.
- Signed APK: in the Moto's Downloads and on both sites (rizal.pw 0.2.3,
  rizal.info 0.2.3).
- Client page: rtorrent/renjin-torrent.html (this folder, served on GitHub Pages)
- Live link: https://muse.ai/s/renjin-torrent-hxi6ej8yxtwuz/CyifUZXzpFju5AwsEx6Y0c4NFcBAU4fCa8XGl3wTMwg
- Opens into: R:> Shell https://muse.ai/s/r-shell-xjxn6dxbxskxa5xyxp/kkOmaDGgjjCjTlH90iROQIDKXoHChxAg8QmB3lc8S6Y
- Magnet: built from PKG SHA-256 3a19e054d6d3718d4f4a87a863dc97b691a7da578f820b8906197820400069c6
  + STATE 16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08,
  tracker RTRACKR https://rizal.pw/rtrackr, RMAIL share relay_8797
- Component: RENJIN-COMPONENT.rzl (922,494 B, SHA 67a8c186…f5aa) — magnetized
  RTOR GHOSTCHAIN transponder + RTOR file integrated
- Kubo: RENJIN-KUBO.rzl (932,923 B, SHA 04b7b1e2…b3a97)
- RGHOSTCHAIN file: RGHOSTCHAIN.rzl (3,669 B, SHA 92d1572a…e81e37) — shared link
  https://raw.githubusercontent.com/RIZALEON/RENJIN-CRYPTOBOT-AI/main/r-operating-system/rtorrent/RGHOSTCHAIN.rzl
- Sites linked: https://rizal.pw/rtrackr — https://rizal.pw — https://rizal.info
  — https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/

## Measured speeds (first, from measured bytes, 2026-11-20 23:11 MST)

- Moto: ~1.5 KB/s each way with the Neo
- Pixel: ~3 KB/s
- Neo: ~4.5 KB/s
- All three peers seeding and leeching above 1 KB/s. The old "no measured RTOR
  speed yet" line no longer applies.

## Live watch

A scheduled check pulls RTRACKR and grabs each device as it comes online,
updating the integrated trackers (R:> Shell + Renjin Torrent) with its
designation, RID and exact entry time. Detection is independent per device and
per app — each reports itself into the stream; ThundR reads the stream and
records it.
