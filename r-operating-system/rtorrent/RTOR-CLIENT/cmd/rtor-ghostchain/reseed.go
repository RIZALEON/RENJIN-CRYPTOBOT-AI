package main

// RE-SEED panel: reads the live RGHOSTCHAIN (public RTRACKR export) and clears ONLY when the sealed RGHOSTKEY block
// is really there. Every condition must hold for block 6:
//   index 6 · prev_hash = block-5 tip 4006b570…f0bb5b · payload.unsigned != true · item rghostkey or rid ЯID-2004-W7P8 ·
//   ghostkey_pin_sha256_fp = 6D:8A:…:16:C3 · a cert SHA-256 starting 2b112834 · asset_hash 70b9d3d0…6303c0 ·
//   a P-256 ECDSA sig that verifies (over the block hash, raw or hex) with a public key whose SPKI SHA-256 is the pin.
// A Face ID approval in rmail-dec-rghostkey-superkey-20261120-t224u.json only shows "pending Face ID"; it never clears.
// This client holds no key, signs nothing and mints nothing.

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const (
	rsPrev     = "4006b570883c31aff44891971dd1935a3a58a822293f919ace27e59d8cf0bb5b"
	rsPin      = "6D:8A:57:30:9D:3F:56:29:9E:4F:B5:DD:0D:35:4C:2E:3A:68:4A:0E:FC:E8:DF:C8:32:05:8E:4F:DD:DA:16:C3"
	rsCert     = "2b112834"
	rsAsset    = "70b9d3d0223619d5c06d2cdf7710b783fd456adbadc47e65179130ea956303c0"
	rsRID      = "ЯID-2004-W7P8"
	rsDecision = "rmail-dec-rghostkey-superkey-20261120-t224u.json"
)

type Reseed struct {
	State   string   `json:"state"` // waiting | pending-faceid | sealed
	Text    string   `json:"text"`
	Height  int      `json:"chain_height"`
	Tip     string   `json:"chain_tip,omitempty"`
	Source  string   `json:"source"`
	Checked string   `json:"checked"`
	Unmet   []string `json:"unmet,omitempty"`
	Err     string   `json:"err,omitempty"`
}

var (
	rsMu  sync.Mutex
	rsCur = Reseed{State: "waiting", Text: "Waiting for Rizal's RGHOSTKEY tap on the trusted device."}
)

func reseedNow() Reseed { rsMu.Lock(); defer rsMu.Unlock(); return rsCur }

func startReseed() {
	go func() {
		for {
			r := checkReseed()
			rsMu.Lock()
			rsCur = r
			rsMu.Unlock()
			if r.State == "sealed" {
				time.Sleep(10 * time.Minute)
			} else {
				time.Sleep(60 * time.Second)
			}
		}
	}()
}

func chainSources() []string {
	if s := os.Getenv("RTOR_GHOSTCHAIN_URL"); s != "" {
		return strings.Split(s, ",")
	}
	return []string{RTRACKRData + "rghostchain.json"}
}

func fetchChain(src string) ([]byte, error) {
	if strings.HasPrefix(src, "http://") || strings.HasPrefix(src, "https://") {
		resp, err := (&http.Client{Timeout: 20 * time.Second}).Get(src)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()
		if resp.StatusCode != 200 {
			return nil, fmt.Errorf("http %d", resp.StatusCode)
		}
		return io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	}
	return os.ReadFile(src)
}

func checkReseed() Reseed {
	r := Reseed{State: "waiting", Text: "Waiting for Rizal's RGHOSTKEY tap on the trusted device.", Checked: nowISO()}
	var blocks []map[string]any
	for _, src := range chainSources() {
		b, err := fetchChain(strings.TrimSpace(src))
		if err != nil {
			r.Err = src + ": " + err.Error()
			continue
		}
		var d struct {
			Blocks []map[string]any `json:"blocks"`
		}
		if json.Unmarshal(b, &d) != nil {
			r.Err = src + ": not a chain export"
			continue
		}
		blocks, r.Source, r.Err = d.Blocks, src, ""
		break
	}
	if len(blocks) > 0 {
		r.Height = len(blocks) - 1
		r.Tip, _ = blocks[len(blocks)-1]["hash"].(string)
	}
	var b6 map[string]any
	for _, b := range blocks {
		if f, ok := b["index"].(float64); ok && f == 6 {
			b6 = b
		}
	}
	if b6 == nil {
		r.Unmet = []string{"no block 6 on the chain yet"}
	} else {
		r.Unmet = sealUnmet(b6)
		if len(r.Unmet) == 0 {
			r.State, r.Text = "sealed", "RGHOSTKEY sealed · block 6"
			return r
		}
	}
	if decisionApproved() {
		r.State, r.Text = "pending-faceid", "RGHOSTKEY pending Face ID — approval recorded, waiting for the sealed block 6 on the chain."
	}
	return r
}

func sealUnmet(b map[string]any) []string {
	var un []string
	p, _ := b["payload"].(map[string]any)
	if p == nil {
		p = map[string]any{}
	}
	if s, _ := b["prev_hash"].(string); s != rsPrev {
		un = append(un, "prev_hash is not the block-5 tip")
	}
	if u, ok := p["unsigned"].(bool); ok && u {
		un = append(un, "payload.unsigned is true")
	}
	item, _ := p["item"].(string)
	rid, _ := p["rid"].(string)
	if !strings.EqualFold(item, "rghostkey") && rid != rsRID {
		un = append(un, "item is not rghostkey and rid is not "+rsRID)
	}
	pin, _ := p["ghostkey_pin_sha256_fp"].(string)
	if !strings.EqualFold(pin, rsPin) {
		un = append(un, "ghostkey_pin_sha256_fp does not match")
	}
	if !hasCertSHA(p) {
		un = append(un, "no cert SHA-256 starting "+rsCert)
	}
	if a, _ := p["asset_hash"].(string); !strings.EqualFold(a, rsAsset) {
		un = append(un, "asset_hash does not match")
	}
	if err := sigVerifies(b); err != nil {
		un = append(un, "sig does not verify: "+err.Error())
	}
	return un
}

func hasCertSHA(v any) bool {
	switch x := v.(type) {
	case map[string]any:
		for k, y := range x {
			if s, ok := y.(string); ok && strings.Contains(strings.ToLower(k), "cert") && strings.HasPrefix(strings.ToLower(strings.ReplaceAll(s, ":", "")), rsCert) {
				return true
			}
			if hasCertSHA(y) {
				return true
			}
		}
	case []any:
		for _, y := range x {
			if hasCertSHA(y) {
				return true
			}
		}
	}
	return false
}

func pinHex() string { return strings.ToLower(strings.ReplaceAll(rsPin, ":", "")) }

func decodeB(s string) []byte {
	s = strings.TrimSpace(s)
	if b, err := hex.DecodeString(s); err == nil {
		return b
	}
	for _, e := range []*base64.Encoding{base64.StdEncoding, base64.RawStdEncoding, base64.URLEncoding, base64.RawURLEncoding} {
		if b, err := e.DecodeString(s); err == nil {
			return b
		}
	}
	return nil
}

// sigVerifies: ECDSA P-256 / SHA-256 over the block hash (hex text or raw 32 bytes), DER or raw r||s, with a public key
// (sig.pubkey_spki_b64 / sig.pubkey, or the key inside sig.cert / payload cert PEM/DER) whose SPKI SHA-256 = the pin.
func sigVerifies(b map[string]any) error {
	sg, _ := b["sig"].(map[string]any)
	if sg == nil {
		return fmt.Errorf("no sig")
	}
	val, _ := sg["value"].(string)
	if val == "" || val == "unsigned" {
		return fmt.Errorf("unsigned")
	}
	sig := decodeB(val)
	if sig == nil {
		return fmt.Errorf("sig value not hex/base64")
	}
	var keys [][]byte // SPKI DER candidates
	p, _ := b["payload"].(map[string]any)
	for _, m := range []map[string]any{sg, p} {
		for k, v := range m {
			s, ok := v.(string)
			if !ok {
				continue
			}
			lk := strings.ToLower(k)
			if strings.Contains(lk, "pubkey") || strings.Contains(lk, "public_key") || strings.Contains(lk, "spki") {
				if d := decodeB(s); d != nil {
					keys = append(keys, d)
				}
			}
			if strings.Contains(lk, "cert") && !strings.Contains(lk, "sha") {
				der := []byte(nil)
				if blk, _ := pem.Decode([]byte(s)); blk != nil {
					der = blk.Bytes
				} else {
					der = decodeB(s)
				}
				if c, err := x509.ParseCertificate(der); err == nil {
					keys = append(keys, c.RawSubjectPublicKeyInfo)
				}
			}
		}
	}
	h, _ := b["hash"].(string)
	msgs := [][]byte{[]byte(h)}
	if raw, err := hex.DecodeString(h); err == nil {
		msgs = append(msgs, raw)
	}
	pinned := false
	for _, k := range keys {
		sum := sha256.Sum256(k)
		if hex.EncodeToString(sum[:]) != pinHex() {
			continue
		}
		pinned = true
		pk, err := x509.ParsePKIXPublicKey(k)
		if err != nil {
			continue
		}
		ek, ok := pk.(*ecdsa.PublicKey)
		if !ok {
			continue
		}
		for _, m := range msgs {
			d := sha256.Sum256(m)
			if ecdsa.VerifyASN1(ek, d[:], sig) {
				return nil
			}
			if len(sig) == 64 && ecdsa.Verify(ek, d[:], new(big.Int).SetBytes(sig[:32]), new(big.Int).SetBytes(sig[32:])) {
				return nil
			}
		}
	}
	if !pinned {
		return fmt.Errorf("no public key in the block matches the pinned SPKI SHA-256")
	}
	return fmt.Errorf("signature does not match the block hash")
}

// decisionApproved reads the Face ID decision file (if this device can see it). It can only ever show "pending".
func decisionApproved() bool {
	var paths []string
	if p := os.Getenv("RTOR_RGHOSTKEY_DECISION"); p != "" {
		paths = append(paths, p)
	}
	home, _ := os.UserHomeDir()
	paths = append(paths,
		filepath.Join(cfg.Data, rsDecision),
		filepath.Join(home, "R/ЯLAB/INBOX-17E-20261103/ЯLAB/RKLOWD/nodes/neo/inbox", rsDecision),
		filepath.Join(home, "R/ЯLAB/RKLOWD/nodes/neo/inbox", rsDecision))
	for _, p := range paths {
		b, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var d map[string]any
		if json.Unmarshal(b, &d) != nil {
			continue
		}
		for _, k := range []string{"decision", "action", "answer", "status", "verdict"} {
			if s, ok := d[k].(string); ok && strings.Contains(strings.ToLower(s), "approve") {
				return true
			}
		}
		if v, ok := d["approve"].(bool); ok && v {
			return true
		}
		if v, ok := d["approved"].(bool); ok && v {
			return true
		}
	}
	return false
}
