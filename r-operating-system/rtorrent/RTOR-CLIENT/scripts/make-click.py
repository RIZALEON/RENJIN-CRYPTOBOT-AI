#!/usr/bin/env python3
"""Assemble an (unsigned) Ubuntu Touch .click from a staged directory, without the click tool.
Layout matches `click build` 0.4: ar[debian-binary, _click-binary, control.tar.gz, data.tar.gz].
Usage: make-click.py STAGE_DIR OUT_DIR  ->  prints the .click path."""
import hashlib, io, json, os, sys, tarfile, time

def tar_gz(members):  # members: list of (arcname, bytes|None for dir, mode)
    buf = io.BytesIO(); mt = int(time.time())
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as t:
        for name, data, mode in members:
            ti = tarfile.TarInfo(name); ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; ti.mtime = mt; ti.mode = mode
            if data is None:
                ti.type = tarfile.DIRTYPE; t.addfile(ti)
            else:
                ti.size = len(data); t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()

def ar(members):
    out = b"!<arch>\n"
    for name, data in members:
        hdr = f"{name:<16}{int(time.time()):<12}{0:<6}{0:<6}{0o100644:<8o}{len(data):<10}`\n".encode()
        assert len(hdr) == 60
        out += hdr + data + (b"\n" if len(data) % 2 else b"")
    return out

def main(stage, outdir):
    m = json.load(open(os.path.join(stage, "manifest.json")))
    data, md5s, total = [("./", None, 0o755)], [], 0
    for root, dirs, files in os.walk(stage):
        dirs.sort()
        rel = os.path.relpath(root, stage)
        if rel != ".":
            data.append(("./" + rel, None, 0o755))
        for f in sorted(files):
            p = os.path.join(root, f); r = os.path.normpath(os.path.join(rel, f))
            b = open(p, "rb").read(); total += len(b)
            mode = 0o755 if os.access(p, os.X_OK) else 0o644
            data.append(("./" + r, b, mode)); md5s.append(f"{hashlib.md5(b).hexdigest()}  {r}\n")
    kb = (total + 1023) // 1024
    m["installed-size"] = str(kb)
    control = (f"Package: {m['name']}\nVersion: {m['version']}\nClick-Version: 0.4\n"
               f"Architecture: {m['architecture']}\nMaintainer: {m['maintainer']}\n"
               f"Installed-Size: {kb}\nDescription: {m['title']}\n")
    preinst = ("#! /bin/sh\necho \"Click packages may not be installed directly using dpkg.\"\n"
               "echo \"Use 'click install' instead.\"\nexit 1\n")
    ctl = tar_gz([("./", None, 0o755), ("./control", control.encode(), 0o644),
                  ("./manifest", (json.dumps(m, indent=4, sort_keys=True) + "\n").encode(), 0o644),
                  ("./md5sums", "".join(md5s).encode(), 0o644), ("./preinst", preinst.encode(), 0o755)])
    click = ar([("debian-binary", b"2.0\n"), ("_click-binary", b"0.4\n"),
                ("control.tar.gz", ctl), ("data.tar.gz", tar_gz(data))])
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{m['name']}_{m['version']}_{m['architecture']}.click")
    open(out, "wb").write(click)
    print(out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
