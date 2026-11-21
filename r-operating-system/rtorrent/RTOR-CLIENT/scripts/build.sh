#!/bin/zsh
# RTOR GHOSTCHAIN cryptoclient build (Xcode External Build targets RTOR-Linux / RTOR-Android, or by hand).
#   build.sh linux   [ACTION]   static Go builds linux x86_64 + arm64 + riscv64, packaged with run-linux.sh (.tar.gz each)
#   build.sh android [ACTION]   UNSIGNED APK: aapt2 + javac + d8 + zipalign (RDRAGON vc39 recipe), WebView over the same client
#   build.sh ubuntutouch [ACTION] UNSIGNED Ubuntu Touch .click (arm64, ubuntu-sdk-20.04): Go client + Morph.Web QML shell
#   build.sh all
# Signs nothing (no debug keystore either), installs nothing, publishes nothing, touches no keys.
# Refuses to run if the Neo disk would be under 3 GB free. Every run logs start + result to RSCRIBE.
set -u
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"
PLAT="${1:-all}"; ACT="${2:-${ACTION:-build}}"; [ -z "$ACT" ] && ACT=build
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
RC="$HOME/R/ЯLAB/RCRYPTOFORGE"
GO="${GO:-$RC/RUNTIME/toolchains/go1.27.4/bin/go}"
VER=$(sed -n 's/^[[:space:]]*Version[[:space:]]*= "\(.*\)"/\1/p' "$ROOT/cmd/rtor-ghostchain/main.go" | head -1); VER="${VER:-0.0.0}"
OUT="${RTOR_BUILD_OUT:-$ROOT/build/$VER}"; WHO="${RTOR_RUN_BY:-Xcode}"
LOGPY="$HERE/rscribe-log.py"
alog() { /usr/bin/python3 "$LOGPY" "xcode-rtor-build:$PLAT" "$1" "$2" >/dev/null 2>&1 || true; }
if [ "$ACT" = "clean" ]; then alog "$WHO RTOR-$PLAT clean" "no-op (outputs kept, checksums recorded instead)"; echo "clean: no-op"; exit 0; fi
FREE_KB=$(df -k "$ROOT" | awk 'NR==2{print $4}')
if [ "$FREE_KB" -lt "${RTOR_MIN_FREE_KB:-3355443}" ]; then alog "$WHO RTOR-$PLAT" "REFUSED: disk under 3.2 GB free ($((FREE_KB/1024)) MB)"; echo "error: disk under 3.2 GB free ($((FREE_KB/1024)) MB); refusing to build"; exit 1; fi
mkdir -p "$OUT"; SUMS="$OUT/SHA256SUMS.txt"; T0=$(date +%s); RC_ALL=0
alog "$WHO RTOR-$PLAT $ACT START v$VER" "started (go $("$GO" version 2>/dev/null | awk '{print $3}'))"

build_linux() {
  export CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-trimpath GOCACHE="${GOCACHE:-$ROOT/build/.gocache}"
  for A in x86_64:amd64 arm64:arm64 riscv64:riscv64; do
    N=${A%%:*}; G=${A##*:}; P="rtor-ghostchain-$VER-linux-$N"; D="$OUT/linux/$P"
    rm -rf "$D"; mkdir -p "$D/bin" "$D/rzl" "$D/records"
    (cd "$ROOT" && GOOS=linux GOARCH=$G "$GO" build -ldflags "-s -w -buildid=" -o "$D/bin/rtor-ghostchain" ./cmd/rtor-ghostchain) || return 1
    cp "$ROOT"/rzl/*.rzl "$D/rzl/"; cp "$ROOT"/records/*.md "$D/records/"; cp "$HERE/run-linux.sh" "$D/"; chmod +x "$D/run-linux.sh"
    cp "$ROOT/README.md" "$D/README.md"
    (cd "$D" && shasum -a 256 bin/rtor-ghostchain rzl/*.rzl run-linux.sh > SHA256SUMS)
    COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata --no-acls --uid 0 --gid 0 -C "$OUT/linux" -czf "$OUT/linux/$P.tar.gz" "$P" || return 1
    echo "linux: $OUT/linux/$P.tar.gz"
  done
}

build_android() {
  export JAVA_HOME=/opt/homebrew/opt/openjdk@17; export PATH=$JAVA_HOME/bin:$PATH
  local SDK=/opt/homebrew/share/android-commandlinetools BT AJ O DEST
  BT=$SDK/build-tools/35.0.0; AJ=$SDK/platforms/android-35/android.jar
  [ -x "$BT/aapt2" ] && [ -f "$AJ" ] || { echo "error: Android build-tools 35 / android-35 not found under $SDK"; return 1; }
  O="$OUT/android/work"; DEST="$OUT/android/RTOR-GHOSTCHAIN-$VER-release-UNSIGNED.apk"; rm -rf "$O" "$DEST"; mkdir -p "$O/classes" "$O/lib/arm64-v8a" "$O/lib/x86_64"
  export CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-trimpath GOCACHE="${GOCACHE:-$ROOT/build/.gocache}"
  (cd "$ROOT" && GOOS=linux GOARCH=arm64 "$GO" build -ldflags "-s -w -buildid=" -o "$O/lib/arm64-v8a/librtorghostchain.so" ./cmd/rtor-ghostchain) || return 1
  (cd "$ROOT" && GOOS=linux GOARCH=amd64 "$GO" build -ldflags "-s -w -buildid=" -o "$O/lib/x86_64/librtorghostchain.so" ./cmd/rtor-ghostchain) || return 1
  sed -e "s/android:versionName=\"[^\"]*\"/android:versionName=\"$VER\"/" "$ROOT/android/AndroidManifest.xml" > "$O/AndroidManifest.xml"
  "$BT/aapt2" link -I "$AJ" --manifest "$O/AndroidManifest.xml" -o "$O/base.apk" || return 1
  javac -nowarn --release 11 -classpath "$AJ" -d "$O/classes" $(find "$ROOT/android/src" -name '*.java') || return 1
  "$BT/d8" --release --min-api 26 --lib "$AJ" --output "$O" $(find "$O/classes" -name '*.class') || return 1
  /usr/bin/python3 - "$O" "$ROOT" <<'PY' || return 1
import zipfile, os, sys
O, R = sys.argv[1:3]
def zi(n, ct): z = zipfile.ZipInfo(n, (1981, 1, 1, 0, 0, 0)); z.compress_type = ct; z.external_attr = 0o644 << 16; return z
with zipfile.ZipFile(O + "/unaligned.apk", "w") as o:
    with zipfile.ZipFile(O + "/base.apk") as b:
        for i in b.infolist(): o.writestr(zi(i.filename, i.compress_type), b.read(i.filename))
    o.writestr(zi("classes.dex", zipfile.ZIP_DEFLATED), open(O + "/classes.dex", "rb").read())
    for abi in ("arm64-v8a", "x86_64"):
        o.writestr(zi("lib/%s/librtorghostchain.so" % abi, zipfile.ZIP_DEFLATED), open("%s/lib/%s/librtorghostchain.so" % (O, abi), "rb").read())
    for f in sorted(os.listdir(R + "/rzl")):
        if f.endswith(".rzl"): o.writestr(zi("assets/rzl/" + f, zipfile.ZIP_STORED), open(R + "/rzl/" + f, "rb").read())
PY
  "$BT/zipalign" -p -f 4 "$O/unaligned.apk" "$DEST" || return 1
  "$BT/zipalign" -c -p 4 "$DEST" && echo "zipalign OK"
  rm -rf "$O"   # UNSIGNED; real signing is Rizal's
  echo "android: $DEST"
}

build_ubuntutouch() {
  local S="$OUT/ubuntutouch/stage" DST="$OUT/ubuntutouch"
  rm -rf "$S"; mkdir -p "$S/bin" "$S/rzl" "$S/qml"
  export CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-trimpath GOCACHE="${GOCACHE:-$ROOT/build/.gocache}"
  (cd "$ROOT" && GOOS=linux GOARCH=arm64 "$GO" build -ldflags "-s -w -buildid=" -o "$S/bin/rtor-ghostchain" ./cmd/rtor-ghostchain) || return 1
  cp "$ROOT"/rzl/*.rzl "$S/rzl/"; cp "$ROOT"/ubuntutouch/qml/*.qml "$S/qml/"
  cp "$ROOT"/ubuntutouch/rtor.apparmor "$ROOT"/ubuntutouch/rtor.desktop "$ROOT"/ubuntutouch/rtor.content-hub \
     "$ROOT"/ubuntutouch/rtor.url-dispatcher "$ROOT"/ubuntutouch/rtor.sh "$ROOT"/ubuntutouch/icon.png \
     "$ROOT"/ubuntutouch/rtor-service.sh "$ROOT"/ubuntutouch/rtor-ghostchain.service "$S/"
  chmod 755 "$S/rtor.sh" "$S/rtor-service.sh" "$S/bin/rtor-ghostchain"
  sed -e "s/\"version\": \"[^\"]*\"/\"version\": \"$VER\"/" "$ROOT/ubuntutouch/manifest.json" > "$S/manifest.json"
  rm -f "$DST"/*.click(N)
  /usr/bin/python3 "$HERE/make-click.py" "$S" "$DST" || return 1
  rm -rf "$S"   # UNSIGNED; nothing signed, no test keys
  echo "ubuntutouch: $(ls "$DST"/*.click)"
}

case "$PLAT" in
  linux) build_linux || RC_ALL=1 ;;
  android) build_android || RC_ALL=1 ;;
  ubuntutouch) build_ubuntutouch || RC_ALL=1 ;;
  all) build_linux || RC_ALL=1; build_android || RC_ALL=1; build_ubuntutouch || RC_ALL=1 ;;
  *) echo "error: unknown platform $PLAT"; exit 2 ;;
esac
(cd "$OUT" && find linux android ubuntutouch -maxdepth 2 \( -name '*.tar.gz' -o -name '*.apk' -o -name '*.click' \) 2>/dev/null | sort | xargs shasum -a 256 > "$SUMS" 2>/dev/null)
DT=$(( $(date +%s) - T0 ))
SHORT=$(awk '{n=split($2,p,"/"); printf "%s %s…; ", p[n], substr($1,1,16)}' "$SUMS")
if [ $RC_ALL -eq 0 ]; then
  alog "$WHO RTOR-$PLAT $ACT RESULT v$VER" "OK in ${DT}s; $SHORT full sums in $SUMS"; echo "rtor-build: OK ($PLAT) in ${DT}s"; cat "$SUMS"; exit 0
else
  alog "$WHO RTOR-$PLAT $ACT RESULT v$VER" "FAILED in ${DT}s"; echo "error: rtor-build FAILED ($PLAT)"; exit 1
fi
