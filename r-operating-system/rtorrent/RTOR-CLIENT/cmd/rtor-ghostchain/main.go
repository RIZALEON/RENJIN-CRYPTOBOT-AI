// RTOR GHOSTCHAIN cryptoclient — Renjin Torrent (RTOR client) + R:> Shell, served locally on 127.0.0.1:4984.
// Built from the RENJIN INSTALL PACKAGE (2026-11-20) and sites/RTOR-INSTALL.md.
//
// Rules this program keeps:
//   - Holds no keys, reads no keys, signs nothing, mints nothing. RMAIL never signs or mints.
//   - Re-seed waits for Rizal's RGHOSTKEY tap on the trusted device; this client has no seed and no key path.
//   - No invented speeds, peers or swarm. Only measured local facts are shown.
//   - The magnet link is used exactly as recorded (PKG + STATE hashes), never rebuilt from user input.
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	Version    = "0.2.3"
	ListenAddr = "127.0.0.1:4984"
	PkgSHA     = "3a19e054d6d3718d4f4a87a863dc97b691a7da578f820b8906197820400069c6"
	StateSHA   = "16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08"
	RTRACKRURL = "https://rizal.pw/rtrackr"
	// Recorded magnet, verbatim from records/RTOR-GHOSTCHAIN-TRANSPONDER.md. Do not retype or rebuild.
	Magnet = "magnet:?xt=urn:btih:3a19e054d6d3718d4f4a87a863dc97b691a7da578f820b8906197820400069c6&xt=urn:sha256:16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08&dn=RENJIN-CORE-V3.rzl&tr=https://rizal.pw/rtrackr"
)

// Published fingerprints (sites/RTOR-INSTALL.md table).
var rzlFiles = []struct{ Name, SHA string }{
	{"RENJIN-COMPONENT.rzl", "67a8c186f45de7359db1ff2c4385dceaeeda9d4d4ace5e79a1024ddb3184f5aa"},
	{"RENJIN-KUBO.rzl", "04b7b1e27d2198bce73936f0e96c09ce90e96fef0d06505f03c232bce98b3a97"},
}

// Default relay_8797 routes, tried in order. "send" = transponder envelope {to:"rmail-<addr>",from,type,body};
// "drop" = RMAIL v2 message posted as-is (the RKLOWD hub /rscale/rmail/drop shape). Override: RTOR_RMAIL_RELAYS.
var defaultRelays = []string{
	"send=http://127.0.0.1:8797/send",
	"drop=http://192.168.0.113:8797/rscale/rmail/drop",
}

//go:embed web
var webFS embed.FS

type Config struct {
	Data, Pkg, Addr, Device, From, To, RTRACKRPost string
	Relays                                         []string
	HeartbeatEvery                                 time.Duration
}

var cfg Config

func env(k, d string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return d
}

func defaultDataDir() string {
	if x := os.Getenv("XDG_DATA_HOME"); x != "" {
		return filepath.Join(x, "rtor-ghostchain")
	}
	h, _ := os.UserHomeDir()
	return filepath.Join(h, ".local", "share", "rtor-ghostchain")
}

func exeDir() string {
	p, err := os.Executable()
	if err != nil {
		return "."
	}
	if r, err := filepath.EvalSymlinks(p); err == nil {
		p = r
	}
	return filepath.Dir(p)
}

func nowISO() string { return time.Now().Format(time.RFC3339) }

func sha256File(p string) (string, int64, error) {
	f, err := os.Open(p)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, f)
	return hex.EncodeToString(h.Sum(nil)), n, err
}

// ---------------------------------------------------------------- RZL verify

type RzlResult struct {
	Name     string `json:"name"`
	Path     string `json:"path"`
	Expected string `json:"expected"`
	Got      string `json:"got"`
	Bytes    int64  `json:"bytes"`
	OK       bool   `json:"ok"`
	Err      string `json:"err,omitempty"`
}

func verifyRzl() ([]RzlResult, bool) {
	all := true
	var out []RzlResult
	for _, f := range rzlFiles {
		p := filepath.Join(cfg.Pkg, "rzl", f.Name)
		r := RzlResult{Name: f.Name, Path: p, Expected: f.SHA}
		got, n, err := sha256File(p)
		if err != nil {
			r.Err = err.Error()
		} else {
			r.Got, r.Bytes, r.OK = got, n, got == f.SHA
		}
		if !r.OK {
			all = false
		}
		out = append(out, r)
	}
	return out, all
}

func magnetCheck() (bool, string) {
	want := "xt=urn:btih:" + PkgSHA
	if !strings.Contains(Magnet, want) || !strings.Contains(Magnet, "xt=urn:sha256:"+StateSHA) || !strings.Contains(Magnet, "tr="+RTRACKRURL) {
		return false, "magnet does not carry the recorded PKG/STATE/tracker"
	}
	return true, "magnet carries PKG " + PkgSHA[:8] + "… STATE " + StateSHA[:8] + "… tracker " + RTRACKRURL
}

// ---------------------------------------------------------------- Ghost chain (local, append-only, unsigned)

type Entry struct {
	Schema    string          `json:"schema"`
	Seq       int             `json:"seq"`
	TS        string          `json:"ts"`
	Kind      string          `json:"kind"`
	Body      json.RawMessage `json:"body"`
	PrevHash  string          `json:"prev_hash"`
	EntryHash string          `json:"entry_hash"`
	Signed    bool            `json:"signed"`
}

type Chain struct {
	mu      sync.Mutex
	path    string
	entries []Entry
	onAdd   func(Entry)
}

func entryHash(e Entry) string {
	core := struct {
		Schema   string          `json:"schema"`
		Seq      int             `json:"seq"`
		TS       string          `json:"ts"`
		Kind     string          `json:"kind"`
		Body     json.RawMessage `json:"body"`
		PrevHash string          `json:"prev_hash"`
	}{e.Schema, e.Seq, e.TS, e.Kind, e.Body, e.PrevHash}
	b, _ := json.Marshal(core)
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])
}

func openChain(path string) (*Chain, error) {
	c := &Chain{path: path}
	b, err := os.ReadFile(path)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	for i, ln := range bytes.Split(b, []byte("\n")) {
		if len(bytes.TrimSpace(ln)) == 0 {
			continue
		}
		var e Entry
		if err := json.Unmarshal(ln, &e); err != nil {
			return nil, fmt.Errorf("chain line %d: %v", i+1, err)
		}
		c.entries = append(c.entries, e)
	}
	if len(c.entries) == 0 {
		// Genesis anchors the recorded Core v3 hashes. It is a record of those hashes, not a re-creation of Core v3.
		body, _ := json.Marshal(map[string]any{
			"anchor": "RENJIN Core v3 (recorded: 9 entries, chain_ok true)", "pkg_sha256": PkgSHA, "state": StateSHA,
			"magnet": Magnet, "tracker": RTRACKRURL, "note": "unsigned local client chain; signing only on the owner's RGHOSTKEY tap",
		})
		if _, err := c.appendLocked("genesis", body); err != nil {
			return nil, err
		}
	}
	return c, nil
}

func (c *Chain) appendLocked(kind string, body json.RawMessage) (Entry, error) {
	prev := strings.Repeat("0", 64)
	if n := len(c.entries); n > 0 {
		prev = c.entries[n-1].EntryHash
	}
	e := Entry{Schema: "rzl.rtor.ghostchain.client.v1", Seq: len(c.entries), TS: nowISO(), Kind: kind, Body: body, PrevHash: prev}
	e.EntryHash = entryHash(e)
	line, _ := json.Marshal(e)
	f, err := os.OpenFile(c.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return e, err
	}
	defer f.Close()
	if _, err := f.Write(append(line, '\n')); err != nil {
		return e, err
	}
	_ = f.Sync()
	c.entries = append(c.entries, e)
	return e, nil
}

func (c *Chain) Append(kind string, body any) (Entry, error) {
	b, _ := json.Marshal(body)
	c.mu.Lock()
	e, err := c.appendLocked(kind, b)
	cb := c.onAdd
	c.mu.Unlock()
	if err == nil && cb != nil {
		go cb(e)
	}
	return e, err
}

type VerifyResult struct {
	OK       bool     `json:"ok"`
	Height   int      `json:"height"`
	Head     string   `json:"head"`
	Problems []string `json:"problems"`
	Anchor   bool     `json:"anchor_matches_recorded"`
}

func (c *Chain) Verify() VerifyResult {
	c.mu.Lock()
	defer c.mu.Unlock()
	r := VerifyResult{Height: len(c.entries), Problems: []string{}}
	prev := strings.Repeat("0", 64)
	for i, e := range c.entries {
		if e.Seq != i {
			r.Problems = append(r.Problems, fmt.Sprintf("#%d seq %d out of order", i, e.Seq))
		}
		if e.PrevHash != prev {
			r.Problems = append(r.Problems, fmt.Sprintf("#%d prev_hash does not link", i))
		}
		if entryHash(e) != e.EntryHash {
			r.Problems = append(r.Problems, fmt.Sprintf("#%d entry_hash does not recompute", i))
		}
		prev = e.EntryHash
	}
	if len(c.entries) > 0 {
		var g map[string]any
		_ = json.Unmarshal(c.entries[0].Body, &g)
		r.Anchor = g["pkg_sha256"] == PkgSHA && g["state"] == StateSHA && g["magnet"] == Magnet
		if !r.Anchor {
			r.Problems = append(r.Problems, "genesis does not carry the recorded PKG/STATE/magnet")
		}
		r.Head = prev
	}
	r.OK = len(r.Problems) == 0
	return r
}

func (c *Chain) Tail(n int) []Entry {
	c.mu.Lock()
	defer c.mu.Unlock()
	if n > len(c.entries) {
		n = len(c.entries)
	}
	return append([]Entry(nil), c.entries[len(c.entries)-n:]...)
}

func (c *Chain) Head() (int, string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.entries) == 0 {
		return 0, ""
	}
	return len(c.entries), c.entries[len(c.entries)-1].EntryHash
}

// ---------------------------------------------------------------- RMAIL outbox over relay_8797

type RMail struct {
	V          int    `json:"v"`
	Kind       string `json:"kind"`
	ID         string `json:"id"`
	To         string `json:"to"`
	ToAddr     string `json:"to_addr"`
	From       string `json:"from"`
	FromAddr   string `json:"from_addr"`
	FromDevice string `json:"from_device"`
	Text       string `json:"text"`
	Origin     string `json:"origin"`
	TS         int64  `json:"ts"`
	Verified   bool   `json:"verified"`
	Type       string `json:"rtor_type,omitempty"`
}

type OutItem struct {
	Msg      RMail           `json:"msg"`
	Queued   string          `json:"queued"`
	Tries    int             `json:"tries"`
	NextTry  int64           `json:"next_try"`
	LastErr  string          `json:"last_err,omitempty"`
	Sent     string          `json:"sent,omitempty"`
	Ack      json.RawMessage `json:"ack,omitempty"`
	AckRelay string          `json:"ack_relay,omitempty"`
}

type Outbox struct {
	fmu   sync.Mutex // serializes Flush so an item is never sent twice at once
	mu    sync.Mutex
	path  string
	items []OutItem
	kick  chan struct{}
}

func openOutbox(p string) *Outbox {
	o := &Outbox{path: p, kick: make(chan struct{}, 1)}
	if b, err := os.ReadFile(p); err == nil {
		_ = json.Unmarshal(b, &o.items)
	}
	return o
}

func (o *Outbox) saveLocked() {
	b, _ := json.MarshalIndent(o.items, "", " ")
	tmp := o.path + ".tmp"
	if os.WriteFile(tmp, b, 0o600) == nil {
		_ = os.Rename(tmp, o.path)
	}
}

func addrOf(h string) string {
	h = strings.TrimSpace(h)
	if h == "" {
		return "@chaserizal"
	}
	return h
}

func box(a string) string {
	var b strings.Builder
	for _, r := range a {
		if (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			b.WriteRune(r)
		} else {
			b.WriteRune('_')
		}
	}
	s := b.String()
	if len(s) > 64 {
		s = s[:64]
	}
	return "rmail-" + s
}

func newID() string {
	var r [4]byte
	f, _ := os.Open("/dev/urandom")
	if f != nil {
		_, _ = io.ReadFull(f, r[:])
		f.Close()
	}
	return strconv.FormatInt(time.Now().UnixMilli(), 36) + hex.EncodeToString(r[:])[:5]
}

func (o *Outbox) Queue(to, text, typ string) RMail {
	if len(text) > 4000 {
		text = text[:4000]
	}
	m := RMail{V: 2, Kind: "rmail", ID: newID(), To: addrOf(to), ToAddr: addrOf(to), From: cfg.From, FromAddr: cfg.From,
		FromDevice: cfg.Device, Text: text, Origin: "rtor-ghostchain/" + Version, TS: time.Now().UnixMilli(), Verified: false, Type: typ}
	o.mu.Lock()
	o.items = append(o.items, OutItem{Msg: m, Queued: nowISO()})
	if len(o.items) > 2000 { // keep sent history bounded, never drop unsent
		var keep []OutItem
		drop := len(o.items) - 2000
		for _, it := range o.items {
			if drop > 0 && it.Sent != "" {
				drop--
				continue
			}
			keep = append(keep, it)
		}
		o.items = keep
	}
	o.saveLocked()
	o.mu.Unlock()
	select {
	case o.kick <- struct{}{}:
	default:
	}
	return m
}

func (o *Outbox) Snapshot() (pending, sent int, items []OutItem) {
	o.mu.Lock()
	defer o.mu.Unlock()
	for _, it := range o.items {
		if it.Sent == "" {
			pending++
		} else {
			sent++
		}
	}
	n := len(o.items)
	s := n - 50
	if s < 0 {
		s = 0
	}
	return pending, sent, append([]OutItem(nil), o.items[s:]...)
}

var httpc = &http.Client{Timeout: 5 * time.Second}

func postRelay(spec string, m RMail) (json.RawMessage, error) {
	mode, url := "drop", spec
	if i := strings.Index(spec, "="); i > 0 && !strings.Contains(spec[:i], "/") {
		mode, url = spec[:i], spec[i+1:]
	}
	var payload []byte
	msg, _ := json.Marshal(m)
	if mode == "send" {
		payload, _ = json.Marshal(map[string]string{"to": box(m.ToAddr), "from": m.FromAddr, "type": "rmail", "body": string(msg)})
	} else {
		payload = msg
	}
	req, _ := http.NewRequest("POST", url, bytes.NewReader(payload))
	req.Header.Set("Content-Type", "text/plain")
	req.Header.Set("User-Agent", "rtor-ghostchain/"+Version)
	resp, err := httpc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<16))
	if resp.StatusCode/100 != 2 {
		return nil, fmt.Errorf("http-%d", resp.StatusCode)
	}
	var ack struct {
		OK bool   `json:"ok"`
		ID string `json:"id"`
	}
	if json.Unmarshal(b, &ack) != nil || !ack.OK || ack.ID == "" {
		return nil, fmt.Errorf("bad-ack")
	}
	return b, nil
}

// Flush tries every unsent item whose backoff has elapsed. Undelivered mail stays in the outbox.
func (o *Outbox) Flush(force bool) (delivered, failed int) {
	o.fmu.Lock()
	defer o.fmu.Unlock()
	o.mu.Lock()
	var idx []int
	now := time.Now().Unix()
	for i, it := range o.items {
		if it.Sent == "" && (force || it.NextTry <= now) {
			idx = append(idx, i)
		}
	}
	work := make([]OutItem, len(idx))
	for k, i := range idx {
		work[k] = o.items[i]
	}
	o.mu.Unlock()
	for k := range work {
		it := &work[k]
		var errs []string
		for _, r := range cfg.Relays {
			ack, err := postRelay(r, it.Msg)
			if err == nil {
				it.Sent, it.Ack, it.AckRelay, it.LastErr = nowISO(), ack, r, ""
				break
			}
			errs = append(errs, r+": "+err.Error())
		}
		it.Tries++
		if it.Sent == "" {
			back := 30 * (1 << min(it.Tries-1, 5)) // 30s .. 16min
			it.NextTry = time.Now().Unix() + int64(back)
			it.LastErr = strings.Join(errs, " | ")
			failed++
		} else {
			delivered++
		}
	}
	o.mu.Lock()
	for k, i := range idx {
		if i < len(o.items) && o.items[i].Msg.ID == work[k].Msg.ID {
			o.items[i] = work[k]
		}
	}
	o.saveLocked()
	o.mu.Unlock()
	return
}

// ---------------------------------------------------------------- RTRACKR heartbeat

type Heart struct {
	mu       sync.Mutex
	path     string
	last     map[string]any
	lastPost string
}

func (h *Heart) Beat(c *Chain, ob *Outbox, reason string, viaRMail bool) map[string]any {
	height, head := c.Head()
	pend, _, _ := ob.Snapshot()
	hb := map[string]any{
		"schema": "rzl.rtor.heartbeat.v1", "ts": nowISO(), "device": cfg.Device, "client": "rtor-ghostchain/" + Version,
		"os": runtime.GOOS + "/" + runtime.GOARCH, "chain_height": height, "chain_head": head, "reason": reason,
		"pkg_sha256": PkgSHA, "state": StateSHA, "tracker": RTRACKRURL, "rmail_outbox_pending": pend,
		"signed": false, "measured_speed": nil, "peers": nil,
	}
	b, _ := json.Marshal(hb)
	if f, err := os.OpenFile(h.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600); err == nil {
		_, _ = f.Write(append(b, '\n'))
		f.Close()
	}
	status := "staged locally (no RTRACKR post URL configured; rizal.pw/rtrackr is a published static page)"
	if cfg.RTRACKRPost != "" {
		req, _ := http.NewRequest("POST", cfg.RTRACKRPost, bytes.NewReader(b))
		req.Header.Set("Content-Type", "application/json")
		if resp, err := httpc.Do(req); err != nil {
			status = "post failed: " + err.Error()
		} else {
			status = "posted: http " + strconv.Itoa(resp.StatusCode)
			resp.Body.Close()
		}
	}
	if viaRMail {
		ob.Queue("rtrackr", string(b), "rtor-heartbeat")
		status += "; chain head queued as RMAIL to rtrackr over relay_8797"
	}
	h.mu.Lock()
	h.last, h.lastPost = hb, status
	h.mu.Unlock()
	return hb
}

// ---------------------------------------------------------------- HTTP

type App struct {
	pmu     sync.Mutex
	pending []string
	lib     *Library
	space   *Space
	chain   *Chain
	ob      *Outbox
	heart   *Heart
	start   time.Time
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	enc := json.NewEncoder(w)
	enc.SetIndent("", " ")
	_ = enc.Encode(v)
}

// localOnly refuses anything that is not a same-origin request from the loopback UI.
func localOnly(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		host, _, _ := net.SplitHostPort(r.RemoteAddr)
		if ip := net.ParseIP(host); ip == nil || !ip.IsLoopback() {
			writeJSON(w, 403, map[string]any{"ok": false, "err": "loopback only"})
			return
		}
		if r.Method == "POST" {
			if o := r.Header.Get("Origin"); o != "" && o != "http://"+cfg.Addr && o != "http://localhost:"+portOf(cfg.Addr) {
				writeJSON(w, 403, map[string]any{"ok": false, "err": "cross-origin refused"})
				return
			}
		}
		next(w, r)
	}
}

func portOf(a string) string { _, p, _ := net.SplitHostPort(a); return p }

func (a *App) status() map[string]any {
	rz, rzOK := verifyRzl()
	mOK, mMsg := magnetCheck()
	height, head := a.chain.Head()
	pend, sent, _ := a.ob.Snapshot()
	a.heart.mu.Lock()
	last, lastPost := a.heart.last, a.heart.lastPost
	a.heart.mu.Unlock()
	var files []map[string]any
	for _, v := range a.lib.Views() {
		files = append(files, map[string]any{"name": v.Name, "sha256": v.SHA256, "seeding_on": v.SeedOn, "leeching_on": v.LeechOn,
			"seed_bps": v.Seeding.RateBps, "leech_bps": v.Leeching.RateBps, "seed_via": v.Seeding.Keepalive, "leech_via": v.Leeching.Keepalive})
	}
	var live []string
	if pnet != nil {
		for _, p := range pnet.Peers() {
			if p.Reachable && !p.Self {
				live = append(live, p.Name)
			}
		}
	}
	xfers := map[string]any{"files": files, "peers_live": live, "keepalive_bps": KeepaliveBps, "floor_bps": MinRateBps, "window_s": int(rateWindow / time.Second)}
	return map[string]any{
		"transfers": xfers,
		"reseed":    reseedNow(),
		"client":    "RTOR GHOSTCHAIN cryptoclient " + Version, "os": runtime.GOOS + "/" + runtime.GOARCH, "device": cfg.Device,
		"listen": cfg.Addr, "uptime_s": int(time.Since(a.start).Seconds()), "rzl": rz, "rzl_ok": rzOK,
		"magnet": Magnet, "magnet_ok": mOK, "magnet_check": mMsg, "chain_height": height, "chain_head": head,
		"rmail":          map[string]any{"relay": "relay_8797", "routes": cfg.Relays, "outbox_pending": pend, "sent": sent},
		"rtrackr":        map[string]any{"tracker": RTRACKRURL, "post_url": cfg.RTRACKRPost, "last_heartbeat": last, "last_post": lastPost},
		"activation":     "not confirmed until the entry appears on RTRACKR (rizal.pw/rtrackr)",
		"measured_speed": nil, "peers": nil, "swarm": "none claimed",
		"space": a.spaceInfo(), "library_items": len(a.lib.List()),
	}
}

func (a *App) routes() http.Handler {
	mux := http.NewServeMux()
	sub, _ := fs.Sub(webFS, "web")
	page := func(name string) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			b, err := fs.ReadFile(sub, name)
			if err != nil {
				http.NotFound(w, r)
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write(b)
		}
	}
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.FileServer(http.FS(sub)).ServeHTTP(w, r)
			return
		}
		page("index.html")(w, r)
	})
	mux.HandleFunc("/torrent", page("RENJIN-TORRENT.html"))
	mux.HandleFunc("/shell", page("R-SHELL.html"))
	mux.HandleFunc("/api/status", localOnly(func(w http.ResponseWriter, r *http.Request) { writeJSON(w, 200, a.status()) }))
	mux.HandleFunc("/api/magnet", localOnly(func(w http.ResponseWriter, r *http.Request) {
		ok, msg := magnetCheck()
		writeJSON(w, 200, map[string]any{"magnet": Magnet, "ok": ok, "check": msg})
	}))
	mux.HandleFunc("/api/chain", localOnly(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"tail": a.chain.Tail(25)})
	}))
	mux.HandleFunc("/api/chain/verify", localOnly(func(w http.ResponseWriter, r *http.Request) {
		v := a.chain.Verify()
		if r.Method == "POST" {
			_, _ = a.chain.Append("chain-verify", map[string]any{"ok": v.OK, "height": v.Height, "head": v.Head})
		}
		writeJSON(w, 200, v)
	}))
	mux.HandleFunc("/api/rmail/send", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		var in struct{ To, Text string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		if strings.TrimSpace(in.Text) == "" {
			writeJSON(w, 400, map[string]any{"ok": false, "err": "empty"})
			return
		}
		m := a.ob.Queue(in.To, in.Text, "rmail")
		_, _ = a.chain.Append("rmail-queued", map[string]any{"id": m.ID, "to": m.To, "text_sha256": shaStr(m.Text)})
		writeJSON(w, 200, map[string]any{"ok": true, "queued": m, "delivery": "queued in outbox; relay_8797 delivery runs in the background (see outbox)"})
	}))
	mux.HandleFunc("/api/rmail/send-magnet", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		m := sendMagnet(a)
		writeJSON(w, 200, map[string]any{"ok": true, "queued": m, "delivery": "queued in outbox; relay_8797 delivery runs in the background (see outbox)",
			"note": "activation is confirmed only when the entry appears on RTRACKR"})
	}))
	mux.HandleFunc("/api/rmail/outbox", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			d, f := a.ob.Flush(true)
			writeJSON(w, 200, map[string]any{"delivered": d, "still_queued": f})
			return
		}
		p, s, items := a.ob.Snapshot()
		writeJSON(w, 200, map[string]any{"pending": p, "sent": s, "items": items})
	}))
	mux.HandleFunc("/api/rtrackr/heartbeat", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			writeJSON(w, 200, a.heart.Beat(a.chain, a.ob, "manual", false))
			return
		}
		a.heart.mu.Lock()
		defer a.heart.mu.Unlock()
		writeJSON(w, 200, map[string]any{"last": a.heart.last, "post": a.heart.lastPost})
	}))
	mux.HandleFunc("/api/space", localOnly(func(w http.ResponseWriter, r *http.Request) { writeJSON(w, 200, a.spaceInfo()) }))
	mux.HandleFunc("/api/library", localOnly(func(w http.ResponseWriter, r *http.Request) {
		var peers []peerState
		if pnet != nil {
			peers = pnet.Peers()
		}
		writeJSON(w, 200, map[string]any{"items": a.lib.Views(), "leech_queue": a.lib.Queue(), "rate_floor_bps": MinRateBps, "keepalive_bps": KeepaliveBps, "peers": peers,
			"rtrackr_public": RTRACKRData + " (download-only: static site, cannot receive uploads)",
			"limits":         map[string]any{"up_bps": xfer.limit("up"), "down_bps": xfer.limit("down"), "note": "0 = unlimited; any set limit is raised to at least 1 KB/s"},
			"always_on":      "seeding keeps a verified copy in every reachable drop point; leeching re-checks queued magnets every 30 s",
			"rates":          "measured from real byte counters over a 10 s window; 0 B/s = idle — no peer/drop transfer"})
	}))
	mux.HandleFunc("/api/library/raw", localOnly(func(w http.ResponseWriter, r *http.Request) {
		it := a.lib.Get(r.URL.Query().Get("sha"))
		if it == nil {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Disposition", "attachment; filename=\""+strings.ReplaceAll(it.Name, "\"", "")+"\"")
		http.ServeFile(w, r, a.lib.path(it))
	}))
	mux.HandleFunc("/api/import", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		name := r.Header.Get("X-Filename")
		if n, err := url.QueryUnescape(name); err == nil {
			name = n
		}
		b, err := io.ReadAll(io.LimitReader(r.Body, maxImport+1))
		if err != nil || len(b) > maxImport {
			writeJSON(w, 413, map[string]any{"ok": false, "refused": "too large or unreadable (limit 512 MB)"})
			return
		}
		src := r.Header.Get("X-Source")
		if src == "" {
			src = "open"
		}
		res := a.importBytes(name, src, b, "")
		go a.lib.ensureSeeded(a.space)
		code := 200
		if !res.OK {
			code = 422
		}
		writeJSON(w, code, res)
	}))
	mux.HandleFunc("/api/magnet/parse", localOnly(func(w http.ResponseWriter, r *http.Request) {
		var in struct{ Magnet string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		mi, err := parseMagnet(in.Magnet)
		e := ""
		if err != nil {
			e = err.Error()
		}
		writeJSON(w, 200, map[string]any{"magnet": mi, "err": e})
	}))
	mux.HandleFunc("/api/seed", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		var in struct{ SHA256 string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		res, code := a.seed(in.SHA256)
		writeJSON(w, code, res)
	}))
	mux.HandleFunc("/api/leech", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		var in struct{ Magnet string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		writeJSON(w, 200, a.leech(in.Magnet))
	}))
	mux.HandleFunc("/api/pending-open", localOnly(func(w http.ResponseWriter, r *http.Request) {
		a.pmu.Lock()
		defer a.pmu.Unlock()
		if r.Method == "POST" {
			var in struct{ URL string }
			_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
			if strings.TrimSpace(in.URL) != "" {
				a.pending = append(a.pending, strings.TrimSpace(in.URL))
			}
			writeJSON(w, 200, map[string]any{"ok": true})
			return
		}
		out := a.pending
		a.pending = nil
		writeJSON(w, 200, map[string]any{"urls": out})
	}))
	// Local import for platform hand-offs (Ubuntu Touch Content Hub): only paths under RTOR_IMPORT_DIRS.
	mux.HandleFunc("/api/import-local", localOnly(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			writeJSON(w, 405, map[string]any{"ok": false})
			return
		}
		var in struct{ Path string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		p := strings.TrimPrefix(in.Path, "file://")
		if u, err := url.PathUnescape(p); err == nil {
			p = u
		}
		p = filepath.Clean(p)
		allowed := false
		for _, d := range filepath.SplitList(os.Getenv("RTOR_IMPORT_DIRS")) {
			if d != "" && strings.HasPrefix(p, filepath.Clean(d)+string(os.PathSeparator)) {
				allowed = true
			}
		}
		if !allowed {
			writeJSON(w, 403, map[string]any{"ok": false, "refused": "path not under an allowed import dir"})
			return
		}
		b, err := os.ReadFile(p)
		if err != nil || len(b) > maxImport {
			writeJSON(w, 422, map[string]any{"ok": false, "refused": "unreadable or too large"})
			return
		}
		res := a.importBytes(filepath.Base(p), "content-hub", b, "")
		code := 200
		if !res.OK {
			code = 422
		}
		writeJSON(w, code, res)
	}))
	mux.HandleFunc("/api/reseed", localOnly(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 409, map[string]any{"ok": false, "state": "waiting",
			"needs": "RGHOSTKEY tap by Rizal on the trusted device. This client holds no key and no seed, and cannot re-seed by itself."})
	}))
	return mux
}

func (a *App) spaceInfo() map[string]any {
	if a.space == nil {
		return map[string]any{"loaded": false, "note": "no SPACE-RID.json found (looked in --space, RTOR_SPACE, data dir, package dir)"}
	}
	return map[string]any{"loaded": true, "source": a.space.Source, "rid": a.space.RID, "space": a.space.Space,
		"rklowd_node": a.space.RKLOWDNode, "rmail_address": a.space.RMailAddr, "drop_points": a.space.Drops()}
}

func (a *App) importBytes(name, src string, b []byte, sumsDir string) ImportResult {
	res := a.lib.Import(name, src, b, sumsDir)
	if res.OK && res.Item != nil && !res.Dup {
		_, _ = a.chain.Append("rtor-import", map[string]any{"sha256": res.Item.SHA256, "name": res.Item.Name, "type": res.Item.Type, "size": res.Item.Size})
	}
	return res
}

func (a *App) seed(sha string) (map[string]any, int) {
	it, notes, err := a.lib.Seed(sha, a.space)
	if err != nil {
		return map[string]any{"ok": false, "err": err.Error()}, 404
	}
	to := cfg.To
	if a.space != nil && a.space.RMailAddr != "" {
		to = a.space.RMailAddr
	}
	text := "RTOR seed: " + it.Name + " (" + strconv.FormatInt(it.Size, 10) + " B)\n" + it.Magnet + "\nsha256 " + it.SHA256
	if a.space != nil {
		text += "\nrid " + a.space.RID + " · space " + a.space.Space
	}
	m := a.ob.Queue(to, text, "rtor-seed")
	_, _ = a.chain.Append("rtor-seed", map[string]any{"sha256": it.SHA256, "name": it.Name, "drop_copies": len(it.Seeded), "rmail_id": m.ID, "rmail_to": to})
	return map[string]any{"ok": true, "item": it, "notes": notes, "rmail": map[string]any{"id": m.ID, "to": to, "delivery": "queued in outbox; relay_8797 delivery runs in the background"}}, 200
}

func (a *App) leech(magnet string) LeechResult {
	r := a.lib.Leech(magnet, a.space)
	if !r.OK && strings.HasPrefix(strings.ToLower(strings.TrimSpace(magnet)), "magnet:?") && len(r.Magnet.hashes()) > 0 {
		a.lib.enqueue(strings.TrimSpace(magnet), r.Note) // leeching is always on: keep re-checking this magnet
		r.Note += " · queued: leeching stays on and re-checks library, drops and sources every 30 s"
	}
	if r.OK && r.Item != nil {
		go a.lib.ensureSeeded(a.space) // seeding is always on: place the new file in the drop points now
		_, _ = a.chain.Append("rtor-leech", map[string]any{"sha256": r.Item.SHA256, "name": r.Item.Name, "from": r.From})
	}
	return r
}

func shaStr(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func sendMagnet(a *App) RMail {
	text := "RTOR GHOSTCHAIN magnet (RMAIL crypto torrent link, as recorded):\n" + Magnet +
		"\nPKG SHA-256 " + PkgSHA + "\nSTATE " + StateSHA + "\nfrom " + cfg.Device + " · unsigned · no keys"
	m := a.ob.Queue(cfg.To, text, "rtor-magnet")
	_, _ = a.chain.Append("magnet-queued", map[string]any{"id": m.ID, "to": m.To, "magnet_sha256": shaStr(Magnet)})
	return m
}

// ---------------------------------------------------------------- Android/static-linux network fallbacks

func netFallbacks() {
	if _, err := os.Stat("/etc/resolv.conf"); err != nil {
		dns := strings.Split(env("RTOR_DNS", "1.1.1.1:53,8.8.8.8:53"), ",")
		net.DefaultResolver = &net.Resolver{PreferGo: true, Dial: func(ctx context.Context, network, _ string) (net.Conn, error) {
			var d net.Dialer
			var last error
			for _, s := range dns {
				c, err := d.DialContext(ctx, network, strings.TrimSpace(s))
				if err == nil {
					return c, nil
				}
				last = err
			}
			return nil, last
		}}
	}
	if os.Getenv("SSL_CERT_DIR") == "" {
		if _, err := os.Stat("/system/etc/security/cacerts"); err == nil {
			os.Setenv("SSL_CERT_DIR", "/system/etc/security/cacerts")
		}
	}
}

// ---------------------------------------------------------------- main

func setup(data, pkg, addr, space string) (*App, error) {
	hn, _ := os.Hostname()
	cfg = Config{Data: data, Pkg: pkg, Addr: addr, Device: env("RTOR_DEVICE", "rtor-"+runtime.GOOS+"-"+hn),
		From: env("RTOR_FROM", "rtor-client"), To: env("RTOR_MAGNET_TO", "rtrackr"), RTRACKRPost: env("RTOR_RTRACKR_POST_URL", ""),
		HeartbeatEvery: 5 * time.Minute}
	if s := env("RTOR_HEARTBEAT_SECONDS", ""); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n >= 15 {
			cfg.HeartbeatEvery = time.Duration(n) * time.Second
		}
	}
	cfg.Relays = defaultRelays
	if s := env("RTOR_RMAIL_RELAYS", ""); s != "" {
		cfg.Relays = strings.Split(s, ",")
	}
	if err := os.MkdirAll(data, 0o700); err != nil {
		return nil, err
	}
	c, err := openChain(filepath.Join(data, "ghostchain.jsonl"))
	if err != nil {
		return nil, err
	}
	sp := loadSpace(space, os.Getenv("RTOR_SPACE"), filepath.Join(data, "SPACE-RID.json"), filepath.Join(pkg, "SPACE-RID.json"))
	return &App{lib: openLibrary(filepath.Join(data, "library")), space: sp, chain: c, ob: openOutbox(filepath.Join(data, "rmail-outbox.json")),
		heart: &Heart{path: filepath.Join(data, "rtrackr-heartbeats.jsonl")}, start: time.Now()}, nil
}

func runCheck(a *App) int {
	fail := 0
	fmt.Println("RTOR GHOSTCHAIN cryptoclient " + Version + " --check (" + runtime.GOOS + "/" + runtime.GOARCH + ")")
	rz, _ := verifyRzl()
	for _, r := range rz {
		st := "OK  "
		if !r.OK {
			st, fail = "FAIL", fail+1
		}
		fmt.Printf("  [%s] sha256 %s  %s (%d B)%s\n", st, r.Name, r.Got, r.Bytes, map[bool]string{true: "", false: "  expected " + r.Expected + " " + r.Err}[r.OK])
	}
	if ok, msg := magnetCheck(); ok {
		fmt.Println("  [OK  ] " + msg)
	} else {
		fmt.Println("  [FAIL] " + msg)
		fail++
	}
	sub, _ := fs.Sub(webFS, "web")
	for _, p := range []string{"index.html", "RENJIN-TORRENT.html", "R-SHELL.html"} {
		if _, err := fs.Stat(sub, p); err != nil {
			fmt.Println("  [FAIL] web/" + p + " missing")
			fail++
		} else {
			fmt.Println("  [OK  ] web/" + p + " embedded")
		}
	}
	v := a.chain.Verify()
	if v.OK {
		fmt.Printf("  [OK  ] CHAIN VERIFY height %d head %s\n", v.Height, v.Head)
	} else {
		fmt.Printf("  [FAIL] CHAIN VERIFY %v\n", v.Problems)
		fail++
	}
	fmt.Println("  [WAIT] re-seed: needs Rizal's RGHOSTKEY tap on the trusted device (client holds no keys)")
	if fail > 0 {
		fmt.Printf("check FAILED (%d)\n", fail)
		return 1
	}
	fmt.Println("check PASSED")
	return 0
}

func serve(a *App) int {
	if lp := os.Getenv("RTOR_LOG"); lp != "" {
		if f, err := os.OpenFile(lp, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600); err == nil {
			log.SetOutput(f)
		}
	}
	ln, err := net.Listen("tcp", cfg.Addr)
	if err != nil {
		log.Printf("listen %s: %v", cfg.Addr, err)
		return 1
	}
	if _, ok := verifyRzl(); !ok {
		log.Printf("WARNING: .rzl SHA256 check failed — activation must not proceed (see /api/status)")
	}
	// After every new chain entry: chain head + heartbeat to RTRACKR (staged/posted) and as RMAIL over relay_8797.
	a.chain.mu.Lock()
	a.chain.onAdd = func(e Entry) {
		a.heart.Beat(a.chain, a.ob, "new-entry #"+strconv.Itoa(e.Seq)+" "+e.Kind, true)
	}
	a.chain.mu.Unlock()
	_, _ = a.chain.Append("client-start", map[string]any{"version": Version, "os": runtime.GOOS + "/" + runtime.GOARCH, "listen": cfg.Addr})
	go a.alwaysOn() // seeding + leeching are always on
	startReseed()   // RE-SEED panel watches the live RGHOSTCHAIN for the sealed RGHOSTKEY block 6
	startNet(a)     // peers + per-file keepalive (>= 1 KB/s each way) — connects immediately
	srv := &http.Server{Handler: a.routes(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		t := time.NewTicker(20 * time.Second)
		hb := time.NewTicker(cfg.HeartbeatEvery)
		for {
			select {
			case <-t.C:
				a.ob.Flush(false)
			case <-a.ob.kick:
				time.Sleep(500 * time.Millisecond)
				a.ob.Flush(false)
			case <-hb.C:
				a.heart.Beat(a.chain, a.ob, "interval", false)
			}
		}
	}()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sig
		ctx, c := context.WithTimeout(context.Background(), 3*time.Second)
		defer c()
		_ = srv.Shutdown(ctx)
	}()
	log.Printf("RTOR GHOSTCHAIN cryptoclient %s serving R:> Shell on http://%s (data %s)", Version, cfg.Addr, cfg.Data)
	if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Print(err)
		return 1
	}
	return 0
}

func main() {
	netFallbacks()
	fsx := flag.NewFlagSet("rtor-ghostchain", flag.ExitOnError)
	data := fsx.String("data", env("RTOR_DATA", defaultDataDir()), "state dir (ghost chain, RMAIL outbox, heartbeats)")
	pkg := fsx.String("pkg", env("RTOR_PKG", filepath.Dir(exeDir())), "package dir containing rzl/")
	addr := fsx.String("addr", env("RTOR_ADDR", ListenAddr), "listen address (loopback)")
	space := fsx.String("space", "", "path to this space's SPACE-RID.json (rid, space, rklowd_node, rmail_address, drop_paths)")
	check := fsx.Bool("check", false, "verify .rzl SHA256, magnet, embedded UI and chain, then exit")
	args := os.Args[1:]
	cmd := "serve"
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		cmd, args = args[0], args[1:]
	}
	_ = fsx.Parse(args)
	if cmd == "ping" { // exit 0 if an RTOR server already answers on --addr (single-instance check for launchers)
		c := &http.Client{Timeout: 1500 * time.Millisecond}
		if resp, err := c.Get("http://" + *addr + "/api/status"); err == nil {
			resp.Body.Close()
			if resp.StatusCode == 200 {
				return
			}
		}
		os.Exit(1)
	}
	if cmd == "open-url" {
		body, _ := json.Marshal(map[string]string{"url": fsx.Arg(0)})
		for i := 0; i < 40; i++ {
			if resp, err := httpc.Post("http://"+*addr+"/api/pending-open", "application/json", bytes.NewReader(body)); err == nil {
				resp.Body.Close()
				return
			}
			time.Sleep(250 * time.Millisecond)
		}
		os.Exit(1)
	}
	if host, _, err := net.SplitHostPort(*addr); err != nil || !net.ParseIP(host).IsLoopback() {
		fmt.Fprintln(os.Stderr, "refusing: --addr must be a loopback address")
		os.Exit(2)
	}
	if _, err := os.Stat(filepath.Join(*pkg, "rzl")); err != nil {
		if _, err2 := os.Stat(filepath.Join(exeDir(), "rzl")); err2 == nil {
			*pkg = exeDir()
		}
	}
	a, err := setup(*data, *pkg, *addr, *space)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if *check {
		cmd = "check"
	}
	switch cmd {
	case "check":
		os.Exit(runCheck(a))
	case "serve":
		os.Exit(serve(a))
	case "version":
		fmt.Println("rtor-ghostchain " + Version + " " + runtime.GOOS + "/" + runtime.GOARCH)
	case "magnet":
		fmt.Println(Magnet)
	case "chain":
		sub := "verify"
		if fsx.NArg() > 0 {
			sub = strings.ToLower(fsx.Arg(0))
		}
		if sub == "tail" {
			for _, e := range a.chain.Tail(10) {
				fmt.Printf("#%d %s %s %s\n", e.Seq, e.TS, e.Kind, e.EntryHash)
			}
			return
		}
		v := a.chain.Verify()
		b, _ := json.MarshalIndent(v, "", " ")
		fmt.Println(string(b))
		if !v.OK {
			os.Exit(1)
		}
	case "send-magnet":
		m := sendMagnet(a)
		d, f := a.ob.Flush(true)
		fmt.Printf("queued %s to %s; delivered %d, still queued %d\n", m.ID, m.To, d, f)
	case "flush":
		d, f := a.ob.Flush(true)
		fmt.Printf("delivered %d, still queued %d\n", d, f)
	case "outbox":
		p, s, items := a.ob.Snapshot()
		fmt.Printf("pending %d, sent %d\n", p, s)
		for _, it := range items {
			fmt.Printf("  %s to=%s type=%s tries=%d sent=%q err=%s\n", it.Msg.ID, it.Msg.To, it.Msg.Type, it.Tries, it.Sent, it.LastErr)
		}
	case "import":
		rc := 0
		for _, p := range fsx.Args() {
			b, err := os.ReadFile(p)
			if err != nil {
				fmt.Println("FAIL", p, err)
				rc = 1
				continue
			}
			res := a.importBytes(filepath.Base(p), "import:"+p, b, filepath.Dir(p))
			if !res.OK {
				fmt.Println("REFUSED", p, res.Refused)
				rc = 1
			} else if res.Item != nil {
				fmt.Printf("OK %s %s %s %v\n", res.Item.Type, res.Item.SHA256, res.Item.Name, res.Item.Verified)
			} else {
				fmt.Printf("OK SHA256SUMS: %d sums added\n", res.Sums)
			}
		}
		os.Exit(rc)
	case "library":
		for _, it := range a.lib.List() {
			fmt.Printf("%s  %-11s %10d  %s  seeded:%d\n", it.SHA256, it.Type, it.Size, it.Name, len(it.Seeded))
		}
	case "space":
		b, _ := json.MarshalIndent(a.spaceInfo(), "", " ")
		fmt.Println(string(b))
	case "parse":
		mi, err := parseMagnet(fsx.Arg(0))
		b, _ := json.MarshalIndent(mi, "", " ")
		fmt.Println(string(b))
		if err != nil {
			fmt.Println("error:", err)
			os.Exit(1)
		}
	case "seed":
		res, code := a.seed(fsx.Arg(0))
		b, _ := json.MarshalIndent(res, "", " ")
		fmt.Println(string(b))
		if code != 200 {
			os.Exit(1)
		}
		a.ob.Flush(true)
	case "leech":
		r := a.leech(fsx.Arg(0))
		b, _ := json.MarshalIndent(r, "", " ")
		fmt.Println(string(b))
		if !r.OK {
			os.Exit(1)
		}
	case "reseed":
		r := checkReseed() // reads the live RGHOSTCHAIN; holds no key, signs nothing
		b, _ := json.MarshalIndent(r, "", " ")
		fmt.Println(string(b))
		if r.State != "sealed" {
			os.Exit(3)
		}
	default:
		fmt.Fprintln(os.Stderr, "usage: rtor-ghostchain [serve|check|import FILE..|library|seed SHA|leech MAGNET|parse MAGNET|space|chain verify|chain tail|magnet|send-magnet|flush|outbox|reseed|version] [--data DIR] [--pkg DIR] [--addr 127.0.0.1:4984]")
		os.Exit(2)
	}
}
