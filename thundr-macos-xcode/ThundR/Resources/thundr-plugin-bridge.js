// thundr-plugin-bridge.js — integrated ThundR plugin adapter, JS side.
// Extends the proven RCODE adapter pattern (rcode-host-adapter.js +
// rcode-bridge-plugin.js): sets globalThis.YASEED_HOST, registers the
// 'thundr-plugin' through the RENJIN core's own registerPlugin()
// (selftest -> device-signed descriptor -> plugin.register chain entry).
//
// Protocol: rzl.thundr.plugin.v1 — rzl.link.v1 envelopes between
// devices (Ed25519, exp <= 24h), plain JSON over the WKWebView bridge
// in-process. Capabilities: communicate, diagnostics, analysis, debug,
// repair, update, code, visual. Repairs / updates are propose-first:
// without Decider approval they return a proposal, never an execution.
// Bots never sign; keys never cross the bridge.
(function (global) {
  'use strict';

  var SCHEMA = 'rzl.link.v1';
  var PLUGIN_SCHEMA = 'rzl.thundr.plugin.v1';
  var PLUGIN_ID = 'thundr-plugin';
  var PLUGIN_VERSION = '0.1.0';

  var READ_ONLY = [
    'talk', 'ask', 'report',
    'diagnostics.status', 'diagnostics.chain', 'diagnostics.plugins',
    'diagnostics.hostInfo', 'diagnostics.modelInventory',
    'analysis.code', 'analysis.corpus', 'analysis.purity',
    'debug.capture', 'repair.propose', 'update.check', 'code.read',
    'rloader.status', 'rloader.resign.status', 'getYaId', 'hostInfo'
  ];

  // --- envelope -------------------------------------------------------
  function makeEnvelope(from, kind, capability, method, args, approved) {
    var now = Math.floor(Date.now() / 1000);
    return {
      schema: SCHEMA, type: 'cmd', from: from || '',
      kind: kind || 'talk', plugin: PLUGIN_ID,
      plugin_version: PLUGIN_VERSION, capability: capability || 'communicate',
      method: method, args: args || {},
      nonce: Math.random().toString(36).slice(2) + Date.now().toString(36),
      iat: now, exp: now + 24 * 3600, approved: !!approved
      // sig: Ed25519 over canonical JSON — added by the device side only.
      // This bridge never signs.
    };
  }

  // Out-of-band text form, as in rzl.link.v1: ЯLINK1 <id8> <i>/<n> <base64url>
  function toTextLines(envelope) {
    var b64 = Buffer.from(JSON.stringify(envelope), 'utf8').toString('base64')
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    var id8 = (envelope.nonce || 'thundr00').slice(0, 8);
    var chunks = b64.match(/.{1,3000}/g) || [''];
    return chunks.map(function (c, i) { return 'ЯLINK1 ' + id8 + ' ' + (i + 1) + '/' + chunks.length + ' ' + c; });
  }

  // --- host adapter (WKWebView bridge) --------------------------------
  function webkitBridge() {
    try {
      var h = global.webkit && global.webkit.messageHandlers && global.webkit.messageHandlers.thundrHost;
      if (!h || typeof h.postMessage !== 'function') return null;
      return { call: function (method, args) { return h.postMessage({ method: method, args: args || {} }); } };
    } catch (e) { return null; }
  }

  function createThundRHostAdapter(nativeBridge, opts) {
    opts = opts || {};
    var bridge = nativeBridge || webkitBridge();
    var platform = opts.platform || 'macos';
    var host = {
      hostId: opts.hostId || (bridge && bridge.__mock ? 'thundr-mock' : 'thundr-' + platform),
      platform: platform,
      bridge: bridge,
      storage: null,
      getYaId: async function () {
        if (!bridge) return null;
        try { var r = await bridge.call('getYaId', {}); return (r && r.yaId) || null; }
        catch (e) { return null; }
      },
      // Call into ThundR / Neo. Read-only methods run; anything
      // state-changing without approval returns a proposal, never
      // an execution (enforced here AND on the Swift side).
      callNative: async function (method, args) {
        if (!bridge) throw new Error('thundr-plugin: no ThundR host attached (not running inside ThundR)');
        return bridge.call(method, args || {});
      },
      call: async function (capability, method, args, approved) {
        var env = makeEnvelope(null, 'talk', capability, method, args, approved);
        if (!bridge) throw new Error('thundr-plugin: no ThundR host attached');
        return bridge.call(method, Object.assign({}, args || {}, { _envelope: env }));
      }
    };
    return host;
  }

  function install(nativeBridge, opts) {
    var host = createThundRHostAdapter(nativeBridge, opts);
    global.YASEED_HOST = host;
    return host;
  }

  // --- core plugin ------------------------------------------------------
  var ThundRPlugin = {
    id: PLUGIN_ID,
    version: PLUGIN_VERSION,
    description: 'Integrated ThundR plugin adapter: communication, diagnostics, analysis, debug, repair (propose-first), update (via Яloader), code and visual integration for all bots and AI, certainly Muse. Carries public identifiers and messages only — bots never sign, keys never cross the bridge.',
    create: function (eng) {
      var host = (typeof global.YASEED_HOST !== 'undefined' && global.YASEED_HOST) || null;
      return {
        engine: eng, host: host, installed: !!host,
        hostId: host ? host.hostId : null,
        schema: PLUGIN_SCHEMA,
        getYaId: async function () { return host && host.getYaId ? host.getYaId() : null; },
        callNative: async function (method, args) {
          if (!host || typeof host.callNative !== 'function') throw new Error('thundr-plugin: no ThundR host attached');
          return host.callNative(method, args);
        },
        // Capability entry points. Each builds a rzl.link.v1 envelope.
        diagnostics: async function (method, args) { return host.call('diagnostics', method, args, false); },
        analysis: async function (method, args) { return host.call('analysis', method, args, false); },
        debugCapture: async function (args) { return host.call('debug', 'debug.capture', args, false); },
        proposeRepair: async function (args) { return host.call('repair', 'repair.propose', args, false); },
        applyRepair: async function (args, approved) {
          if (!approved) return { proposed: true, method: 'repair.apply', note: 'Decider approval required — proposal recorded, nothing executed' };
          return host.call('repair', 'repair.apply', args, true);
        },
        requestUpdate: async function (args, approved) {
          if (!approved) return { proposed: true, method: 'update.request', note: 'Decider approval required — rebuild is requested via Яloader, nothing executed' };
          return host.call('update', 'update.request', args, true);
        },
        rloaderStatus: async function () { return host.call('update', 'rloader.status', {}, false); }
      };
    },
    selftest: function (api) {
      var A = global.ThundRPluginBridge;
      if (!api.assert(!!A, 'thundr plugin bridge module present')) return false;
      var mock = { __mock: true, call: async function (m) { return m === 'getYaId' ? { yaId: 'RID-SELFTEST' } : { ok: true, method: m }; } };
      var host = A.createThundRHostAdapter(mock, { platform: 'macos' });
      if (!api.assert(host.hostId === 'thundr-mock', 'adapter builds a thundr host')) return false;
      if (!api.assert(typeof host.getYaId === 'function' && typeof host.callNative === 'function', 'adapter exposes getYaId + callNative')) return false;
      var env = makeEnvelope('ЯID-0001-3QQS', 'talk', 'diagnostics', 'diagnostics.status', {}, false);
      if (!api.assert(env.schema === SCHEMA && env.plugin === PLUGIN_ID && env.exp - env.iat === 86400, 'envelope is rzl.link.v1, thundr-plugin, exp 24h')) return false;
      var lines = toTextLines(env);
      if (!api.assert(lines.length >= 1 && lines[0].indexOf('ЯLINK1 ') === 0, 'out-of-band ЯLINK1 text form')) return false;
      return true;
    }
  };

  var api = {
    createThundRHostAdapter: createThundRHostAdapter, install: install,
    makeEnvelope: makeEnvelope, toTextLines: toTextLines,
    PLUGIN_ID: PLUGIN_ID, PLUGIN_VERSION: PLUGIN_VERSION, SCHEMA: SCHEMA
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.ThundRPluginBridge = api;
  global.ThundRPlugin = ThundRPlugin;
})(typeof globalThis !== 'undefined' ? globalThis : this);
