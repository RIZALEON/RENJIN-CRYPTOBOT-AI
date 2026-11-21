package main

// RTOR peers + always-on keepalive (>= 1 KB/s each way, per file, from real transfers).
//
// Peer listener (--peer / RTOR_PEER_LISTEN, default 0.0.0.0:4985): LAN-only, separate from the loopback UI.
//   GET  /peer/v1/hello            {node, device, version, files:[{sha256,name,size}]}
//   GET  /peer/v1/file/<sha256>    library bytes (Range supported) — the peer leeches from us (our upload)
//   PUT  /peer/v1/file/<sha256>    a peer seeds to us (our download); accepted only if the body's SHA-256 matches
// Peer list (data/peers.json or RTOR_PEERS "name=url,…"), tried in order: Neo, Pixel, Moto, 17e…; then public
// RTRACKR (https://rizal.pw/rtrackr/data/, download-only: a static site cannot receive uploads).
// Keepalive per file: seed = paced PUT of the file to the first reachable peer (else a paced rewrite of a local drop
// copy); leech = paced Range download from the first peer that has it (else public RTRACKR if listed in its
// SHA256SUMS, else a local drop copy), with a SHA-256 check per chunk (against the local copy) and per pass.
// Every byte counted is a byte actually moved. If nothing is reachable the rate shows 0 and says why.

import (
	"bufio"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

var KeepaliveBps int64 = 1536 // per file, per direction; never below MinRateBps

const RTRACKRData = "https://rizal.pw/rtrackr/data/"

type Peer struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

type peerState struct {
	Peer
	Reachable bool            `json:"reachable"`
	Self      bool            `json:"self,omitempty"`
	Node      string          `json:"node,omitempty"`
	Device    string          `json:"device,omitempty"`
	Version   string          `json:"version,omitempty"`
	Files     map[string]bool `json:"-"`
	NFiles    int             `json:"files"`
	Checked   string          `json:"checked"`
	Err       string          `json:"err,omitempty"`
}

type KA struct {
	Via    string `json:"via"`
	Peer   string `json:"peer,omitempty"`
	Passes int    `json:"passes"`
	LastOK *bool  `json:"last_pass_sha_ok,omitempty"`
	Note   string `json:"note,omitempty"`
	At     string `json:"at,omitempty"`
}

type Net struct {
	mu      sync.Mutex
	node    string
	peers   []*peerState
	sums    map[string]string // RTRACKR SHA256SUMS: sha -> file name
	sumsAt  string
	ka      map[string]*KA // "up|sha" / "down|sha"
	running map[string]bool
	lib     *Library
	space   *Space
	allowIP map[string]bool
}

var pnet *Net

func defaultPeers() []Peer {
	return []Peer{{"neo", "http://192.168.0.113:4985"}, {"pixel", "http://192.168.0.206:4985"}, {"moto", "http://192.168.0.224:4985"}}
}

func loadPeers(data string) []Peer {
	if s := os.Getenv("RTOR_PEERS"); s != "" {
		var out []Peer
		for _, kv := range strings.Split(s, ",") {
			if n, u, ok := strings.Cut(strings.TrimSpace(kv), "="); ok {
				out = append(out, Peer{n, strings.TrimRight(u, "/")})
			}
		}
		return out
	}
	var f struct{ Peers []Peer }
	if b, err := os.ReadFile(filepath.Join(data, "peers.json")); err == nil && json.Unmarshal(b, &f) == nil && len(f.Peers) > 0 {
		return f.Peers
	}
	return defaultPeers()
}

func nodeID(data string) string {
	p := filepath.Join(data, "node-id")
	if b, err := os.ReadFile(p); err == nil && len(strings.TrimSpace(string(b))) >= 16 {
		return strings.TrimSpace(string(b))
	}
	r := make([]byte, 12)
	_, _ = rand.Read(r)
	id := hex.EncodeToString(r)
	_ = os.WriteFile(p, []byte(id+"\n"), 0o600)
	return id
}

func startNet(a *App) {
	if v, err := strconv.ParseInt(os.Getenv("RTOR_KEEPALIVE_BPS"), 10, 64); err == nil && v > 0 {
		KeepaliveBps = v
	}
	if KeepaliveBps < MinRateBps {
		KeepaliveBps = MinRateBps
	}
	n := &Net{node: nodeID(cfg.Data), sums: map[string]string{}, ka: map[string]*KA{}, running: map[string]bool{}, lib: a.lib, space: a.space, allowIP: map[string]bool{}}
	for _, p := range loadPeers(cfg.Data) {
		n.peers = append(n.peers, &peerState{Peer: p, Files: map[string]bool{}})
		if h, _, err := net.SplitHostPort(strings.TrimPrefix(strings.TrimPrefix(p.URL, "http://"), "https://")); err == nil {
			n.allowIP[h] = true
		}
	}
	pnet = n
	if l := env("RTOR_PEER_LISTEN", "0.0.0.0:4985"); l != "off" {
		go func() {
			srv := &http.Server{Addr: l, Handler: n.peerRoutes(), ReadHeaderTimeout: 10 * time.Second}
			if err := srv.ListenAndServe(); err != nil {
				fmt.Fprintln(os.Stderr, "peer listener:", err)
			}
		}()
	}
	go func() { // peer discovery: immediately, then every 15 s
		for {
			n.refresh()
			time.Sleep(15 * time.Second)
		}
	}()
	go func() { // RTRACKR SHA256SUMS (public, download-only): immediately, then every 10 min
		for {
			n.syncSums()
			time.Sleep(10 * time.Minute)
		}
	}()
	go func() { // keepalive supervisor: start per-file seed/leech loops as soon as files exist
		for {
			for _, it := range a.lib.List() {
				n.ensure("up", it.SHA256)
				n.ensure("down", it.SHA256)
			}
			time.Sleep(2 * time.Second)
		}
	}()
}

// ------------------------------------------------------------------ peer server (LAN only)

func lanIP(ip net.IP) bool {
	return ip != nil && (ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast())
}

func (n *Net) peerRoutes() http.Handler {
	mux := http.NewServeMux()
	guard := func(h http.HandlerFunc) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			host, _, _ := net.SplitHostPort(r.RemoteAddr)
			if !lanIP(net.ParseIP(host)) {
				http.Error(w, "LAN peers only", 403)
				return
			}
			h(w, r)
		}
	}
	mux.HandleFunc("/peer/v1/hello", guard(func(w http.ResponseWriter, r *http.Request) {
		var files []map[string]any
		for _, it := range n.lib.List() {
			files = append(files, map[string]any{"sha256": it.SHA256, "name": it.Name, "size": it.Size})
		}
		writeJSON(w, 200, map[string]any{"node": n.node, "device": cfg.Device, "version": Version, "files": files, "keepalive_bps": KeepaliveBps})
	}))
	mux.HandleFunc("/peer/v1/file/", guard(func(w http.ResponseWriter, r *http.Request) {
		sha := strings.ToLower(strings.TrimPrefix(r.URL.Path, "/peer/v1/file/"))
		if len(sha) != 64 {
			http.Error(w, "bad sha", 400)
			return
		}
		host, _, _ := net.SplitHostPort(r.RemoteAddr)
		switch r.Method {
		case "GET", "HEAD":
			it := n.lib.Get(sha)
			if it == nil {
				http.NotFound(w, r)
				return
			}
			f, err := os.Open(n.lib.path(it))
			if err != nil {
				http.NotFound(w, r)
				return
			}
			defer f.Close()
			mw := &meterW{w: w, key: sha}
			xfer.begin("up", sha)
			start := time.Now()
			http.ServeContent(mw, r, it.Name, time.Time{}, f)
			xfer.end("up", sha, mw.n, start, "served to peer "+host)
		case "PUT":
			known := n.lib.Get(sha) != nil
			if !known && !n.allowIP[host] {
				http.Error(w, "unknown sha from a non-listed peer", 403)
				return
			}
			b, err := meteredRead(io.LimitReader(r.Body, maxImport+1), sha, "seeded by peer "+host, maxImport+1)
			if err != nil || len(b) > maxImport {
				http.Error(w, "read failed", 400)
				return
			}
			if sha256Hex(b) != sha {
				writeJSON(w, 422, map[string]any{"ok": false, "refused": "SHA-256 mismatch; discarded"})
				return
			}
			if known {
				writeJSON(w, 200, map[string]any{"ok": true, "verified": true, "stored": "already in library (keepalive pass verified)"})
				return
			}
			name := filepath.Base(r.URL.Query().Get("name"))
			if name == "" || name == "." {
				name = sha[:12]
			}
			res := n.lib.Import(name, "peer:"+host, b, "")
			writeJSON(w, 200, map[string]any{"ok": res.OK, "verified": true, "stored": "imported", "refused": res.Refused})
		default:
			http.Error(w, "method", 405)
		}
	}))
	return mux
}

type meterW struct {
	w   http.ResponseWriter
	key string
	n   int64
}

func (m *meterW) Header() http.Header { return m.w.Header() }
func (m *meterW) WriteHeader(c int)   { m.w.WriteHeader(c) }
func (m *meterW) Write(p []byte) (int, error) {
	k, err := m.w.Write(p)
	m.n += int64(k)
	xfer.add("up", m.key, int64(k))
	return k, err
}

// ------------------------------------------------------------------ discovery

func (n *Net) refresh() {
	c := &http.Client{Timeout: 2500 * time.Millisecond}
	var wg sync.WaitGroup
	for _, p := range n.peers {
		wg.Add(1)
		go func(p *peerState) {
			defer wg.Done()
			var h struct {
				Node, Device, Version string
				Files                 []struct{ SHA256 string }
			}
			resp, err := c.Get(p.URL + "/peer/v1/hello")
			if err == nil {
				err = json.NewDecoder(io.LimitReader(resp.Body, 4<<20)).Decode(&h)
				resp.Body.Close()
			}
			n.mu.Lock()
			defer n.mu.Unlock()
			p.Checked = nowISO()
			if err != nil {
				p.Reachable, p.Err, p.NFiles = false, err.Error(), 0
				p.Files = map[string]bool{}
				return
			}
			p.Reachable, p.Err, p.Node, p.Device, p.Version = true, "", h.Node, h.Device, h.Version
			p.Self = h.Node == n.node
			p.Files = map[string]bool{}
			for _, f := range h.Files {
				p.Files[f.SHA256] = true
			}
			p.NFiles = len(p.Files)
		}(p)
	}
	wg.Wait()
}

func (n *Net) Peers() []peerState {
	n.mu.Lock()
	defer n.mu.Unlock()
	var out []peerState
	for _, p := range n.peers {
		out = append(out, *p)
	}
	return out
}

// livePeer returns the first reachable non-self peer (in list order), optionally one that has sha.
func (n *Net) livePeer(sha string, mustHave bool) *peerState {
	n.mu.Lock()
	defer n.mu.Unlock()
	for _, p := range n.peers {
		if p.Reachable && !p.Self && (!mustHave || p.Files[sha]) {
			c := *p
			return &c
		}
	}
	return nil
}

func (n *Net) syncSums() {
	c := &http.Client{Timeout: 20 * time.Second}
	resp, err := c.Get(RTRACKRData + "SHA256SUMS")
	if err != nil {
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return
	}
	m := map[string]string{}
	sc := bufio.NewScanner(io.LimitReader(resp.Body, 1<<20))
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		if len(f) >= 2 && len(f[0]) == 64 {
			m[strings.ToLower(f[0])] = strings.TrimPrefix(f[len(f)-1], "*")
		}
	}
	n.mu.Lock()
	n.sums, n.sumsAt = m, nowISO()
	n.mu.Unlock()
}

func (n *Net) rtrackrURL(sha string) string {
	n.mu.Lock()
	defer n.mu.Unlock()
	if name, ok := n.sums[sha]; ok {
		return RTRACKRData + name
	}
	return ""
}

// ------------------------------------------------------------------ keepalive loops

func (n *Net) ensure(dir, sha string) {
	k := dir + "|" + sha
	n.mu.Lock()
	if n.running[k] {
		n.mu.Unlock()
		return
	}
	n.running[k] = true
	n.ka[k] = &KA{Via: "starting"}
	n.mu.Unlock()
	go func() {
		for {
			var ka KA
			if dir == "up" {
				ka = n.seedPass(sha)
			} else {
				ka = n.leechPass(sha)
			}
			n.mu.Lock()
			old := n.ka[k]
			ka.Passes = old.Passes
			if ka.LastOK != nil {
				ka.Passes++
			}
			ka.At = nowISO()
			n.ka[k] = &ka
			n.mu.Unlock()
			if ka.LastOK == nil {
				time.Sleep(3 * time.Second) // nothing reachable: retry soon, rate truthfully 0
			}
		}
	}()
}

func (n *Net) KAState(dir, sha string) *KA {
	n.mu.Lock()
	defer n.mu.Unlock()
	if k, ok := n.ka[dir+"|"+sha]; ok {
		c := *k
		return &c
	}
	return nil
}

// pacer sleeps so that n bytes since start never exceed KeepaliveBps (keeps every stream >= the 1 KB/s floor, and light).
func pace(start time.Time, n int64) {
	want := time.Duration(float64(n) / float64(KeepaliveBps) * float64(time.Second))
	if el := time.Since(start); el < want {
		time.Sleep(want - el)
	}
}

type pacedReader struct {
	r     io.Reader
	key   string
	n     int64
	start time.Time
	h     io.Writer
}

func (p *pacedReader) Read(b []byte) (int, error) {
	if len(b) > 512 {
		b = b[:512]
	}
	k, err := p.r.Read(b)
	if k > 0 {
		p.h.Write(b[:k])
		p.n += int64(k)
		xfer.add("up", p.key, int64(k))
		pace(p.start, p.n)
	}
	return k, err
}

func okp(v bool) *bool { return &v }

func (n *Net) seedPass(sha string) KA {
	it := n.lib.Get(sha)
	if it == nil {
		return KA{Via: "none", Note: "not in library"}
	}
	if p := n.livePeer(sha, false); p != nil {
		f, err := os.Open(n.lib.path(it))
		if err != nil {
			return KA{Via: "none", Note: err.Error()}
		}
		defer f.Close()
		h := sha256.New()
		pr := &pacedReader{r: f, key: sha, start: time.Now(), h: h}
		req, _ := http.NewRequest("PUT", p.URL+"/peer/v1/file/"+sha+"?name="+urlQueryEscape(it.Name), pr)
		req.ContentLength = it.Size
		xfer.begin("up", sha)
		resp, err := (&http.Client{Timeout: time.Duration(it.Size/MinRateBps+60) * time.Second}).Do(req)
		xfer.end("up", sha, pr.n, pr.start, "seed → peer "+p.Name)
		if err != nil {
			return KA{Via: "peer", Peer: p.Name, Note: "upload failed: " + err.Error()}
		}
		var out struct {
			OK      bool
			Refused string
		}
		_ = json.NewDecoder(io.LimitReader(resp.Body, 1<<16)).Decode(&out)
		resp.Body.Close()
		ok := out.OK && hex.EncodeToString(h.Sum(nil)) == sha
		note := "peer verified the SHA-256 of the full pass"
		if !ok {
			note = "peer refused: " + out.Refused
		}
		return KA{Via: "peer", Peer: p.Name + " (" + p.URL + ")", LastOK: okp(ok), Note: note}
	}
	for _, d := range n.space.Drops() {
		if !d.Reachable {
			continue
		}
		dst := filepath.Join(d.Path, it.SHA256[:12]+"-"+it.Name)
		in, err := os.Open(n.lib.path(it))
		if err != nil {
			break
		}
		out, err := os.Create(dst + ".part")
		if err != nil {
			in.Close()
			continue
		}
		h := sha256.New()
		pr := &pacedReader{r: in, key: sha, start: time.Now(), h: h}
		xfer.begin("up", sha)
		_, err = io.Copy(out, pr)
		xfer.end("up", sha, pr.n, pr.start, "seed → local drop "+d.Name)
		in.Close()
		out.Close()
		ok := err == nil && hex.EncodeToString(h.Sum(nil)) == sha
		if ok {
			_ = os.Rename(dst+".part", dst)
		}
		return KA{Via: "local-drop", Peer: d.Path, LastOK: okp(ok), Note: "no reachable peer; seeding to this device's drop point (local)"}
	}
	return KA{Via: "none", Note: "no reachable peer or drop point — seed rate is 0 until one answers"}
}

func (n *Net) leechPass(sha string) KA {
	it := n.lib.Get(sha)
	if it == nil {
		return KA{Via: "none", Note: "not in library"}
	}
	type src struct{ via, name, url, path string }
	var s *src
	if p := n.livePeer(sha, true); p != nil {
		s = &src{"peer", p.Name + " (" + p.URL + ")", p.URL + "/peer/v1/file/" + sha, ""}
	} else if u := n.rtrackrURL(sha); u != "" {
		s = &src{"rtrackr-public", "rizal.pw/rtrackr", u, ""}
	} else {
		for _, d := range n.space.Drops() {
			p := filepath.Join(d.Path, sha[:12]+"-"+it.Name)
			if fi, err := os.Stat(p); err == nil && fi.Size() == it.Size {
				s = &src{"local-drop", d.Path, "", p}
				break
			}
		}
	}
	if s == nil {
		return KA{Via: "none", Note: "no reachable peer has this file, it is not on public RTRACKR, and no drop copy exists — leech rate is 0"}
	}
	local, err := os.Open(n.lib.path(it))
	if err != nil {
		return KA{Via: "none", Note: err.Error()}
	}
	defer local.Close()
	h := sha256.New()
	chunk := int64(KeepaliveBps) // one chunk ≈ one second at the keepalive rate
	start := time.Now()
	var got int64
	xfer.begin("down", sha)
	defer func() { xfer.end("down", sha, got, start, "leech ← "+s.via+" "+s.name) }()
	var df *os.File
	if s.path != "" {
		if df, err = os.Open(s.path); err != nil {
			return KA{Via: s.via, Peer: s.name, Note: err.Error()}
		}
		defer df.Close()
	}
	c := &http.Client{Timeout: 30 * time.Second}
	buf := make([]byte, chunk)
	lbuf := make([]byte, chunk)
	for off := int64(0); off < it.Size; off += chunk {
		want := chunk
		if off+want > it.Size {
			want = it.Size - off
		}
		var b []byte
		if df != nil {
			k, err := io.ReadFull(df, buf[:want])
			if err != nil {
				return KA{Via: s.via, Peer: s.name, LastOK: okp(false), Note: "drop read failed: " + err.Error()}
			}
			b = buf[:k]
		} else {
			req, _ := http.NewRequest("GET", s.url, nil)
			req.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", off, off+want-1))
			resp, err := c.Do(req)
			if err != nil {
				return KA{Via: s.via, Peer: s.name, Note: "download failed: " + err.Error()}
			}
			b, err = io.ReadAll(io.LimitReader(resp.Body, want+1))
			resp.Body.Close()
			if err != nil || (resp.StatusCode != 206 && !(resp.StatusCode == 200 && off == 0 && int64(len(b)) >= want)) {
				return KA{Via: s.via, Peer: s.name, Note: fmt.Sprintf("range request http %d", resp.StatusCode)}
			}
			if int64(len(b)) > want {
				b = b[:want]
			}
		}
		got += int64(len(b))
		xfer.add("down", sha, int64(len(b)))
		h.Write(b)
		// chunk check: SHA-256 of the received chunk must equal the SHA-256 of the same range of the verified local copy
		if _, err := local.ReadAt(lbuf[:len(b)], off); err == nil && sha256Hex(b) != sha256Hex(lbuf[:len(b)]) {
			return KA{Via: s.via, Peer: s.name, LastOK: okp(false), Note: fmt.Sprintf("chunk at %d failed its SHA-256 check", off)}
		}
		pace(start, got)
	}
	ok := hex.EncodeToString(h.Sum(nil)) == sha
	return KA{Via: s.via, Peer: s.name, LastOK: okp(ok), Note: "full pass re-verified by SHA-256"}
}
