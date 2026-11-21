package main

// Always-on seeding and leeching with measured rates.
//   Seeding (upload)  = bytes this client writes into the space's drop points (RKLOWD / RENJIN folders) so other
//                       devices can leech them. Always on: a background pass keeps a verified copy in every reachable drop.
//   Leeching (download) = bytes this client reads from a drop point or an exact-source URL while resolving a magnet.
//                       Always on: queued magnets are re-checked across library → drops → xs/as/ws, and stored files are
//                       re-verified and re-leeched by their own magnet if a stored copy ever fails its SHA-256.
// Rates are measured from real byte counters over a sliding window. Nothing is estimated or invented: idle = 0 B/s.
// Per-direction throttles (RTOR_RATE_LIMIT_UP / RTOR_RATE_LIMIT_DOWN, bytes/s, 0 = unlimited) can never be set below
// MinRateBps (1 KB/s), so a throttle never starves a transfer below 1 KB/s while bytes are available.

import (
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	MinRateBps  = 1024 // floor for any configured per-direction limit
	rateWindow  = 10 * time.Second
	alwaysEvery = 30 * time.Second
	idleNote    = "idle — no peer/drop transfer"
)

type sample struct {
	t time.Time
	n int64
}

type LastXfer struct {
	Bytes int64   `json:"bytes"`
	Ms    float64 `json:"ms"`
	Bps   float64 `json:"bps"`
	At    string  `json:"at"`
	Via   string  `json:"via"`
}

type meter struct {
	samples []sample
	total   int64
	active  int
	last    *LastXfer
}

func (m *meter) prune(now time.Time) {
	i := 0
	for i < len(m.samples) && now.Sub(m.samples[i].t) > rateWindow {
		i++
	}
	m.samples = m.samples[i:]
}

type Transfers struct {
	mu   sync.Mutex
	up   map[string]*meter
	down map[string]*meter
	limU int64
	limD int64
}

var xfer = newTransfers()

func clampLimit(v int64) int64 {
	if v <= 0 {
		return 0 // unlimited
	}
	if v < MinRateBps {
		return MinRateBps
	}
	return v
}

func newTransfers() *Transfers {
	lu, _ := strconv.ParseInt(os.Getenv("RTOR_RATE_LIMIT_UP"), 10, 64)
	ld, _ := strconv.ParseInt(os.Getenv("RTOR_RATE_LIMIT_DOWN"), 10, 64)
	return &Transfers{up: map[string]*meter{}, down: map[string]*meter{}, limU: clampLimit(lu), limD: clampLimit(ld)}
}

func (t *Transfers) get(dir, key string) *meter {
	mm := t.up
	if dir == "down" {
		mm = t.down
	}
	m := mm[key]
	if m == nil {
		m = &meter{}
		mm[key] = m
	}
	return m
}

func (t *Transfers) add(dir, key string, n int64) {
	t.mu.Lock()
	m := t.get(dir, key)
	now := time.Now()
	m.samples = append(m.samples, sample{now, n})
	m.total += n
	m.prune(now)
	t.mu.Unlock()
}

func (t *Transfers) begin(dir, key string) {
	t.mu.Lock()
	t.get(dir, key).active++
	t.mu.Unlock()
}

func (t *Transfers) end(dir, key string, bytes int64, start time.Time, via string) {
	t.mu.Lock()
	m := t.get(dir, key)
	m.active--
	el := time.Since(start)
	ms := float64(el.Microseconds()) / 1000
	if bytes > 0 {
		d := el.Seconds()
		if d < 1e-6 {
			d = 1e-6
		}
		m.last = &LastXfer{Bytes: bytes, Ms: ms, Bps: float64(bytes) / d, At: nowISO(), Via: via}
	}
	t.mu.Unlock()
}

func (t *Transfers) limit(dir string) int64 {
	if dir == "down" {
		return t.limD
	}
	return t.limU
}

// Rate is the measured sliding-window rate: bytes moved in the last rateWindow / rateWindow seconds.
type Rate struct {
	On         bool      `json:"on"`
	Direction  string    `json:"direction"`
	RateBps    float64   `json:"rate_bps"`
	WindowSec  int       `json:"window_s"`
	TotalBytes int64     `json:"total_bytes"`
	Active     bool      `json:"active"`
	Last       *LastXfer `json:"last,omitempty"`
	LimitBps   int64     `json:"limit_bps"`
	FloorBps   int       `json:"floor_bps"`
	Note       string    `json:"note,omitempty"`
	Keepalive  *KA       `json:"keepalive,omitempty"`
}

func (t *Transfers) rate(dir string, keys ...string) Rate {
	t.mu.Lock()
	defer t.mu.Unlock()
	r := Rate{On: true, Direction: dir, WindowSec: int(rateWindow / time.Second), LimitBps: t.limit(dir), FloorBps: MinRateBps}
	now := time.Now()
	var inWin int64
	for _, k := range keys {
		if k == "" {
			continue
		}
		mm := t.up
		if dir == "down" {
			mm = t.down
		}
		m := mm[k]
		if m == nil {
			continue
		}
		m.prune(now)
		for _, s := range m.samples {
			inWin += s.n
		}
		r.TotalBytes += m.total
		r.Active = r.Active || m.active > 0
		if m.last != nil && (r.Last == nil || m.last.At > r.Last.At) {
			r.Last = m.last
		}
	}
	r.RateBps = float64(inWin) / rateWindow.Seconds()
	if inWin == 0 && !r.Active {
		r.Note = idleNote
	}
	return r
}

// meteredCopy copies src → dst, counting bytes on (dir,key). A configured limit is honored but never below MinRateBps.
func meteredCopy(dst io.Writer, src io.Reader, dir, key string) (int64, error) {
	lim := xfer.limit(dir)
	chunk := 32 << 10
	if lim > 0 && int64(chunk) > lim/4 {
		chunk = int(lim / 4)
		if chunk < 256 {
			chunk = 256
		}
	}
	buf := make([]byte, chunk)
	start := time.Now()
	var n int64
	for {
		k, rerr := src.Read(buf)
		if k > 0 {
			if _, werr := dst.Write(buf[:k]); werr != nil {
				return n, werr
			}
			n += int64(k)
			xfer.add(dir, key, int64(k))
			if lim > 0 {
				want := time.Duration(float64(n) / float64(lim) * float64(time.Second))
				if el := time.Since(start); el < want {
					time.Sleep(want - el)
				}
			}
		}
		if rerr == io.EOF {
			return n, nil
		}
		if rerr != nil {
			return n, rerr
		}
	}
}

type limitedBuf struct {
	b   []byte
	max int
}

func (w *limitedBuf) Write(p []byte) (int, error) {
	if len(w.b)+len(p) > w.max {
		return 0, io.ErrShortBuffer
	}
	w.b = append(w.b, p...)
	return len(p), nil
}

// meteredRead reads up to max bytes from r on the download meter for key.
func meteredRead(r io.Reader, key, via string, max int) ([]byte, error) {
	return meteredReadSince(r, key, via, max, time.Now())
}

// meteredReadSince times the transfer from start (e.g. before the HTTP request, so latency counts against the rate).
func meteredReadSince(r io.Reader, key, via string, max int, start time.Time) ([]byte, error) {
	xfer.begin("down", key)
	w := &limitedBuf{max: max}
	n, err := meteredCopy(w, r, "down", key)
	xfer.end("down", key, n, start, via)
	return w.b, err
}

// ------------------------------------------------------------------ always-on loop

type queued struct {
	Magnet string `json:"magnet"`
	Added  string `json:"added"`
	Tries  int    `json:"tries"`
	Last   string `json:"last_try,omitempty"`
	Note   string `json:"note,omitempty"`
}

// ensureSeeded keeps a verified copy of every library file in every reachable drop point (upload bytes are metered).
var seedMu sync.Mutex

func (l *Library) ensureSeeded(sp *Space) {
	seedMu.Lock()
	defer seedMu.Unlock()
	drops := sp.Drops()
	for _, it := range l.List() {
		for _, d := range drops {
			if !d.Reachable {
				continue
			}
			dst := filepath.Join(d.Path, it.SHA256[:12]+"-"+it.Name)
			if fi, err := os.Stat(dst); err == nil && fi.Size() == it.Size {
				continue
			}
			if got, _, err := sha256File(l.path(it)); err != nil || got != it.SHA256 {
				break // stored copy bad: the leech pass re-fetches it
			}
			if err := copyFile(l.path(it), dst, it.SHA256); err != nil {
				continue
			}
			l.mu.Lock()
			if x, ok := l.items[it.SHA256]; ok {
				seen := false
				for _, p := range x.Seeded {
					seen = seen || p == dst
				}
				if !seen {
					x.Seeded = append(x.Seeded, dst)
				}
				x.SeededAt = nowISO()
				l.saveLocked()
			}
			l.mu.Unlock()
		}
	}
}

func (l *Library) enqueue(magnet, note string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	for _, q := range l.queue {
		if q.Magnet == magnet {
			q.Note = note
			return
		}
	}
	l.queue = append(l.queue, &queued{Magnet: magnet, Added: nowISO(), Note: note})
	l.saveLocked()
}

func (l *Library) Queue() []queued {
	l.mu.Lock()
	defer l.mu.Unlock()
	out := make([]queued, 0, len(l.queue))
	for _, q := range l.queue {
		out = append(out, *q)
	}
	return out
}

// leechPass re-checks queued magnets and re-verifies stored files (re-leeching by magnet + recorded sources if bad).
func (l *Library) leechPass(sp *Space, onOK func(LeechResult)) {
	for _, q := range l.Queue() {
		r := l.Leech(q.Magnet, sp)
		l.mu.Lock()
		for i, x := range l.queue {
			if x.Magnet != q.Magnet {
				continue
			}
			if r.OK {
				l.queue = append(l.queue[:i], l.queue[i+1:]...)
			} else {
				x.Tries++
				x.Last = nowISO()
				x.Note = r.Note
			}
			break
		}
		l.saveLocked()
		l.mu.Unlock()
		if r.OK && onOK != nil {
			onOK(r)
		}
	}
	for _, it := range l.List() {
		if it.Size > 64<<20 && time.Since(l.lastVerify(it.SHA256)) < 10*time.Minute {
			continue
		}
		got, _, err := sha256File(l.path(it))
		l.markVerified(it.SHA256)
		if err == nil && got == it.SHA256 {
			continue
		}
		m := it.Magnet
		for _, s := range it.Sources {
			m += "&ws=" + urlQueryEscape(s)
		}
		l.mu.Lock()
		delete(l.items, it.SHA256) // stored copy failed SHA-256: drop the record so Leech re-fetches and re-imports it
		l.mu.Unlock()
		if r := l.Leech(m, sp); !r.OK {
			l.mu.Lock()
			l.items[it.SHA256] = it
			l.mu.Unlock()
			l.enqueue(m, "stored copy failed SHA-256; waiting for a verified source")
		}
	}
}

func (l *Library) lastVerify(sha string) time.Time {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.verifiedAt[sha]
}

func (l *Library) markVerified(sha string) {
	l.mu.Lock()
	l.verifiedAt[sha] = time.Now()
	l.mu.Unlock()
}

func urlQueryEscape(s string) string {
	r := strings.NewReplacer("%", "%25", "&", "%26", "=", "%3D", "?", "%3F", "#", "%23", " ", "%20", ":", "%3A", "/", "%2F")
	return r.Replace(s)
}

func (a *App) alwaysOn() {
	time.Sleep(3 * time.Second)
	for {
		a.lib.ensureSeeded(a.space)
		a.lib.leechPass(a.space, func(r LeechResult) {
			_, _ = a.chain.Append("rtor-leech", map[string]any{"sha256": r.Item.SHA256, "name": r.Item.Name, "from": r.From, "by": "always-on queue"})
		})
		time.Sleep(alwaysEvery)
	}
}

// itemView is a library row with its always-on seeding / leeching state and measured rates.
type itemView struct {
	*Item
	Seeding  Rate `json:"seeding"`
	Leeching Rate `json:"leeching"`
}

func (l *Library) Views() []itemView {
	out := []itemView{}
	for _, it := range l.List() {
		keys := []string{it.SHA256, it.BTMH}
		v := itemView{Item: it, Seeding: xfer.rate("up", keys...), Leeching: xfer.rate("down", keys...)}
		if pnet != nil {
			v.Seeding.Keepalive, v.Leeching.Keepalive = pnet.KAState("up", it.SHA256), pnet.KAState("down", it.SHA256)
			if v.Seeding.Keepalive != nil && v.Seeding.RateBps == 0 {
				v.Seeding.Note = v.Seeding.Keepalive.Note
			}
			if v.Leeching.Keepalive != nil && v.Leeching.RateBps == 0 {
				v.Leeching.Note = v.Leeching.Keepalive.Note
			}
		}
		out = append(out, v)
	}
	return out
}
