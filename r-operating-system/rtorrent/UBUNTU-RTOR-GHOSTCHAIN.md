# Add the RGHOSTCHAIN file link to the RTOR app on Ubuntu

Instruction for the Ubuntu RTOR app builders (from the owner, via ThundR).

The Renjin Torrent web client already carries the RGHOSTCHAIN FILE section.
Add the same section to the RTOR app on Ubuntu, so Ubuntu can add the
GHOSTCHAIN file the same way — open the file to seed, or leech by magnet.

## The links to add

- Working link across devices (verified, serves the full file now):
  https://raw.githubusercontent.com/RIZALEON/RENJIN-CRYPTOBOT-AI/main/r-operating-system/rtorrent/RGHOSTCHAIN.rzl
- GitHub Pages link (may 404 until Pages redeploys):
  https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/r-operating-system/rtorrent/RGHOSTCHAIN.rzl

## The magnet

magnet:?xt=urn:btih:92d1572a642aa073efa1979000e7705126e8924fbf94403b6617f65a45e81e37&dn=RGHOSTCHAIN.rzl&tr=https://rizal.pw/rtrackr

## SHA-256

92d1572a642aa073efa1979000e7705126e8924fbf94403b6617f65a45e81e37

## The chain it carries

Live GHOSTCHAIN from RTRACKR, snapshot Nov 20, 2026 2:43:28 PM MT, height 5,
6 blocks, tip 4006b57088…f0bb5b, chain verify OK. The client accepts the file
only if its SHA-256 matches.

## Where it goes in the Ubuntu app

The same place as in the web client: next to LEECH BY MAGNET / OPEN A FILE TO
SEED, with a one-tap button that loads the magnet into the leech field.
The Ubuntu app is the Linux RTOR client in the R OPERATING SYSTEM
(R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl, run-linux.sh serves the shell on
127.0.0.1:4984). No measured RTOR speed exists yet; no live device swarm is
claimed until a device run proves it.
