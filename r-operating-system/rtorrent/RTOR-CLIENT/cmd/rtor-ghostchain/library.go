package main

// RTOR file library: open/import, hash-verify, seed and leech one file at a time.
// RTOR is simple seed/leech of a file. Seeding = the verified file is placed in this space's RKLOWD/RMAIL drop points
// with a .rtor.json manifest and announced (magnet) over RMAIL; leeching = find the file by hash in the library or a
// drop point, or fetch it from an exact-source URL in the magnet, and accept it only if the SHA-256 matches.
// No peers or swarm are invented. Private keys are refused on import and never stored.

import (
	"bufio"
	"bytes"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const maxImport = 512 << 20

// ------------------------------------------------------------- SPACE-RID.json

type Space struct {
	RID         string          `json:"rid"`
	Space       string          `json:"space"`
	RKLOWDNode  string          `json:"rklowd_node"`
	RMailAddr   string          `json:"rmail_address"`
	DropPathsJS json.RawMessage `json:"drop_paths"`
	Source      string          `json:"-"`
}

type DropPoint struct {
	Name      string `json:"name"`
	Path      string `json:"path"`
	Reachable bool   `json:"reachable"`
}

func (s *Space) Drops() []DropPoint {
	var out []DropPoint
	add := func(n, p string) {
		p = os.ExpandEnv(strings.TrimSpace(p))
		if strings.HasPrefix(p, "~/") {
			h, _ := os.UserHomeDir()
			p = filepath.Join(h, p[2:])
		}
		if p == "" {
			return
		}
		st, err := os.Stat(p)
		out = append(out, DropPoint{Name: n, Path: p, Reachable: err == nil && st.IsDir()})
	}
	if s == nil || len(s.DropPathsJS) == 0 {
		return out
	}
	var arr []string
	var obj map[string]any
	var ents []struct{ Address, Kind string }
	if json.Unmarshal(s.DropPathsJS, &arr) != nil && json.Unmarshal(s.DropPathsJS, &ents) == nil {
		// registry form: [{address, kind, role}] — only filesystem addresses are drop folders (RMAIL/site entries are not)
		for i, e := range ents {
			if strings.Contains(e.Address, "@") || strings.Contains(e.Address, "://") || e.Kind == "rmail" || e.Kind == "site" {
				continue
			}
			if strings.HasPrefix(e.Address, "/") || strings.HasPrefix(e.Address, "~/") || strings.HasPrefix(e.Address, "$") {
				k := e.Kind
				if k == "" {
					k = "drop"
				}
				add(k+strconv.Itoa(i), e.Address)
			}
		}
		return out
	}
	if json.Unmarshal(s.DropPathsJS, &arr) == nil {
		for i, p := range arr {
			add("drop"+strconv.Itoa(i), p)
		}
	} else if json.Unmarshal(s.DropPathsJS, &obj) == nil {
		keys := make([]string, 0, len(obj))
		for k := range obj {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			switch v := obj[k].(type) {
			case string:
				add(k, v)
			case []any:
				for i, x := range v {
					if s, ok := x.(string); ok {
						add(k+strconv.Itoa(i), s)
					}
				}
			}
		}
	}
	return out
}

func loadSpace(cands ...string) *Space {
	for _, p := range cands {
		if p == "" {
			continue
		}
		b, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var s Space
		if json.Unmarshal(b, &s) == nil && (s.RID != "" || s.Space != "") {
			s.Source = p
			return &s
		}
	}
	return nil
}

// ------------------------------------------------------------- magnets

type MagnetInfo struct {
	Raw      string   `json:"raw"`
	BTIHv1   string   `json:"btih_v1,omitempty"` // 40-hex (or base32) v1 infohash
	BTIH64   string   `json:"btih_64,omitempty"` // 64-hex btih as used by the RENJIN records
	BTMH     string   `json:"btmh_v2,omitempty"` // urn:btmh:1220<sha256> v2 infohash
	SHA256   string   `json:"sha256,omitempty"`  // urn:sha256 exact file/state hash
	Name     string   `json:"dn,omitempty"`
	Size     int64    `json:"xl,omitempty"`
	Trackers []string `json:"tr,omitempty"`
	Sources  []string `json:"xs,omitempty"`
	Problems []string `json:"problems,omitempty"`
}

var hex40 = regexp.MustCompile(`^[0-9a-fA-F]{40}$`)
var hex64 = regexp.MustCompile(`^[0-9a-fA-F]{64}$`)
var b32 = regexp.MustCompile(`^[A-Za-z2-7]{32}$`)

func parseMagnet(s string) (MagnetInfo, error) {
	m := MagnetInfo{Raw: strings.TrimSpace(s)}
	if !strings.HasPrefix(strings.ToLower(m.Raw), "magnet:?") {
		return m, errors.New("not a magnet: link")
	}
	q, err := url.ParseQuery(m.Raw[len("magnet:?"):])
	if err != nil {
		return m, err
	}
	for k, vs := range q {
		base := strings.SplitN(k, ".", 2)[0] // xt.1, xt.2 ...
		for _, v := range vs {
			switch base {
			case "xt":
				lv := strings.ToLower(v)
				switch {
				case strings.HasPrefix(lv, "urn:btih:"):
					h := v[len("urn:btih:"):]
					switch {
					case hex40.MatchString(h):
						m.BTIHv1 = strings.ToLower(h)
					case b32.MatchString(h):
						m.BTIHv1 = "b32:" + strings.ToUpper(h)
					case hex64.MatchString(h):
						m.BTIH64 = strings.ToLower(h)
					default:
						m.Problems = append(m.Problems, "btih not 40-hex, 32-base32 or 64-hex: "+h)
					}
				case strings.HasPrefix(lv, "urn:btmh:"):
					h := strings.ToLower(v[len("urn:btmh:"):])
					if strings.HasPrefix(h, "1220") && hex64.MatchString(h[4:]) {
						m.BTMH = h[4:]
					} else {
						m.Problems = append(m.Problems, "btmh not a sha2-256 multihash: "+h)
					}
				case strings.HasPrefix(lv, "urn:sha256:"):
					h := strings.ToLower(v[len("urn:sha256:"):])
					if hex64.MatchString(h) {
						m.SHA256 = h
					} else {
						m.Problems = append(m.Problems, "sha256 not 64-hex")
					}
				}
			case "dn":
				m.Name = v
			case "xl":
				m.Size, _ = strconv.ParseInt(v, 10, 64)
			case "tr":
				m.Trackers = append(m.Trackers, v)
			case "xs", "as", "ws":
				m.Sources = append(m.Sources, v)
			}
		}
	}
	if m.BTIHv1 == "" && m.BTIH64 == "" && m.BTMH == "" && m.SHA256 == "" {
		return m, errors.New("magnet has no usable xt hash")
	}
	return m, nil
}

func (m MagnetInfo) hashes() []string {
	var h []string
	for _, x := range []string{m.SHA256, m.BTIH64, m.BTMH} {
		if x != "" {
			h = append(h, x)
		}
	}
	return h
}

func fileMagnet(it *Item) string {
	v := url.Values{}
	v.Set("dn", it.Name)
	v.Set("xl", strconv.FormatInt(it.Size, 10))
	v.Set("tr", RTRACKRURL)
	s := "magnet:?xt=urn:sha256:" + it.SHA256
	if it.BTIHv1 != "" {
		s += "&xt=urn:btih:" + it.BTIHv1
	}
	if it.BTMH != "" {
		s += "&xt=urn:btmh:1220" + it.BTMH
	}
	return s + "&" + v.Encode()
}

// ------------------------------------------------------------- bencode (.torrent infohash)

func bdecodeSkip(b []byte, i int) (int, error) {
	if i >= len(b) {
		return 0, errors.New("bencode: eof")
	}
	switch c := b[i]; {
	case c == 'i':
		j := bytes.IndexByte(b[i:], 'e')
		if j < 0 {
			return 0, errors.New("bencode: int")
		}
		return i + j + 1, nil
	case c == 'l' || c == 'd':
		i++
		for i < len(b) && b[i] != 'e' {
			var err error
			if i, err = bdecodeSkip(b, i); err != nil {
				return 0, err
			}
		}
		return i + 1, nil
	case c >= '0' && c <= '9':
		j := bytes.IndexByte(b[i:], ':')
		if j < 0 {
			return 0, errors.New("bencode: str")
		}
		n, err := strconv.Atoi(string(b[i : i+j]))
		if err != nil || i+j+1+n > len(b) {
			return 0, errors.New("bencode: strlen")
		}
		return i + j + 1 + n, nil
	}
	return 0, errors.New("bencode: bad byte")
}

type torrentMeta struct {
	Name        string
	Length      int64
	InfoV1      string
	InfoV2      string
	MetaVersion int
	Announce    string
}

func bstr(b []byte, i int) (string, int, error) {
	j := bytes.IndexByte(b[i:], ':')
	if j < 0 {
		return "", 0, errors.New("bencode: key")
	}
	n, err := strconv.Atoi(string(b[i : i+j]))
	if err != nil || i+j+1+n > len(b) {
		return "", 0, errors.New("bencode: key len")
	}
	return string(b[i+j+1 : i+j+1+n]), i + j + 1 + n, nil
}

func parseTorrent(b []byte) (*torrentMeta, error) {
	if len(b) == 0 || b[0] != 'd' {
		return nil, errors.New("not a bencoded dictionary")
	}
	t := &torrentMeta{}
	i := 1
	for i < len(b) && b[i] != 'e' {
		k, j, err := bstr(b, i)
		if err != nil {
			return nil, err
		}
		end, err := bdecodeSkip(b, j)
		if err != nil {
			return nil, err
		}
		switch k {
		case "info":
			raw := b[j:end]
			s1 := sha1.Sum(raw)
			s2 := sha256.Sum256(raw)
			t.InfoV1, t.InfoV2 = hex.EncodeToString(s1[:]), hex.EncodeToString(s2[:])
			// shallow read of name / length / meta version
			for x := j + 1; x < end-1 && b[x] != 'e'; {
				ik, y, err := bstr(b, x)
				if err != nil {
					break
				}
				ye, err := bdecodeSkip(b, y)
				if err != nil {
					break
				}
				v := b[y:ye]
				switch ik {
				case "name":
					if s, _, err := bstr(v, 0); err == nil {
						t.Name = s
					}
				case "length":
					t.Length, _ = strconv.ParseInt(strings.Trim(string(v), "ie"), 10, 64)
				case "meta version":
					t.MetaVersion, _ = strconv.Atoi(strings.Trim(string(v), "ie"))
				}
				x = ye
			}
		case "announce":
			if s, _, err := bstr(b[j:end], 0); err == nil {
				t.Announce = s
			}
		}
		i = end
	}
	if t.InfoV1 == "" {
		return nil, errors.New("torrent has no info dictionary")
	}
	return t, nil
}

// ------------------------------------------------------------- classify + refuse private keys

var privKeyRx = regexp.MustCompile(`(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----|-----BEGIN OPENSSH PRIVATE KEY-----|-----BEGIN PGP PRIVATE KEY BLOCK-----`)
var privFieldRx = regexp.MustCompile(`(?i)^(private_?key|privkey|priv|secret(_?key)?|seed(_?hex|_?phrase)?|mnemonic|xprv|wif|keystore|ciphertext|passphrase|password|signing_?key|sk|d)$`)

func jsonPrivateFields(v any, path string, hits *[]string) {
	switch t := v.(type) {
	case map[string]any:
		for k, x := range t {
			if privFieldRx.MatchString(k) {
				if s, ok := x.(string); !ok || strings.TrimSpace(s) != "" {
					*hits = append(*hits, path+"."+k)
				}
			}
			jsonPrivateFields(x, path+"."+k, hits)
		}
	case []any:
		for i, x := range t {
			jsonPrivateFields(x, path+"["+strconv.Itoa(i)+"]", hits)
		}
	case string:
		if strings.HasPrefix(t, "xprv") || privKeyRx.MatchString(t) {
			*hits = append(*hits, path)
		}
	}
}

// classify returns type, detail, refusal reason ("" = accepted)
func classify(name string, b []byte, it *Item) (string, string) {
	ext := strings.ToLower(filepath.Ext(name))
	if privKeyRx.Match(b) {
		return "refused", "contains a private key block; RTOR never stores or moves keys"
	}
	switch ext {
	case ".rzl":
		it.Type = "rzl"
		for _, f := range rzlFiles {
			if f.Name == filepath.Base(name) || f.SHA == it.SHA256 {
				it.verify("published RTOR-INSTALL table", f.SHA == it.SHA256, f.Name+" expected "+f.SHA[:12]+"…")
			}
		}
	case ".torrent":
		t, err := parseTorrent(b)
		if err != nil {
			return "refused", "torrent parse failed: " + err.Error()
		}
		it.Type, it.BTIHv1 = "torrent", t.InfoV1
		if t.MetaVersion == 2 {
			it.BTMH = t.InfoV2
		}
		it.Detail = map[string]any{"torrent_name": t.Name, "torrent_length": t.Length, "meta_version": t.MetaVersion, "announce": t.Announce}
	case ".rtor":
		it.Type = "rtor"
		var j map[string]any
		if json.Unmarshal(b, &j) == nil {
			it.Detail = map[string]any{"fields": keysOf(j)}
			if mg, ok := j["magnet"].(string); ok {
				if mi, err := parseMagnet(mg); err == nil {
					it.Detail["magnet"] = mi
				}
			}
			var hits []string
			jsonPrivateFields(j, "$", &hits)
			if len(hits) > 0 {
				return "refused", "private-key fields present: " + strings.Join(hits, ", ")
			}
		}
	case ".magnet":
		it.Type = "magnet"
		if mi, err := parseMagnet(strings.TrimSpace(string(b))); err == nil {
			it.Detail = map[string]any{"magnet": mi}
		} else {
			return "refused", err.Error()
		}
	case ".json":
		var j any
		if err := json.Unmarshal(b, &j); err != nil {
			return "refused", "not valid JSON: " + err.Error()
		}
		var hits []string
		jsonPrivateFields(j, "$", &hits)
		if len(hits) > 0 {
			return "refused", "private-key fields present (" + strings.Join(hits, ", ") + "); only public wallet/chain exports are accepted"
		}
		it.Type = "crypto-json"
		if m, ok := j.(map[string]any); ok {
			it.Detail = map[string]any{"fields": keysOf(m)}
		}
	case ".pem", ".crt", ".cer":
		s := string(b)
		if !strings.Contains(s, "-----BEGIN CERTIFICATE-----") && !strings.Contains(s, "-----BEGIN PUBLIC KEY-----") {
			return "refused", "only public certificates / public keys are accepted"
		}
		it.Type = "crypto-pem"
	default:
		if strings.HasPrefix(strings.ToLower(strings.TrimSpace(string(b[:min(len(b), 16)]))), "magnet:?") {
			it.Type = "magnet"
		} else {
			it.Type = "file"
		}
	}
	return "", ""
}

func keysOf(m map[string]any) []string {
	k := make([]string, 0, len(m))
	for x := range m {
		k = append(k, x)
	}
	sort.Strings(k)
	if len(k) > 40 {
		k = k[:40]
	}
	return k
}

// ------------------------------------------------------------- library

type Verify struct {
	Method string `json:"method"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail"`
}

type Item struct {
	SHA256   string         `json:"sha256"`
	Name     string         `json:"name"`
	Type     string         `json:"type"`
	Size     int64          `json:"size"`
	Imported string         `json:"imported"`
	Source   string         `json:"source"`
	BTIHv1   string         `json:"btih_v1,omitempty"`
	BTMH     string         `json:"btmh_v2,omitempty"`
	Verified []Verify       `json:"verified"`
	Magnet   string         `json:"magnet"`
	Seeded   []string       `json:"seeded_to,omitempty"`
	SeededAt string         `json:"seeded_at,omitempty"`
	Sources  []string       `json:"sources,omitempty"`
	SeedOn   bool           `json:"seeding_on"`  // always on (no off state)
	LeechOn  bool           `json:"leeching_on"` // always on (no off state)
	Detail   map[string]any `json:"detail,omitempty"`
}

func (it *Item) verify(method string, ok bool, detail string) {
	it.Verified = append(it.Verified, Verify{method, ok, detail})
}

type Library struct {
	mu         sync.Mutex
	dir        string
	items      map[string]*Item
	sums       map[string]string // sha256 -> name from imported SHA256SUMS files
	hashC      map[string]string // path|size|mtime -> sha256 (drop-point scan cache)
	queue      []*queued         // magnets leeching keeps re-checking (always on)
	verifiedAt map[string]time.Time
}

func openLibrary(dir string) *Library {
	l := &Library{dir: dir, items: map[string]*Item{}, sums: map[string]string{}, hashC: map[string]string{}, verifiedAt: map[string]time.Time{}}
	_ = os.MkdirAll(filepath.Join(dir, "files"), 0o700)
	if b, err := os.ReadFile(filepath.Join(dir, "library.json")); err == nil {
		var s struct {
			Items []*Item           `json:"items"`
			Sums  map[string]string `json:"sums"`
			Queue []*queued         `json:"leech_queue"`
		}
		if json.Unmarshal(b, &s) == nil {
			for _, it := range s.Items {
				it.SeedOn, it.LeechOn = true, true
				l.items[it.SHA256] = it
			}
			l.queue = s.Queue
			if s.Sums != nil {
				l.sums = s.Sums
			}
		}
	}
	return l
}

func (l *Library) saveLocked() {
	var list []*Item
	for _, it := range l.items {
		list = append(list, it)
	}
	sort.Slice(list, func(i, j int) bool { return list[i].Imported > list[j].Imported })
	b, _ := json.MarshalIndent(map[string]any{"items": list, "sums": l.sums, "leech_queue": l.queue}, "", " ")
	tmp := filepath.Join(l.dir, "library.json.tmp")
	if os.WriteFile(tmp, b, 0o600) == nil {
		_ = os.Rename(tmp, filepath.Join(l.dir, "library.json"))
	}
}

func (l *Library) List() []*Item {
	l.mu.Lock()
	defer l.mu.Unlock()
	var list []*Item
	for _, it := range l.items {
		c := *it
		list = append(list, &c)
	}
	sort.Slice(list, func(i, j int) bool { return list[i].Imported > list[j].Imported })
	return list
}

func (l *Library) path(it *Item) string { return filepath.Join(l.dir, "files", it.SHA256) }

func parseSums(b []byte) map[string]string {
	out := map[string]string{}
	sc := bufio.NewScanner(bytes.NewReader(b))
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		if len(f) >= 2 && hex64.MatchString(f[0]) {
			out[strings.ToLower(f[0])] = filepath.Base(strings.TrimPrefix(f[len(f)-1], "*"))
		}
	}
	return out
}

func isSumsName(n string) bool {
	b := strings.ToUpper(filepath.Base(n))
	return strings.HasPrefix(b, "SHA256SUMS") || strings.HasSuffix(b, ".SHA256")
}

func (l *Library) applySumsLocked(it *Item) {
	if n, ok := l.sums[it.SHA256]; ok {
		for _, v := range it.Verified {
			if v.Method == "SHA256SUMS" {
				return
			}
		}
		it.verify("SHA256SUMS", true, "listed as "+n)
	}
}

type ImportResult struct {
	OK      bool   `json:"ok"`
	Item    *Item  `json:"item,omitempty"`
	Refused string `json:"refused,omitempty"`
	Sums    int    `json:"sums_added,omitempty"`
	Dup     bool   `json:"already_in_library,omitempty"`
}

// Import stores bytes (never a private key), verifies and classifies them. sumsDir: optional directory to look for SHA256SUMS.
func (l *Library) Import(name, source string, b []byte, sumsDir string) ImportResult {
	name = filepath.Base(strings.ReplaceAll(name, "\\", "/"))
	if name == "" || name == "." || name == "/" {
		name = "file"
	}
	if isSumsName(name) {
		s := parseSums(b)
		l.mu.Lock()
		for k, v := range s {
			l.sums[k] = v
		}
		for _, it := range l.items {
			l.applySumsLocked(it)
		}
		l.saveLocked()
		l.mu.Unlock()
		return ImportResult{OK: true, Sums: len(s)}
	}
	h := sha256.Sum256(b)
	it := &Item{SHA256: hex.EncodeToString(h[:]), Name: name, Size: int64(len(b)), Imported: nowISO(), Source: source, Verified: []Verify{}, SeedOn: true, LeechOn: true}
	if why, reason := classify(name, b, it); why == "refused" {
		return ImportResult{OK: false, Refused: reason}
	}
	it.verify("sha256", true, "computed on import")
	if sumsDir != "" {
		for _, sn := range []string{"SHA256SUMS", "SHA256SUMS.txt"} {
			if sb, err := os.ReadFile(filepath.Join(sumsDir, sn)); err == nil {
				s := parseSums(sb)
				if n, ok := s[it.SHA256]; ok {
					it.verify("SHA256SUMS", true, sn+" lists "+n)
				} else {
					for k, n := range s {
						if n == name {
							it.verify("SHA256SUMS", false, sn+" lists "+n+" as "+k[:12]+"… (mismatch)")
						}
					}
				}
			}
		}
	}
	it.Magnet = fileMagnet(it)
	l.mu.Lock()
	defer l.mu.Unlock()
	if old, ok := l.items[it.SHA256]; ok {
		return ImportResult{OK: true, Item: old, Dup: true}
	}
	l.applySumsLocked(it)
	tmp := l.path(it) + ".tmp"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return ImportResult{OK: false, Refused: "store failed: " + err.Error()}
	}
	_ = os.Rename(tmp, l.path(it))
	l.items[it.SHA256] = it
	l.saveLocked()
	c := *it
	return ImportResult{OK: true, Item: &c}
}

func (l *Library) Get(sha string) *Item {
	l.mu.Lock()
	defer l.mu.Unlock()
	if it, ok := l.items[strings.ToLower(sha)]; ok {
		c := *it
		return &c
	}
	return nil
}

// Seed places the verified file in every reachable drop point, with a .rtor.json manifest beside it.
func (l *Library) Seed(sha string, sp *Space) (*Item, []string, error) {
	it := l.Get(sha)
	if it == nil {
		return nil, nil, errors.New("not in library")
	}
	got, _, err := sha256File(l.path(it))
	if err != nil || got != it.SHA256 {
		return nil, nil, errors.New("stored file failed SHA-256 re-check; not seeding")
	}
	var placed, notes []string
	man := map[string]any{"schema": "rzl.rtor.seed.v1", "name": it.Name, "sha256": it.SHA256, "size": it.Size, "type": it.Type,
		"magnet": it.Magnet, "ts": nowISO(), "device": cfg.Device, "signed": false}
	if sp != nil {
		man["rid"], man["space"], man["rklowd_node"], man["rmail_address"] = sp.RID, sp.Space, sp.RKLOWDNode, sp.RMailAddr
	}
	mb, _ := json.MarshalIndent(man, "", " ")
	for _, d := range sp.Drops() {
		if !d.Reachable {
			notes = append(notes, d.Name+": not reachable ("+d.Path+")")
			continue
		}
		dst := filepath.Join(d.Path, it.SHA256[:12]+"-"+it.Name)
		if err := copyFile(l.path(it), dst, it.SHA256); err != nil {
			notes = append(notes, d.Name+": "+err.Error())
			continue
		}
		_ = os.WriteFile(dst+".rtor.json", mb, 0o644)
		placed = append(placed, dst)
	}
	l.mu.Lock()
	if x, ok := l.items[it.SHA256]; ok {
		x.Seeded = append(x.Seeded, placed...)
		x.SeededAt = nowISO()
		it = x
	}
	l.saveLocked()
	l.mu.Unlock()
	return it, notes, nil
}

// copyFile places a seed copy; the bytes written count as this file's upload (seeding) rate.
func copyFile(src, dst, key string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".part"
	out, err := os.Create(tmp)
	if err != nil {
		return err
	}
	xfer.begin("up", key)
	start := time.Now()
	n, err := meteredCopy(out, in, "up", key)
	xfer.end("up", key, n, start, "drop "+filepath.Dir(dst))
	if err != nil {
		out.Close()
		return err
	}
	if err := out.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, dst)
}

type LeechResult struct {
	OK     bool       `json:"ok"`
	Magnet MagnetInfo `json:"magnet"`
	Item   *Item      `json:"item,omitempty"`
	From   string     `json:"from,omitempty"`
	Tried  []string   `json:"tried"`
	Note   string     `json:"note,omitempty"`
}

// Leech resolves a magnet to a verified file: library → drop points → exact-source URLs. Nothing is accepted unverified.
func (l *Library) Leech(raw string, sp *Space) LeechResult {
	r := LeechResult{Tried: []string{}}
	m, err := parseMagnet(raw)
	r.Magnet = m
	if err != nil {
		r.Note = err.Error()
		return r
	}
	want := m.hashes()
	// 1. library (file sha256, or a torrent whose v1/v2 infohash matches)
	l.mu.Lock()
	for _, it := range l.items {
		for _, h := range want {
			if it.SHA256 == h || it.BTMH == h {
				c := *it
				r.OK, r.Item, r.From = true, &c, "library"
			}
		}
		if m.BTIHv1 != "" && it.BTIHv1 == m.BTIHv1 {
			c := *it
			r.OK, r.Item, r.From = true, &c, "library (.torrent with this v1 infohash)"
		}
	}
	l.mu.Unlock()
	r.Tried = append(r.Tried, "library")
	if r.OK {
		return r
	}
	// 2. drop points (files hashed once and cached by path/size/mtime)
	for _, d := range sp.Drops() {
		r.Tried = append(r.Tried, "drop "+d.Name)
		if !d.Reachable || len(want) == 0 {
			continue
		}
		ents, _ := os.ReadDir(d.Path)
		for _, e := range ents {
			if e.IsDir() || strings.HasSuffix(e.Name(), ".rtor.json") || strings.HasSuffix(e.Name(), ".part") {
				continue
			}
			fi, err := e.Info()
			if err != nil || fi.Size() > maxImport || (m.Size > 0 && fi.Size() != m.Size) {
				continue
			}
			p := filepath.Join(d.Path, e.Name())
			key := p + "|" + strconv.FormatInt(fi.Size(), 10) + "|" + strconv.FormatInt(fi.ModTime().Unix(), 10)
			l.mu.Lock()
			h, ok := l.hashC[key]
			l.mu.Unlock()
			if !ok {
				if h, _, err = sha256File(p); err != nil {
					continue
				}
				l.mu.Lock()
				l.hashC[key] = h
				l.mu.Unlock()
			}
			for _, w := range want {
				if h == w {
					f, err := os.Open(p)
					if err != nil {
						continue
					}
					b, err := meteredRead(f, h, "drop "+d.Name, maxImport+1)
					f.Close()
					if err != nil || sha256Hex(b) != h {
						continue
					}
					name := m.Name
					if name == "" {
						name = strings.TrimPrefix(e.Name(), h[:12]+"-")
					}
					ir := l.Import(name, "leech:drop:"+d.Name, b, d.Path)
					r.OK, r.Item, r.From = ir.OK, ir.Item, "drop "+d.Name+" ("+p+")"
					if !ir.OK {
						r.Note = ir.Refused
					}
					return r
				}
			}
		}
	}
	// 3. exact sources (xs/as/ws http(s) URLs) — accepted only if SHA-256 matches a hash in the magnet
	for _, src := range m.Sources {
		if !strings.HasPrefix(src, "http://") && !strings.HasPrefix(src, "https://") {
			continue
		}
		r.Tried = append(r.Tried, "source "+src)
		if len(want) == 0 {
			r.Note = "magnet has only a v1 btih; a URL download cannot be verified without a SHA-256"
			continue
		}
		c := &http.Client{Timeout: 5 * time.Minute}
		t0 := time.Now()
		resp, err := c.Get(src)
		if err != nil {
			r.Note = err.Error()
			continue
		}
		b, err := meteredReadSince(io.LimitReader(resp.Body, maxImport+1), want[0], src, maxImport+1, t0)
		resp.Body.Close()
		if err != nil || resp.StatusCode/100 != 2 || len(b) > maxImport {
			r.Note = fmt.Sprintf("source http %d / %d bytes", resp.StatusCode, len(b))
			continue
		}
		h := sha256.Sum256(b)
		hs := hex.EncodeToString(h[:])
		match := false
		for _, w := range want {
			match = match || hs == w
		}
		if !match {
			r.Note = "downloaded bytes did not match the magnet hash; discarded"
			continue
		}
		name := m.Name
		if name == "" {
			name = filepath.Base(src)
		}
		ir := l.Import(name, "leech:"+src, b, "")
		if ir.Item != nil {
			l.mu.Lock()
			if x, ok := l.items[ir.Item.SHA256]; ok {
				has := false
				for _, s := range x.Sources {
					has = has || s == src
				}
				if !has {
					x.Sources = append(x.Sources, src)
					l.saveLocked()
				}
			}
			l.mu.Unlock()
		}
		r.OK, r.Item, r.From = ir.OK, ir.Item, src
		if !ir.OK {
			r.Note = ir.Refused
		}
		return r
	}
	if r.Note == "" {
		r.Note = "no copy found in the library, drop points or exact sources. This client has no peer swarm; seed the file on another device's drop point first."
	}
	return r
}

func sha256Hex(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
