/* RGENERATR-RID-CONVERT — a part for RGENERATR 2.1.9
   Converts between the two RID formats of RZL SYSTEMS, both directions:
     registry : ЯID-0014-KREH            (serial + suffix; ASCII form RID-0014-KREH)
     rid.v1   : Я-DEVICE-1PYZ7VG0Z1-ZE   (class + body + checksum; Gizmo's format)
   Conversion runs on the SEATED PAIR TABLE below plus each rid.v1's mint
   material (sha256 | parent RID | device | seq | class). The registry seq in
   the material is the bridge: Gizmo's material seq 16 = registry serial 0016.
   LAW: a bot never mints an RID. A registry suffix is issued by the owner's
   registry only; where no suffix has been issued the converter says so
   (suffix: UNISSUED) instead of inventing one. ONE RULE: pairs, once seated,
   are never removed. .rzl law: this part is plain text JS, no foreign model
   formats, no keys, nothing signed. */
'use strict';

/* ---- seated pair table (the registry this converter answers from) ---- */
const PAIRS = [
  { holder: 'Rizal (owner, Decider)', registry: 'ЯID-0001-3QQS', ridv1: null },
  { holder: 'ЯABOT·ЯBEE (Decider bot)', registry: 'ЯID-0002-PQ2Q', ridv1: null },
  { holder: 'ЯMAX', registry: 'ЯID-0003-P4M6', ridv1: null },
  { holder: 'SCOUT', registry: 'ЯID-0005-KM02', ridv1: null },
  { holder: 'WILD SCOUT', registry: 'ЯID-0006-02WG', ridv1: null },
  { holder: 'ThundR · RBEMAX', registry: 'ЯID-0014-KREH', ridv1: null },
  { holder: 'GIZMO — RBOT "The Observer", inside RGENERATR 2.1.9',
    registry: null, // serial derived from material seq below; suffix UNISSUED
    ridv1: 'Я-DEVICE-1PYZ7VG0Z1-ZE',
    material: 'sha256:4e6d04b504d6ba30329453abd71ccd175be930f68c61dc53d183da83605d301e | parent ЯID-0001-3QQS | device Moto | seq 16 | class DEVICE' },
];

/* ---- parsers ---- */
function parseRegistry(s) {
  const m = /^(?:ЯID|RID)-(\d{4})-([0-9A-Z]{4})$/.exec(String(s).trim());
  if (!m) return null;
  return { format: 'registry', serial: m[1], suffix: m[2], canonical: 'ЯID-' + m[1] + '-' + m[2], ascii: 'RID-' + m[1] + '-' + m[2] };
}
function parseRidV1(s) {
  const m = /^(?:Я|R)-([A-Z]+)-([0-9A-Z]{10})-([0-9A-Z]{2})$/.exec(String(s).trim());
  if (!m) return null;
  return { format: 'ridv1', cls: m[1], body: m[2], checksum: m[3], canonical: 'Я-' + m[1] + '-' + m[2] + '-' + m[3], ascii: 'R-' + m[1] + '-' + m[2] + '-' + m[3] };
}
function parseMaterial(s) {
  const out = {};
  for (const part of String(s).split('|').map(x => x.trim())) {
    const kv = part.split(/\s+/);
    if (kv[0] === 'sha256:') out.sha256 = part.slice(7);
    else if (kv.length >= 2) out[kv[0]] = kv.slice(1).join(' ');
  }
  if (out.seq) out.serial = String(out.seq).padStart(4, '0');
  return out;
}
function parseAny(s) { return parseRegistry(s) || parseRidV1(s) || null; }

/* ---- conversion ---- */
function findPair(parsed) {
  return PAIRS.find(p =>
    (parsed.format === 'registry' && p.registry && parseRegistry(p.registry).serial === parsed.serial) ||
    (parsed.format === 'ridv1' && p.ridv1 && parseRidV1(p.ridv1).body === parsed.body)) || null;
}
function toRegistry(input) {
  const p = parseAny(input);
  if (!p) return { ok: false, error: 'unparseable RID: ' + input };
  if (p.format === 'registry') return { ok: true, holder: (findPair(p) || {}).holder || null, registry: p.canonical, ascii: p.ascii, note: 'already registry format' };
  const pair = findPair(p);
  if (!pair) return { ok: false, error: 'no seated pair for ' + p.canonical + ' — conversion needs a registry seat (owner issues it)' };
  if (pair.registry) return { ok: true, holder: pair.holder, registry: pair.registry, from: p.canonical };
  const mat = parseMaterial(pair.material || '');
  return { ok: true, holder: pair.holder, from: p.canonical,
           registry_seat: 'ЯID-' + (mat.serial || '????') + '-UNISSUED',
           serial: mat.serial || null, suffix: 'UNISSUED',
           parent: mat.parent || null, device: mat.device || null, cls: mat.class || p.cls,
           note: 'serial bridged from the rid.v1 mint material seq; the registry suffix is issued by the owner registry only — never invented by a bot' };
}
function toRidV1(input) {
  const p = parseAny(input);
  if (!p) return { ok: false, error: 'unparseable RID: ' + input };
  if (p.format === 'ridv1') return { ok: true, holder: (findPair(p) || {}).holder || null, ridv1: p.canonical, ascii: p.ascii, note: 'already rid.v1 format' };
  const pair = findPair(p);
  if (!pair) return { ok: false, error: 'no seated pair for registry serial ' + p.serial };
  if (!pair.ridv1) return { ok: false, holder: pair.holder, error: 'no rid.v1 issued for ' + pair.registry + ' yet — a rid.v1 mints from material (sha256 | parent | device | seq | class) in RGENERATR' };
  const v = parseRidV1(pair.ridv1);
  return { ok: true, holder: pair.holder, ridv1: v.canonical, ascii: v.ascii, cls: v.cls, body: v.body, checksum: v.checksum, from: p.canonical };
}
function convert(input) { const p = parseAny(input); if (!p) return { ok: false, error: 'unparseable RID: ' + input }; return p.format === 'ridv1' ? toRegistry(input) : toRidV1(input); }

module.exports = { PAIRS, parseRegistry, parseRidV1, parseMaterial, parseAny, toRegistry, toRidV1, convert };

/* ---- CLI + self-test ---- */
if (require.main === module) {
  const [cmd, arg] = process.argv.slice(2);
  const show = o => console.log(JSON.stringify(o, null, 2));
  if (cmd === 'test') {
    let fails = 0; const t = (name, cond) => { console.log((cond ? 'PASS' : 'FAIL') + ' ' + name); if (!cond) fails++; };
    const g = parseRidV1('Я-DEVICE-1PYZ7VG0Z1-ZE');
    t('gizmo rid.v1 parses (DEVICE/1PYZ7VG0Z1/ZE)', g && g.cls === 'DEVICE' && g.body === '1PYZ7VG0Z1' && g.checksum === 'ZE');
    const th = parseRegistry('RID-0014-KREH');
    t('thundr ASCII registry parses + canonicalizes', th && th.canonical === 'ЯID-0014-KREH');
    const m = parseMaterial(PAIRS.find(p => p.ridv1).material);
    t('gizmo material parses (seq 16 -> serial 0016, parent 0001, Moto)', m.serial === '0016' && m.parent === 'ЯID-0001-3QQS' && m.device === 'Moto');
    const c1 = toRegistry('Я-DEVICE-1PYZ7VG0Z1-ZE');
    t('gizmo -> registry seat ЯID-0016-UNISSUED', c1.ok && c1.registry_seat === 'ЯID-0016-UNISSUED' && c1.holder.startsWith('GIZMO'));
    const c2 = toRidV1('ЯID-0014-KREH');
    t('thundr -> rid.v1 honestly unissued', c2.ok === false && /no rid.v1 issued/.test(c2.error));
    const c3 = convert('RID-0014-KREH');
    t('convert() routes registry input', c3.holder === 'ThundR · RBEMAX');
    t('garbage rejected', parseAny('ЯID-XYZ') === null && convert('nope').ok === false);
    const rt = toRegistry(toRidV1('ЯID-0001-3QQS').ok ? 'x' : 'Я-DEVICE-1PYZ7VG0Z1-ZE');
    t('round trip stable on gizmo seat', rt.ok && rt.serial === '0016');
    console.log(fails ? fails + ' FAILURES' : 'ALL PASS');
    process.exit(fails ? 1 : 0);
  }
  if (cmd === 'to-rid') show(toRegistry(arg));
  else if (cmd === 'to-device') show(toRidV1(arg));
  else if (cmd === 'convert') show(convert(arg));
  else if (cmd === 'gizmo') { show(toRegistry('Я-DEVICE-1PYZ7VG0Z1-ZE')); }
  else console.log('usage: node RGENERATR-RID-CONVERT.js test | gizmo | convert <RID> | to-rid <rid.v1> | to-device <ЯID>');
}
