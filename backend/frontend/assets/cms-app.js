const { useState, useEffect, useMemo, useRef, useCallback } = React;
const tenantSlug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get("tenant") || (location.pathname.match(/^\/([^/]+)(?:\/cms)?\/?$/) || [])[1] || "";
const nowAU = () => (/* @__PURE__ */ new Date()).toLocaleString("en-AU", {
  timeZone: "Australia/Melbourne",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});
const todayISO = () => (/* @__PURE__ */ new Date()).toLocaleDateString("en-CA");
const fmtDate = (s) => {
  if (!s) return "—";
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(s).split(" ")[0];
};
const daysSince = (iso) => {
  if (!iso) return 9999;
  const d = new Date(iso);
  return isNaN(d) ? 9999 : Math.floor((Date.now() - d) / 864e5);
};
const TENANT_SLUG = window.STUDIOSAAS_TENANT_SLUG || "";
const v1Api = async (path, options = {}) => {
  const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(d.message || d.error || `HTTP ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return d;
};
const parseMonthKey = (ds) => {
  if (!ds) return null;
  const s = String(ds);
  const a = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (a) return `${a[3]}-${a[2].padStart(2, "0")}`;
  const b = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);
  if (b) return `${b[1]}-${b[2].padStart(2, "0")}`;
  const c = s.match(/^(\d{4})-(\d{2})/);
  if (c) return `${c[1]}-${c[2]}`;
  return null;
};
const fmtMK = (k) => {
  if (!k) return "";
  const [y, m] = k.split("-");
  return `${m}/${y}`;
};
const PIN_KEY = "lp_pin_v1";
const SESSION_KEY = "lp_sess_v1";
const getPin = () => {
  try {
    const v = localStorage.getItem(PIN_KEY);
    return v ? atob(v).replace("lp:", "") : null;
  } catch {
    return null;
  }
};
const savePin = (p) => localStorage.setItem(PIN_KEY, btoa("lp:" + p));
const sessOK = () => sessionStorage.getItem(SESSION_KEY) === "1";
const markSess = () => sessionStorage.setItem(SESSION_KEY, "1");
const clearSess = () => sessionStorage.removeItem(SESSION_KEY);
function PINScreen({ onUnlock }) {
  const stored = getPin();
  const isSetup = !stored;
  const [dig, setDig] = useState(["", "", "", ""]);
  const [conf, setConf] = useState(["", "", "", ""]);
  const [step, setStep] = useState(isSetup ? "set" : "enter");
  const [err, setErr] = useState("");
  const refs = useRef([]);
  const focus = (i) => refs.current[i]?.focus();
  const push = (val, arr, setArr, base) => {
    const i = arr.findIndex((d) => d === "");
    if (i === -1) return;
    const na = [...arr];
    na[i] = val;
    setArr(na);
    if (i < 3) focus(base + i + 1);
    if (i === 3) setTimeout(() => submit([...na]), 60);
  };
  const pop = (arr, setArr, base) => {
    const rev = [...arr].reverse();
    const i = rev.findIndex((d) => d !== "");
    if (i === -1) return;
    const na = [...arr];
    na[3 - i] = "";
    setArr(na);
    focus(base + 3 - i);
  };
  const submit = (filled) => {
    const pin = filled.join("");
    if (pin.length < 4) return;
    setErr("");
    if (step === "enter") {
      if (pin === stored) onUnlock();
      else {
        setErr("PIN 不正确，请重试");
        setDig(["", "", "", ""]);
        setTimeout(() => focus(0), 60);
      }
    } else if (step === "set") {
      setStep("confirm");
      setConf(["", "", "", ""]);
      setTimeout(() => focus(4), 60);
    } else {
      if (pin === dig.join("")) {
        savePin(dig.join(""));
        onUnlock();
      } else {
        setErr("两次输入不一致，请重新设置");
        setConf(["", "", "", ""]);
        setTimeout(() => focus(4), 60);
      }
    }
  };
  const Dots = ({ arr }) => /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 justify-center my-5" }, arr.map((d, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: `pin-dot ${d ? "on" : ""}` })));
  const Inputs = ({ arr, setArr, base }) => /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 justify-center" }, arr.map((_, i) => /* @__PURE__ */ React.createElement(
    "input",
    {
      key: i,
      ref: (el) => refs.current[base + i] = el,
      type: "password",
      inputMode: "numeric",
      maxLength: 1,
      value: arr[i],
      className: "pin-input",
      onChange: (e) => {
        const v = e.target.value.replace(/\D/, "");
        if (v) push(v, arr, setArr, base);
      },
      onKeyDown: (e) => {
        if (e.key === "Backspace") pop(arr, setArr, base);
      }
    }
  )));
  return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-950 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-3xl p-8 w-full max-w-xs shadow-2xl text-center anim" }, /* @__PURE__ */ React.createElement("img", { src: "/logo.png", alt: "Studio", className: "w-36 mx-auto mb-3" }), /* @__PURE__ */ React.createElement("p", { className: "tenant-slogan text-sm text-gray-500 italic mb-4" }, "Learn, grow, and feel confident."), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mb-4" }, step === "set" ? "首次使用，请设置 4 位 PIN 码" : step === "confirm" ? "再次输入确认 PIN" : "输入 PIN 码解锁"), step !== "confirm" ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Dots, { arr: dig }), /* @__PURE__ */ React.createElement(Inputs, { arr: dig, setArr: setDig, base: 0 })) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Dots, { arr: conf }), /* @__PURE__ */ React.createElement(Inputs, { arr: conf, setArr: setConf, base: 4 })), err && /* @__PURE__ */ React.createElement("p", { className: "text-red-500 text-xs mt-4 font-medium" }, err), step === "enter" && /* @__PURE__ */ React.createElement("details", { className: "mt-5 text-left" }, /* @__PURE__ */ React.createElement("summary", { className: "text-xs text-gray-400 cursor-pointer select-none text-center" }, "忘记 PIN？"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-2 bg-gray-50 rounded-xl p-3 leading-relaxed" }, "在浏览器开发者工具的 Console 中运行：", /* @__PURE__ */ React.createElement("br", null), /* @__PURE__ */ React.createElement("code", { className: "text-indigo-600 font-mono break-all" }, "localStorage.removeItem('lp_pin_v1')"), /* @__PURE__ */ React.createElement("br", null), "刷新页面后即可重新设置 PIN。"))));
}
function BarChart({ items, color = "#6366f1", h = 140, prefix = "" }) {
  if (!items?.length) return /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-6" }, "暂无数据");
  const max = Math.max(...items.map((d) => d.v), 0.01);
  const W = 54, PAD = 6;
  return /* @__PURE__ */ React.createElement("svg", { viewBox: `0 0 ${items.length * W} ${h + 24}`, className: "w-full overflow-visible" }, items.map((d, i) => {
    const bh = Math.max(2, d.v / max * (h - 12));
    return /* @__PURE__ */ React.createElement("g", { key: i, transform: `translate(${i * W + PAD},0)` }, /* @__PURE__ */ React.createElement("rect", { x: 4, y: h - bh, width: W - PAD * 2, height: bh, fill: color, rx: 3, opacity: 0.82 }), d.v > 0 && /* @__PURE__ */ React.createElement("text", { x: (W - PAD * 2) / 2 + 4, y: h - bh - 4, textAnchor: "middle", fontSize: 8, fill: "#374151", fontWeight: "bold" }, prefix, d.v), /* @__PURE__ */ React.createElement("text", { x: (W - PAD * 2) / 2 + 4, y: h + 16, textAnchor: "middle", fontSize: 7.5, fill: "#9ca3af" }, d.l));
  }));
}
function BalBadge({ n }) {
  const v = parseInt(n, 10) || 0;
  if (v === 0) return /* @__PURE__ */ React.createElement("span", { className: "px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-700 whitespace-nowrap" }, "0 ⚠️");
  if (v <= 2) return /* @__PURE__ */ React.createElement("span", { className: "px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-100 text-orange-700 whitespace-nowrap" }, v, " ⚡");
  if (v <= 4) return /* @__PURE__ */ React.createElement("span", { className: "px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 whitespace-nowrap" }, v);
  return /* @__PURE__ */ React.createElement("span", { className: "px-2.5 py-1 rounded-lg text-xs font-bold bg-green-100 text-green-700 whitespace-nowrap" }, v);
}
function Toast({ msg, type, action, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, action ? 6e3 : 2700);
    return () => clearTimeout(t);
  }, []);
  const bg = type === "error" ? "bg-red-600" : type === "warn" ? "bg-amber-500" : "bg-gray-900";
  return /* @__PURE__ */ React.createElement("div", { className: `toast toast-bottom fixed left-1/2 -translate-x-1/2 z-[999] ${bg} text-white px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold max-w-xs text-center` }, /* @__PURE__ */ React.createElement("div", null, type === "error" ? "❌" : type === "warn" ? "⚠️" : "✅", " ", msg), action && /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => {
        action.onClick();
        onDone();
      },
      className: "mt-2 w-full bg-white/20 active:bg-white/30 rounded-lg py-1.5 text-xs font-bold"
    },
    action.label
  ));
}
function ConfirmDialog({ dialog, onClose }) {
  if (!dialog) return null;
  return /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 bg-black/50 z-[95] flex items-center justify-center p-4", onClick: onClose }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl anim", onClick: (e) => e.stopPropagation() }, dialog.title && /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 mb-2" }, dialog.title), /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 text-sm leading-relaxed mb-6" }, dialog.message), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: onClose,
      className: "flex-1 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm"
    },
    "取消"
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => {
        dialog.onConfirm();
        onClose();
      },
      className: `flex-1 py-3 font-bold rounded-xl text-sm text-white ${dialog.danger ? "bg-red-600 active:bg-red-700" : "bg-indigo-600 active:bg-indigo-700"}`
    },
    dialog.confirmText || "确认"
  ))));
}
function StudentPicker({ students, value, onChange, placeholder = "-- 选择学员 --", showBal = true }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const sel = students.find((s) => s.id === value);
  useEffect(() => {
    if (!value) setQ("");
  }, [value]);
  const filtered = useMemo(
    () => q ? students.filter((s) => s.name.toLowerCase().includes(q.toLowerCase())) : students,
    [students, q]
  );
  useEffect(() => {
    const h = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    document.addEventListener("touchstart", h, { passive: true });
    return () => {
      document.removeEventListener("mousedown", h);
      document.removeEventListener("touchstart", h);
    };
  }, []);
  return /* @__PURE__ */ React.createElement("div", { ref, className: "relative" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center border border-gray-300 rounded-xl bg-white focus-within:ring-2 focus-within:ring-indigo-500 overflow-hidden" }, /* @__PURE__ */ React.createElement("span", { className: "pl-3 text-gray-400 flex-shrink-0" }, "🔍"), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "text",
      placeholder: sel ? sel.name : placeholder,
      value: open ? q : sel ? sel.name : "",
      onFocus: () => {
        setQ("");
        setOpen(true);
      },
      onChange: (e) => {
        setQ(e.target.value);
        setOpen(true);
      },
      className: "flex-1 px-2 py-3 outline-none bg-transparent"
    }
  ), sel && /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "button",
      onClick: () => {
        onChange(null);
        setQ("");
      },
      className: "pr-3 text-gray-400 active:text-gray-700 text-xl leading-none py-3 px-2"
    },
    "×"
  )), open && /* @__PURE__ */ React.createElement("div", { className: "absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-2xl max-h-52 overflow-y-auto sl" }, !filtered.length ? /* @__PURE__ */ React.createElement("div", { className: "p-4 text-center text-gray-400 text-sm" }, "无匹配") : filtered.map((s) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: s.id,
      type: "button",
      onClick: () => {
        onChange(s.id);
        setQ(s.name);
        setOpen(false);
      },
      className: `w-full text-left px-4 py-3 active:bg-indigo-50 text-sm flex justify-between items-center min-h-[44px] ${s.id === value ? "bg-indigo-50" : "hover:bg-indigo-50"}`
    },
    /* @__PURE__ */ React.createElement("span", { className: "font-medium truncate pr-2" }, s.name),
    showBal && /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance })
  ))));
}
function mediaSrc(value, fallbackBase = "photos") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.startsWith("media:")) {
    const id = raw.slice(6);
    const slug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get("tenant") || "";
    return `/s/${encodeURIComponent(slug)}/v1/media/${encodeURIComponent(id)}`;
  }
  return `/${fallbackBase}/${encodeURIComponent(raw)}`;
}
function portfolioImgSrc(studentId, item) {
  if (item?.mediaUrl) return item.mediaUrl;
  const filename = item?.filename || "";
  if (String(filename).startsWith("media:")) return mediaSrc(filename, "portfolio");
  return `/portfolio/img/${encodeURIComponent(studentId)}/${encodeURIComponent(filename)}`;
}
function portfolioThumbSrc(studentId, item) {
  const src = portfolioImgSrc(studentId, item);
  if (src.includes("/v1/media/")) return src + (src.includes("?") ? "&" : "?") + "thumb=1";
  return src;
}
function PhotoAvatar({ photo, name, size = "sm" }) {
  const cls = size === "sm" ? "w-9 h-9 text-xs" : size === "md" ? "w-14 h-14 text-base" : "w-20 h-20 text-2xl";
  const initials = (name || "?").trim().split(/\s+/).map((w) => w[0] || "").slice(0, 2).join("").toUpperCase() || "?";
  if (photo) return /* @__PURE__ */ React.createElement("img", { src: mediaSrc(photo), className: `${cls} rounded-full object-cover flex-shrink-0 border-2 border-white shadow-sm`, alt: name });
  return /* @__PURE__ */ React.createElement("div", { className: `${cls} rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold flex-shrink-0 border-2 border-white shadow-sm` }, initials);
}
function PhotoUploader({ value, onChange }) {
  const [uploading, setUploading] = useState(false);
  const handleFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert("照片不能超过 5MB");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/media/upload`, { method: "POST", credentials: "include", body: fd });
      const d = await r.json();
      if (d.filename) onChange(d.filename);
    } catch {
      alert("上传失败，请重试");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };
  const btnBase = uploading ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed" : "";
  return /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-4" }, value ? /* @__PURE__ */ React.createElement("img", { src: mediaSrc(value), className: "w-14 h-14 rounded-full object-cover border-2 border-indigo-100 flex-shrink-0" }) : /* @__PURE__ */ React.createElement("div", { className: "w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center text-2xl border-2 border-dashed border-gray-300 flex-shrink-0" }, "📷"), /* @__PURE__ */ React.createElement("div", { className: "space-y-1.5" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("label", { className: `cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[40px] ${btnBase || "bg-indigo-50 text-indigo-700 border-indigo-200 active:bg-indigo-100"}` }, "📁 ", uploading ? "上传中..." : value ? "更换" : "选择", /* @__PURE__ */ React.createElement("input", { type: "file", accept: "image/*", onChange: handleFile, disabled: uploading, className: "hidden" })), /* @__PURE__ */ React.createElement("label", { className: `cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[40px] ${btnBase || "bg-purple-50 text-purple-700 border-purple-200 active:bg-purple-100"}` }, "📷 拍照", /* @__PURE__ */ React.createElement("input", { type: "file", accept: "image/*", capture: "environment", onChange: handleFile, disabled: uploading, className: "hidden" }))), value && /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => onChange(""), className: "text-xs text-red-400 active:text-red-600" }, "移除照片")));
}
function MaintSection({ onRestored, renewTh, saveRenewTh }) {
  const [hc, setHc] = useState(null);
  const [hcBusy, setHcBusy] = useState(false);
  const [cfg, setCfg] = useState(null);
  const [pw, setPw] = useState("");
  const [cfgMsg, setCfgMsg] = useState("");
  const [bks, setBks] = useState(null);
  const [bkSel, setBkSel] = useState(null);
  const [busy, setBusy] = useState(false);
  const post = (url, body) => fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const [stale, setStale] = useState(false);
  useEffect(() => {
    fetch("/api/config", { credentials: "include" }).then((r) => {
      if (r.status === 404) {
        setStale(true);
        return null;
      }
      return r.json();
    }).then((d) => {
      if (d) setCfg(d);
    }).catch(() => {
    });
  }, []);
  const runHC = async () => {
    setHcBusy(true);
    try {
      const r = await fetch("/api/healthcheck", { credentials: "include" });
      if (r.status === 404) {
        setStale(true);
        setHc(null);
        return;
      }
      setHc(await r.json());
    } catch {
      setHc({ error: "连接失败" });
    } finally {
      setHcBusy(false);
    }
  };
  const saveCfg = async () => {
    if (!cfg) return;
    setBusy(true);
    setCfgMsg("");
    try {
      const body = {
        email_to: cfg.email_to,
        smtp_user: cfg.smtp_user,
        smtp_host: cfg.smtp_host,
        smtp_port: cfg.smtp_port,
        weekly_enabled: cfg.weekly_enabled,
        renew_threshold: renewTh
      };
      if (pw) body.smtp_password = pw;
      const r = await post("/api/config", body);
      if (r.status === 404) {
        setStale(true);
        setCfgMsg("");
        return;
      }
      setCfgMsg(r.ok ? "✅ 已保存" : `❌ 保存失败 (HTTP ${r.status})`);
      if (r.ok && pw) {
        setPw("");
        setCfg((c) => ({ ...c, hasPassword: true }));
      }
    } catch {
      setCfgMsg("❌ 连接失败");
    } finally {
      setBusy(false);
    }
  };
  const testEmail = async () => {
    setBusy(true);
    setCfgMsg("发送中…（请先点过「保存配置」）");
    try {
      const r = await post("/api/email-test", {});
      const d = await r.json();
      setCfgMsg(d.ok ? "✅ 测试邮件已发出，请查收（含每周汇总预览）" : `❌ ${d.error || "发送失败"}`);
    } catch {
      setCfgMsg("❌ 连接失败");
    } finally {
      setBusy(false);
    }
  };
  const loadBks = async () => {
    try {
      const r = await fetch("/api/backups", { credentials: "include" });
      const d = await r.json();
      if (Array.isArray(d) && d.length && typeof d[0] === "string") {
        setStale(true);
        setBks([]);
        return;
      }
      setBks(Array.isArray(d) ? d : []);
    } catch {
      setBks([]);
    }
  };
  const clearPwaCache = async () => {
    try {
      if ("serviceWorker" in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        regs.forEach((r) => r.active && r.active.postMessage({ type: "CLEAR_LPCMS_CACHE" }));
      }
      if ("caches" in window) {
        const keys = await caches.keys();
        await Promise.all(keys.filter((k) => k.startsWith("lpcms-")).map((k) => caches.delete(k)));
      }
      window.alert("✅ PWA 缓存已清理，页面将刷新。若主屏幕 App 图标仍未更新，请删除后重新添加。");
      window.location.reload();
    } catch (e) {
      window.alert("❌ 缓存清理失败，请关闭 App 后重新打开。");
    }
  };
  const pickBk = async (name) => {
    try {
      const r = await fetch(`/api/backups/${name}/summary`, { credentials: "include" });
      setBkSel({ name, ...await r.json() });
    } catch {
    }
  };
  const doRestore = async () => {
    if (!bkSel || !bkSel.valid) return;
    const d1 = `确认恢复备份 ${bkSel.name}？

该备份: ${bkSel.students} 名学员 / ${bkSel.logs} 条日志
与当前相比: 学员 ${bkSel.diffStudents >= 0 ? "+" : ""}${bkSel.diffStudents} / 日志 ${bkSel.diffLogs >= 0 ? "+" : ""}${bkSel.diffLogs}`;
    if (!window.confirm(d1)) return;
    if (!window.confirm("再次确认：当前数据会先自动另存为 pre_restore 备份（可再恢复回来），然后被该备份覆盖。继续？")) return;
    setBusy(true);
    try {
      const r = await post("/api/restore", { filename: bkSel.name });
      const d = await r.json();
      if (d.ok) {
        window.alert(`✅ 恢复完成：${d.students} 名学员 / ${d.logs} 条日志。页面即将刷新数据。`);
        onRestored();
      } else window.alert(`❌ ${d.error || "恢复失败"}`);
    } catch {
      window.alert("❌ 连接失败");
    } finally {
      setBusy(false);
    }
  };
  const inp = "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400";
  if (stale) return /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "bg-red-50 border border-red-300 rounded-xl p-3 space-y-1.5" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-red-700" }, "⚠️ 服务器还在运行旧版本"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600" }, "界面已是新版，但数据体检 / 邮件 / 备份恢复需要新版 server.py 支持。请："), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600 font-mono bg-red-100 rounded-lg px-2 py-1.5" }, "1. 用新版 server.py 覆盖 CMS 目录里的旧文件", /* @__PURE__ */ React.createElement("br", null), "2. 终端运行 ./cms.sh restart", /* @__PURE__ */ React.createElement("br", null), "3. 刷新本页面"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "验证方法：浏览器打开 /api/ping，version 应为 4.3.3-aws")));
  return /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "🩺 数据体检"), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: runHC,
      disabled: hcBusy,
      className: "w-full bg-teal-50 active:bg-teal-100 disabled:opacity-50 text-teal-700 border border-teal-200 py-2.5 rounded-xl font-bold text-sm"
    },
    hcBusy ? "体检中…" : "运行数据体检"
  ), hc && !hc.error && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-1 text-xs text-gray-600" }, /* @__PURE__ */ React.createElement("p", null, "学员 ", hc.students, "（活跃 ", hc.activeStudents, "）· 日志 ", hc.logs, " 条 · 库 ", hc.dbSizeKB, " KB"), /* @__PURE__ */ React.createElement("p", { className: hc.mismatchCount ? "text-amber-600 font-bold" : "text-green-600" }, "账目核对: ", hc.mismatchCount ? `${hc.mismatchCount} 人不一致` : "全部一致 ✓"), (hc.mismatches || []).slice(0, 8).map((m, i) => /* @__PURE__ */ React.createElement("p", { key: i, className: "pl-2 text-amber-700" }, "· ", m.name, ": 余额 ", m.balance, "，日志合计 ", m.logsSum, "（差 ", m.diff > 0 ? "+" : "", m.diff, "）")), hc.duplicateNames.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-amber-600" }, "重名学员: ", hc.duplicateNames.join("、")), hc.missingPhotos.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-amber-600" }, "照片文件丢失: ", hc.missingPhotos.length, " 人"), hc.conflictCopies.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-red-600 font-bold" }, "⚠️ iCloud 冲突副本: ", hc.conflictCopies.join("、")), /* @__PURE__ */ React.createElement("p", null, "待审申请 ", hc.pendingCount, " 条 · 最近备份 ", hc.lastBackup || "无", "（", hc.backupCount, " 份）")), hc && hc.error && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "体检失败，请重试")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "⚡ 待续课提醒阈值（剩余 ≤N 节）"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, [1, 2, 3, 5].map((d) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: d,
      onClick: () => {
        saveRenewTh(d);
        post("/api/config", { renew_threshold: d }).catch(() => {
        });
      },
      className: `flex-1 py-2 rounded-xl text-xs font-bold border ${renewTh === d ? "bg-indigo-600 text-white border-indigo-600" : "bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100"}`
    },
    d,
    " 节"
  ))), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "影响学员页「低余额」筛选和每周邮件中的待续课名单")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "📱 主屏幕 App / PWA 缓存"), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: clearPwaCache,
      className: "w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm"
    },
    "清理 PWA 缓存并刷新"
  ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "用于更新主屏幕图标、Service Worker 或修复旧页面缓存。")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "📧 每周汇总邮件（周一 10:00）"), !cfg ? /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "加载中…") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
    "input",
    {
      className: inp,
      placeholder: "收件邮箱",
      value: cfg.email_to || "",
      onChange: (e) => setCfg({ ...cfg, email_to: e.target.value })
    }
  ), /* @__PURE__ */ React.createElement(
    "input",
    {
      className: inp,
      placeholder: "发件 Gmail 地址",
      value: cfg.smtp_user || "",
      onChange: (e) => setCfg({ ...cfg, smtp_user: e.target.value })
    }
  ), /* @__PURE__ */ React.createElement(
    "input",
    {
      className: inp,
      type: "password",
      value: pw,
      onChange: (e) => setPw(e.target.value),
      placeholder: cfg.hasPassword ? "应用专用密码（已保存，留空不变）" : "Gmail 应用专用密码（16位）"
    }
  ), /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-600" }, "每周一自动发送"), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => setCfg({ ...cfg, weekly_enabled: !cfg.weekly_enabled }),
      className: `relative inline-flex h-6 w-11 items-center rounded-full transition ${cfg.weekly_enabled ? "bg-indigo-600" : "bg-gray-300"}`
    },
    /* @__PURE__ */ React.createElement("span", { className: `inline-block h-4 w-4 transform rounded-full bg-white transition ${cfg.weekly_enabled ? "translate-x-6" : "translate-x-1"}` })
  )), cfgMsg && /* @__PURE__ */ React.createElement("p", { className: `text-xs font-medium ${cfgMsg.startsWith("✅") ? "text-green-600" : cfgMsg.startsWith("❌") ? "text-red-500" : "text-gray-500"}` }, cfgMsg), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: saveCfg,
      disabled: busy,
      className: "flex-1 bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
    },
    "保存配置"
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: testEmail,
      disabled: busy,
      className: "flex-1 bg-white border border-indigo-300 active:bg-indigo-50 disabled:opacity-50 text-indigo-700 py-2.5 rounded-xl font-bold text-sm"
    },
    "发送测试邮件"
  )), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "需要 Gmail「应用专用密码」，获取方法见《邮件设置教程》文档"))), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "♻️ 备份与恢复"), !bks ? /* @__PURE__ */ React.createElement("button", { onClick: loadBks, className: "w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm" }, "查看备份列表") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "max-h-44 overflow-y-auto space-y-1 modal-scroll" }, bks.length === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 text-center py-2" }, "暂无备份"), bks.map((b) => /* @__PURE__ */ React.createElement(
    "button",
    {
      key: b.name,
      onClick: () => pickBk(b.name),
      className: `w-full text-left px-3 py-2 rounded-xl border text-xs ${bkSel?.name === b.name ? "border-indigo-400 bg-indigo-50" : "border-gray-200 bg-gray-50 active:bg-gray-100"}`
    },
    /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-700" }, b.mtime),
    /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 ml-2" }, (b.size / 1024).toFixed(0), " KB"),
    b.name.startsWith("pre_restore") && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-amber-600 font-bold" }, "恢复前存档")
  ))), bkSel && (bkSel.valid ? /* @__PURE__ */ React.createElement("div", { className: "bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-1 text-xs text-indigo-800" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, bkSel.students, " 名学员 · ", bkSel.logs, " 条日志"), /* @__PURE__ */ React.createElement("p", null, "与当前相比: 学员 ", bkSel.diffStudents >= 0 ? "+" : "", bkSel.diffStudents, " · 日志 ", bkSel.diffLogs >= 0 ? "+" : "", bkSel.diffLogs), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: doRestore,
      disabled: busy,
      className: "w-full mt-1 bg-red-600 active:bg-red-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
    },
    "恢复此备份（双重确认）"
  )) : /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "该备份文件已损坏，不可恢复")))));
}
function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState(() => localStorage.getItem(`lp_admin_email_${tenantSlug}`) || "");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e && e.preventDefault();
    if (!email || !pw) {
      setErr("请输入管理员邮箱和密码");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/s/" + encodeURIComponent(tenantSlug) + "/v1/auth/legacy-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pw }),
        credentials: "include"
      });
      const d = await r.json();
      if (d.ok) {
        localStorage.setItem(`lp_admin_email_${tenantSlug}`, email);
        onLogin();
      } else {
        setErr(d.error || "密码错误");
        setPw("");
      }
    } catch {
      setErr("连接失败，请重试");
    } finally {
      setBusy(false);
    }
  };
  return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-950 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-3xl p-8 w-full max-w-xs shadow-2xl text-center anim" }, /* @__PURE__ */ React.createElement("img", { src: "/logo.png", alt: "Studio", className: "w-36 mx-auto mb-3" }), /* @__PURE__ */ React.createElement("p", { className: "tenant-slogan text-sm text-gray-500 italic mb-4" }, "Learn, grow, and feel confident."), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mb-6" }, "请输入 Studio Admin 账号"), /* @__PURE__ */ React.createElement("form", { onSubmit: submit, className: "space-y-3" }, /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "email",
      placeholder: "管理员邮箱",
      value: email,
      onChange: (e) => setEmail(e.target.value),
      autoFocus: true,
      className: "w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-sm focus:ring-2 focus:ring-indigo-500"
    }
  ), /* @__PURE__ */ React.createElement(
    "input",
    {
      type: "password",
      placeholder: "密码",
      value: pw,
      onChange: (e) => setPw(e.target.value),
      className: "w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-lg tracking-widest focus:ring-2 focus:ring-indigo-500"
    }
  ), err && /* @__PURE__ */ React.createElement("p", { className: "text-red-500 text-xs font-medium" }, err), /* @__PURE__ */ React.createElement(
    "button",
    {
      type: "submit",
      disabled: busy || !email || !pw,
      className: "w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm"
    },
    busy ? "验证中..." : "进入系统 →"
  ))));
}
function App() {
  const [pinOK, setPinOK] = useState(sessOK);
  const [pinEnabled, setPinEnabled] = useState(() => localStorage.getItem("lp_pin_enabled") === "true");
  const togglePin = (val) => {
    setPinEnabled(val);
    localStorage.setItem("lp_pin_enabled", val ? "true" : "false");
  };
  const [db, setDb] = useState({ students: [], logs: [], rosters: {}, pending: [] });
  const [tab, setTab] = useState("dashboard");
  const [moreOpen, setMoreOpen] = useState(false);
  const [selS, setSelS] = useState(null);
  const [editP, setEditP] = useState(false);
  const [busy, setBusy] = useState(false);
  const [conn, setConn] = useState(false);
  const [connErr, setConnErr] = useState(null);
  const [toast, setToast] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [newPin1, setNewPin1] = useState("");
  const [newPin2, setNewPin2] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [pwOld, setPwOld] = useState("");
  const [pwNew1, setPwNew1] = useState("");
  const [pwNew2, setPwNew2] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [gOpen, setGOpen] = useState(false);
  const [gQ, setGQ] = useState("");
  const [portLB, setPortLB] = useState(null);
  const [portUpload, setPortUpload] = useState(false);
  const [portUpFile, setPortUpFile] = useState(null);
  const [portEdit, setPortEdit] = useState(null);
  const [portBusy, setPortBusy] = useState(false);
  const lbTouchX = useRef(0);
  const [inactiveDays, setInactiveDays] = useState(() => parseInt(localStorage.getItem("lp_inactive_days") || "90", 10));
  const saveInactiveDays = (v) => {
    const n = parseInt(v, 10);
    if (n > 0) {
      setInactiveDays(n);
      localStorage.setItem("lp_inactive_days", String(n));
    }
  };
  const [srch, setSrch] = useState("");
  const [sortBy, setSortBy] = useState("date-desc");
  const [filterBy, setFilterBy] = useState("all");
  const [rDate, setRDate] = useState(todayISO);
  const [rPick, setRPick] = useState(null);
  const [grpSel, setGrpSel] = useState("");
  const [schedules, setSchedules] = useState([]);
  const [bizStats, setBizStats] = useState(null);
  const [schedEdit, setSchedEdit] = useState(null);
  const [schedPick, setSchedPick] = useState(null);
  const [renewTh, setRenewTh] = useState(() => parseInt(localStorage.getItem("lp_renew_threshold") || "2", 10));
  const saveRenewTh = (v) => {
    const n = parseInt(v, 10);
    if (n >= 0) {
      setRenewTh(n);
      localStorage.setItem("lp_renew_threshold", String(n));
    }
  };
  const [tuStu, setTuStu] = useState(null);
  const [settleMode, setSettleMode] = useState("topup");
  const [rfCr, setRfCr] = useState("");
  const [rfAmt, setRfAmt] = useState("");
  const [rfReason, setRfReason] = useState("");
  const [tuCr, setTuCr] = useState("");
  const [tuFee, setTuFee] = useState("");
  const [tuPkg, setTuPkg] = useState("");
  const [tuPay, setTuPay] = useState("微信");
  const [lSrch, setLSrch] = useState("");
  const [lStu, setLStu] = useState(null);
  const [lAct, setLAct] = useState("");
  const [lDateFrom, setLDateFrom] = useState("");
  const [lDateTo, setLDateTo] = useState("");
  const [lPage, setLPage] = useState(1);
  const LPP = 30;
  const [sPeriod, setSPeriod] = useState("monthly");
  const [sYear, setSYear] = useState(String((/* @__PURE__ */ new Date()).getFullYear()));
  const [sFrom, setSFrom] = useState("");
  const [sTo, setSTo] = useState("");
  const [sStu, setSStu] = useState(null);
  const [sStu2, setSStu2] = useState(null);
  const [approveCredits, setApproveCredits] = useState({});
  const [pkgEditId, setPkgEditId] = useState(null);
  const [pkgName, setPkgName] = useState("");
  const [pkgCredits, setPkgCredits] = useState("");
  const [pkgPrice, setPkgPrice] = useState("");
  const [tenantBrand, setTenantBrand] = useState(() => window.STUDIOSAAS_BRAND || {});
  const [formPhoto, setFormPhoto] = useState("");
  const [editPhoto, setEditPhoto] = useState("");
  const cooldowns = useRef(/* @__PURE__ */ new Set());
  const wasDownRef = useRef(false);
  const showToast = (msg, type = "success", action = null) => setToast({ msg, type, action, key: Date.now() });
  useEffect(() => {
    const syncBrand = (event) => setTenantBrand(event?.detail || window.STUDIOSAAS_BRAND || {});
    window.addEventListener("studiosaas:brand", syncBrand);
    syncBrand();
    return () => window.removeEventListener("studiosaas:brand", syncBrand);
  }, []);
  const tenantLogoUrl = tenantBrand.logo_url || tenantBrand.logoUrl || "/logo-light.png";
  const tenantDisplayName = tenantBrand.name || tenantBrand.studioName || "Studio";
  const preferenceProfile = () => {
    const raw = tenantBrand.registration_profile || tenantBrand.registrationProfile || {};
    const fields = Array.isArray(raw.fields) && raw.fields.length ? raw.fields : [
      { key: "interests", label: "Interests", placeholder: "What does the student enjoy?" },
      { key: "experience", label: "Experience", placeholder: "Beginner, some experience, advanced" },
      { key: "goals", label: "Goals", placeholder: "Confidence, skills, exam prep, fun" }
    ];
    return {
      title: raw.title || "Student Preferences",
      fields: fields.filter((f) => f && f.key && f.label).map((f) => ({
        key: String(f.key).trim(),
        label: String(f.label).trim(),
        placeholder: String(f.placeholder || "").trim()
      }))
    };
  };
  const preferenceValue = (source, key) => {
    const prefs = source?.preferences && typeof source.preferences === "object" ? source.preferences : {};
    return prefs[key] ?? source?.[key] ?? "";
  };
  const collectPreferences = (fd) => {
    const prefs = {};
    preferenceProfile().fields.forEach((field) => {
      prefs[field.key] = (fd.get(`pref_${field.key}`) || "").trim();
    });
    return prefs;
  };
  const legacyPreferenceKeys = ["artStyle", "favArtist", "experience", "goals"];
  const legacyPreferenceValues = (prefs, fd = null, source = null) => {
    const out = {};
    legacyPreferenceKeys.forEach((key) => {
      out[key] = (prefs[key] || (fd ? fd.get(key) : "") || source?.[key] || "").trim();
    });
    return out;
  };
  const preferenceRows = (source) => {
    const prefs = source?.preferences && typeof source.preferences === "object" ? source.preferences : {};
    return preferenceProfile().fields.map((field) => ({ ...field, value: prefs[field.key] ?? source?.[field.key] ?? "" })).filter((row) => row.value);
  };
  const copyText = (str, successMsg) => {
    const onOk = () => showToast(successMsg || "已复制");
    const onFail = () => showToast("复制失败，请手动复制", "error");
    const doFallback = () => {
      try {
        const ta = document.createElement("textarea");
        ta.value = str;
        ta.style.cssText = "position:fixed;opacity:0;top:0;left:0;pointer-events:none;";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(ta);
        copied ? onOk() : onFail();
      } catch (e) {
        onFail();
      }
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(str).then(onOk).catch(doFallback);
    } else {
      doFallback();
    }
  };
  const confirm = (message, onConfirm, opts = {}) => setConfirmDialog({ message, onConfirm, ...opts });
  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setGOpen((o) => !o);
        setGQ("");
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  useEffect(() => {
    const onKey = (e) => {
      if (portLB) {
        if (e.key === "ArrowRight") setPortLB((p) => p && p.idx < p.items.length - 1 ? { ...p, idx: p.idx + 1 } : p);
        if (e.key === "ArrowLeft") setPortLB((p) => p && p.idx > 0 ? { ...p, idx: p.idx - 1 } : p);
        if (e.key === "Escape") setPortLB(null);
      } else if (portEdit && e.key === "Escape") setPortEdit(null);
      else if (portUpload && e.key === "Escape") {
        if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
        setPortUpload(false);
        setPortUpFile(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [portLB, portEdit, portUpload, portUpFile]);
  useEffect(() => {
    fetch("/v1/auth/me", { credentials: "include" }).then((r) => r.json()).then((d) => {
      const memberships = d.memberships || [];
      if (d.ok && memberships.some((m) => m.tenant_slug === tenantSlug && ["owner", "admin", "platform_super_admin", "super_admin"].includes(m.role))) {
        setLoggedIn(true);
      }
    }).catch(() => {
    });
  }, []);
  const apiHeaders = () => ({ "Content-Type": "application/json" });
  const revRef = useRef(0);
  useEffect(() => {
    if (loggedIn && (!pinEnabled || pinOK)) load();
  }, [loggedIn, pinOK, pinEnabled]);
  useEffect(() => {
    if (!loggedIn || pinEnabled && !pinOK) return;
    const id = setInterval(async () => {
      try {
        const r = await fetch("/api/ping");
        if (r.ok) {
          if (wasDownRef.current) {
            wasDownRef.current = false;
            load();
            showToast("已重新连接，数据已刷新");
          }
        } else {
          wasDownRef.current = true;
          setConn(false);
        }
      } catch {
        wasDownRef.current = true;
        setConn(false);
      }
    }, 3e4);
    return () => clearInterval(id);
  }, [loggedIn, pinOK, pinEnabled]);
  const doLogout = async () => {
    await fetch("/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => {
    });
    clearSess();
    setPinOK(false);
    setLoggedIn(false);
    setConn(false);
    setDb({ students: [], logs: [], rosters: {}, pending: [] });
    setShowSettings(false);
  };
  const changeWebPw = async () => {
    if (!pwOld || !pwNew1) {
      setPwMsg("请填写旧密码和新密码");
      return;
    }
    if (pwNew1 !== pwNew2) {
      setPwMsg("两次新密码不一致");
      return;
    }
    if (pwNew1.length < 8) {
      setPwMsg("新密码至少 8 位");
      return;
    }
    setPwBusy(true);
    setPwMsg("");
    try {
      const r = await fetch("/v1/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ oldPassword: pwOld, newPassword: pwNew1 }),
        credentials: "include"
      });
      const d = await r.json();
      if (d.ok) {
        setPwOld("");
        setPwNew1("");
        setPwNew2("");
        setPwMsg("✅ 密码已更新");
      } else {
        setPwMsg(`❌ ${d.message || d.error || "修改失败"}`);
      }
    } catch {
      setPwMsg("❌ 连接失败");
    } finally {
      setPwBusy(false);
    }
  };
  const load = async () => {
    setBusy(true);
    setConnErr(null);
    try {
      const r = await fetch("/api/data", { credentials: "include" });
      if (r.status === 401) {
        setLoggedIn(false);
        setBusy(false);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (!d.rosters) d.rosters = {};
      d.students = d.students.map((s) => ({
        email: "",
        wechat: "",
        archived: false,
        firstName: s.name || "",
        lastName: "",
        photo: "",
        artStyle: "",
        favArtist: "",
        experience: "",
        goals: "",
        preferences: {},
        birthday: "",
        ...s
      }));
      if (!d.pending) d.pending = [];
      if (!d.packages) d.packages = [{ id: 1, name: "标准课包", credits: 10, price: 1200 }];
      revRef.current = d.rev || 1;
      setDb(d);
      setConn(true);
      loadSchedules();
    } catch (e) {
      setConnErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const save = async (nd, force = false) => {
    setDb(nd);
    try {
      const body = { ...nd, rev: revRef.current, ...force ? { force: true } : {} };
      const r = await fetch("/api/save", {
        method: "POST",
        headers: apiHeaders(),
        credentials: "include",
        body: JSON.stringify(body)
      });
      if (r.status === 401) {
        showToast("登录已过期，请重新登录 / Session expired", "error");
        setTimeout(doLogout, 1500);
        return;
      }
      if (r.status === 403) {
        showToast("无权保存此租户数据 / No permission for this tenant.", "error");
        return;
      }
      if (r.status === 409) {
        const d2 = await r.json().catch(() => ({}));
        if (d2.status === "conflict") {
          showToast("数据已在其他设备/标签页被修改，正在刷新…", "error");
          setTimeout(load, 800);
        } else if (d2.status === "shrink_guard") {
          confirm(
            `⚠️ 安全拦截：${d2.message || `数据量将从 ${d2.current} 减少到 ${d2.incoming}`} 如果这不是你刻意删除的结果，请选择取消并刷新页面！`,
            async () => {
              await save(nd, true);
            },
            { danger: true, confirmText: "我确认，继续保存" }
          );
        }
        return;
      }
      if (!r.ok) throw new Error("save failed");
      const d = await r.json().catch(() => null);
      if (d && d.rev) {
        revRef.current = d.rev;
        setDb((prev) => ({ ...prev, rev: d.rev }));
      }
    } catch (err) {
      if (!String(err).includes("401")) showToast("数据未能同步到服务器！", "error");
    }
  };
  const exportDB = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(db, null, 2)], { type: "application/json" }));
    a.download = `Studio_${todayISO()}.json`;
    a.click();
  };
  const activityMap = useMemo(() => {
    const map = {};
    const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1e3;
    db.logs.forEach((l) => {
      if (l.action !== "上课签到") return;
      const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
      if (m) {
        const d = /* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`);
        if (!isNaN(d) && d.getTime() >= cutoff)
          map[l.studentName] = (map[l.studentName] || 0) + 1;
      }
    });
    return map;
  }, [db.logs]);
  const getTag = (s) => {
    const cnt = activityMap[s.name] || 0;
    if (cnt >= 4) return { icon: "🔥", label: "活跃", cls: "bg-red-100 text-red-700" };
    if (cnt >= 1) return { icon: "💤", label: "低频", cls: "bg-gray-100 text-gray-500" };
    if ((parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays)
      return { icon: "⚠️", label: "流失风险", cls: "bg-orange-100 text-orange-600" };
    return null;
  };
  const upcomingBirthdays = useMemo(() => {
    const now = /* @__PURE__ */ new Date();
    const out = [];
    db.students.forEach((s) => {
      if (s.archived) return;
      const m = String(s.birthday || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (!m) return;
      for (let i = 0; i < 14; i++) {
        const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
        if (d.getMonth() + 1 === parseInt(m[2], 10) && d.getDate() === parseInt(m[3], 10)) {
          const age = d.getFullYear() - parseInt(m[1], 10);
          out.push({ s, in: i, md: `${m[3]}/${m[2]}`, age });
          break;
        }
      }
    });
    return out.sort((a, b) => a.in - b.in);
  }, [db.students]);
  const sortedFiltered = useMemo(() => {
    let list = [...db.students];
    if (filterBy === "archived") {
      list = list.filter((s) => s.archived);
    } else {
      if (!filterBy || filterBy === "all") list = list.filter((s) => !s.archived);
      if (filterBy === "active") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0);
      if (filterBy === "low") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && (parseInt(s.balance, 10) || 0) <= renewTh);
      if (filterBy === "zero") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 0);
      if (filterBy === "tag-hot") list = list.filter((s) => !s.archived && (activityMap[s.name] || 0) >= 4);
      if (filterBy === "tag-low") list = list.filter((s) => !s.archived && (activityMap[s.name] || 0) >= 1 && (activityMap[s.name] || 0) < 4);
      if (filterBy === "tag-risk") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.name] || 0) === 0);
    }
    if (srch) {
      const q = srch.toLowerCase();
      list = list.filter(
        (s) => s.name.toLowerCase().includes(q) || (s.firstName || "").toLowerCase().includes(q) || (s.lastName || "").toLowerCase().includes(q) || (s.mobile || "").includes(srch) || (s.email || "").toLowerCase().includes(q) || (s.wechat || "").toLowerCase().includes(q)
      );
    }
    const cmp = (a, b, dir = 1) => {
      const an = a || "", bn = b || "";
      return dir * an.localeCompare(bn, "zh-CN");
    };
    if (sortBy === "name-az") list.sort((a, b) => cmp(a.name, b.name));
    if (sortBy === "name-za") list.sort((a, b) => cmp(b.name, a.name));
    if (sortBy === "last-az") list.sort((a, b) => {
      const r = cmp(a.lastName, b.lastName);
      return r !== 0 ? r : cmp(a.firstName, b.firstName);
    });
    if (sortBy === "last-za") list.sort((a, b) => {
      const r = cmp(b.lastName, a.lastName);
      return r !== 0 ? r : cmp(b.firstName, a.firstName);
    });
    if (sortBy === "bal-desc") list.sort((a, b) => (parseInt(b.balance, 10) || 0) - (parseInt(a.balance, 10) || 0));
    if (sortBy === "bal-asc") list.sort((a, b) => (parseInt(a.balance, 10) || 0) - (parseInt(b.balance, 10) || 0));
    if (sortBy === "date-desc") list.sort((a, b) => (b.lastActive || "").localeCompare(a.lastActive || ""));
    return list;
  }, [db.students, srch, sortBy, filterBy, activityMap, inactiveDays, renewTh]);
  const sortedAZ = useMemo(
    () => [...db.students].filter((s) => !s.archived).sort((a, b) => a.name.localeCompare(b.name, "zh-CN")),
    [db.students]
  );
  const scheduledForDate = useMemo(() => {
    if (!TENANT_SLUG || !schedules.length) return [];
    const wd = (/* @__PURE__ */ new Date(`${rDate}T12:00:00`)).getDay();
    return schedules.filter((sc) => sc.weekday === wd);
  }, [schedules, rDate]);
  const scheduledIdSet = useMemo(
    () => new Set(scheduledForDate.flatMap((sc) => sc.students.map((st) => st.id))),
    [scheduledForDate]
  );
  const dayIds = useMemo(() => {
    const manual = db.rosters[rDate] || [];
    return [.../* @__PURE__ */ new Set([...scheduledIdSet, ...manual])];
  }, [db.rosters, rDate, scheduledIdSet]);
  const todayEffectiveCount = useMemo(() => {
    const manual = db.rosters[todayISO()] || [];
    const wd = (/* @__PURE__ */ new Date()).getDay();
    const sched = schedules.filter((sc) => sc.weekday === wd).flatMap((sc) => sc.students.map((st) => st.id));
    return (/* @__PURE__ */ new Set([...sched, ...manual])).size;
  }, [db.rosters, schedules]);
  const availRoster = useMemo(
    () => sortedAZ.filter((s) => !dayIds.includes(s.id)),
    [sortedAZ, dayIds]
  );
  const analytics = useMemo(() => {
    const totalStudents = db.students.filter((s) => !s.archived).length;
    const totalBalance = db.students.reduce((a, b) => a + (parseInt(b.balance, 10) || 0), 0);
    const totalCheckins = db.logs.filter((l) => l.action === "上课签到").length;
    const totalRevenue = db.logs.reduce((s, l) => s + (parseFloat(l.feePaid) || 0), 0);
    const lowBalance = [...db.students].filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) <= 2).sort((a, b) => (parseInt(a.balance, 10) || 0) - (parseInt(b.balance, 10) || 0));
    const inactive = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays).sort((a, b) => daysSince(b.lastActive) - daysSince(a.lastActive));
    const todayRoster = db.rosters[todayISO()] || [];
    const allMonths = {}, allYears = {};
    db.logs.forEach((l) => {
      const mk = parseMonthKey(l.date);
      if (!mk) return;
      const yk = mk.split("-")[0];
      if (!allMonths[mk]) allMonths[mk] = { revenue: 0, checkins: 0, topups: 0 };
      if (!allYears[yk]) allYears[yk] = { revenue: 0, checkins: 0 };
      if (l.action === "上课签到") {
        allMonths[mk].checkins++;
        allYears[yk].checkins++;
      }
      if (l.feePaid) {
        allMonths[mk].revenue += parseFloat(l.feePaid);
        allYears[yk].revenue += parseFloat(l.feePaid);
      }
      if (l.action === "充值购课") allMonths[mk].topups++;
    });
    const monthlyReports = Object.keys(allMonths).sort().reverse().map((k) => ({ key: k, ...allMonths[k] }));
    const yearlyReports = Object.keys(allYears).sort().reverse().map((k) => ({ key: k, ...allYears[k] }));
    const availYears = Object.keys(allYears).sort().reverse();
    const now = /* @__PURE__ */ new Date();
    const chart12 = Array.from({ length: 12 }, (_, i) => {
      const d = new Date(now.getFullYear(), now.getMonth() - 11 + i, 1);
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      const mo = allMonths[k] || { revenue: 0, checkins: 0 };
      const lbl = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getFullYear()).slice(2)}`;
      return { k, l: lbl, rev: Math.round(mo.revenue), ci: mo.checkins };
    });
    const recentGroups = [];
    let curDateKey = null;
    for (const log of db.logs.slice(0, 30)) {
      const dk = String(log.date).split(",")[0];
      if (dk !== curDateKey) {
        curDateKey = dk;
        if (recentGroups.length >= 3) break;
        recentGroups.push({ date: dk, logs: [] });
      }
      if (recentGroups.length && recentGroups[recentGroups.length - 1].logs.length < 5)
        recentGroups[recentGroups.length - 1].logs.push(log);
    }
    return { totalStudents, totalBalance, totalCheckins, totalRevenue, lowBalance, inactive, todayRoster, monthlyReports, yearlyReports, availYears, chart12, recentGroups };
  }, [db, inactiveDays]);
  const statsData = useMemo(() => {
    let logs = sStu ? db.logs.filter((l) => {
      const s = db.students.find((x) => x.id === sStu);
      return s && (l.studentId === s.id || !l.studentId && l.studentName === s.name);
    }) : db.logs;
    if (sPeriod === "custom") {
      const from = sFrom && sTo && sFrom > sTo ? sTo : sFrom;
      const to = sFrom && sTo && sFrom > sTo ? sFrom : sTo;
      logs = logs.filter((l) => {
        const mk = parseMonthKey(l.date);
        if (!mk) return false;
        return (!from || mk >= from) && (!to || mk <= to);
      });
    } else if (sPeriod === "monthly" && sYear !== "all") {
      logs = logs.filter((l) => {
        const mk = parseMonthKey(l.date);
        return mk && mk.startsWith(sYear);
      });
    }
    const byP = {};
    logs.forEach((l) => {
      const mk = parseMonthKey(l.date);
      if (!mk) return;
      const key = sPeriod === "yearly" ? mk.split("-")[0] : mk;
      if (!byP[key]) byP[key] = { revenue: 0, checkins: 0, topups: 0 };
      if (l.action === "上课签到") byP[key].checkins++;
      if (l.action === "充值购课") {
        byP[key].topups++;
      }
      if (l.feePaid) byP[key].revenue += parseFloat(l.feePaid);
    });
    const rows = Object.keys(byP).sort().reverse().map((k) => ({ key: k, ...byP[k] }));
    return { rows, totalRev: rows.reduce((s, r) => s + r.revenue, 0), totalCI: rows.reduce((s, r) => s + r.checkins, 0) };
  }, [db, sPeriod, sYear, sFrom, sTo, sStu]);
  const studentStats = useMemo(() => {
    if (!sStu2) return null;
    const s = db.students.find((x) => x.id === sStu2);
    if (!s) return null;
    const logs = db.logs.filter((l) => l.studentId === s.id || !l.studentId && l.studentName === s.name);
    const totalSpent = logs.reduce((sum, l) => sum + (parseFloat(l.feePaid) || 0), 0);
    const checkins = logs.filter((l) => l.action === "上课签到").length;
    const topups = logs.filter((l) => l.action === "充值购课");
    const totalBought = topups.reduce((sum, l) => {
      const c = String(l.change).replace("+", "");
      return sum + (parseInt(c) || 0);
    }, 0);
    return {
      student: s,
      totalSpent,
      checkins,
      totalBought,
      topupCount: topups.length,
      first: logs.length ? logs[logs.length - 1].date : "",
      last: logs.length ? logs[0].date : "",
      logs
    };
  }, [db, sStu2]);
  const gResults = useMemo(() => {
    if (!gQ.trim()) return [];
    const q = gQ.trim().toLowerCase();
    return db.students.filter((s) => !s.archived && (s.name.toLowerCase().includes(q) || (s.firstName || "").toLowerCase().includes(q) || (s.lastName || "").toLowerCase().includes(q) || (s.mobile || "").includes(q) || (s.wechat || "").toLowerCase().includes(q))).slice(0, 10);
  }, [db.students, gQ]);
  const logDateISO = (ds) => {
    const m = String(ds).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
  };
  const filteredLogs = useMemo(() => {
    const stuName = lStu ? (db.students.find((x) => x.id === lStu) || {}).name : null;
    return db.logs.filter((l) => {
      if (stuName && l.studentName !== stuName) return false;
      if (lSrch && !l.studentName.toLowerCase().includes(lSrch.toLowerCase())) return false;
      if (lAct && l.action !== lAct) return false;
      if (lDateFrom || lDateTo) {
        const iso = logDateISO(l.date);
        if (lDateFrom && iso < lDateFrom) return false;
        if (lDateTo && iso > lDateTo) return false;
      }
      return true;
    });
  }, [db.logs, db.students, lStu, lSrch, lAct, lDateFrom, lDateTo]);
  const logPageCount = Math.max(1, Math.ceil(filteredLogs.length / LPP));
  const pagedLogs = filteredLogs.slice((lPage - 1) * LPP, lPage * LPP);
  const logActions = useMemo(() => [...new Set(db.logs.map((l) => l.action))].sort(), [db.logs]);
  useEffect(() => {
    setLPage(1);
  }, [lStu, lSrch, lAct, lDateFrom, lDateTo]);
  useEffect(() => {
    if (lPage > logPageCount) setLPage(logPageCount);
  }, [logPageCount]);
  const bizReport = useMemo(() => {
    const now = /* @__PURE__ */ new Date();
    const months = Array.from({ length: 6 }, (_, i) => {
      const d = new Date(now.getFullYear(), now.getMonth() - 5 + i, 1);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    });
    const rows = months.map((k) => ({
      k,
      label: `${k.split("-")[1]}/${k.split("-")[0].slice(2)}`,
      rev: 0,
      ci: 0,
      topups: 0,
      newStu: 0
    }));
    const byKey = Object.fromEntries(rows.map((r) => [r.k, r]));
    const pkgSales = {};
    db.logs.forEach((l) => {
      const mk = parseMonthKey(l.date);
      const r = mk && byKey[mk];
      if (r) {
        if (l.action === "上课签到") r.ci++;
        if (l.action === "充值购课") {
          r.topups++;
          r.rev += parseFloat(l.feePaid) || 0;
        }
        if (l.action === "新生注册" || l.action === "批准注册") r.newStu++;
      }
      if (l.action === "充值购课") {
        const m = String(l.note || "").match(/套餐:\s*([^|]+)/);
        const name = m ? m[1].trim() : "自定义";
        if (!pkgSales[name]) pkgSales[name] = { count: 0, revenue: 0 };
        pkgSales[name].count++;
        pkgSales[name].revenue += parseFloat(l.feePaid) || 0;
      }
    });
    const cutoff = Date.now() - 180 * 24 * 3600 * 1e3;
    const perStu = {};
    db.logs.forEach((l) => {
      if (l.action !== "上课签到") return;
      const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
      if (!m) return;
      const t = (/* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`)).getTime();
      if (t < cutoff) return;
      const key = l.studentId || l.studentName;
      (perStu[key] = perStu[key] || []).push(t);
    });
    let gaps = [];
    Object.values(perStu).forEach((ts) => {
      if (ts.length < 2) return;
      ts.sort((a, b) => a - b);
      for (let i = 1; i < ts.length; i++) gaps.push((ts[i] - ts[i - 1]) / 864e5);
    });
    const avgGap = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0;
    const pkgRank = Object.entries(pkgSales).sort((a, b) => b[1].revenue - a[1].revenue);
    return { rows, pkgRank, avgGap, regularStu: Object.values(perStu).filter((t) => t.length >= 2).length };
  }, [db.logs]);
  const exportBizCSV = () => {
    const head = ["月份", "营收(AUD)", "充值笔数", "消课次数", "新增学员"];
    const lines = bizReport.rows.map((r) => [r.label, r.rev.toFixed(0), r.topups, r.ci, r.newStu]);
    const pkg = bizReport.pkgRank.map(([n, d]) => ["课包:" + n, d.revenue.toFixed(0), d.count, "", ""]);
    const csv = [head, ...lines, [], ["课包销量排行", "营收", "笔数"], ...pkg].map((r) => r.join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }));
    a.download = `Studio_经营月报_${todayISO()}.csv`;
    a.click();
  };
  const payBreakdown = useMemo(() => {
    const map = {};
    db.logs.filter((l) => l.action === "充值购课").forEach((l) => {
      const pm = l.payMethod || "未记录";
      if (!map[pm]) map[pm] = { count: 0, revenue: 0 };
      map[pm].count++;
      map[pm].revenue += parseFloat(l.feePaid) || 0;
    });
    return Object.entries(map).sort((a, b) => b[1].revenue - a[1].revenue);
  }, [db.logs]);
  const mkLog = (sName, action, change, note, fee = 0, extra = {}) => {
    const matches = db.students.filter((x) => x.name === sName);
    const sidObj = matches.length === 1 ? { studentId: matches[0].id } : {};
    return { id: Date.now(), date: nowAU(), studentName: sName, ...sidObj, action, change, note, feePaid: fee, ...extra };
  };
  const checkIn = async (sid, sname) => {
    if (cooldowns.current.has(sid)) {
      showToast("请稍候再次操作", "warn");
      return;
    }
    if (busy) return;
    const student = db.students.find((s) => s.id === sid);
    if (!student || student.balance <= 0) {
      showToast(`${sname} 课时余额不足`, "error");
      return;
    }
    cooldowns.current.add(sid);
    setTimeout(() => cooldowns.current.delete(sid), 3e3);
    setBusy(true);
    try {
      let nb;
      if (TENANT_SLUG) {
        const res = await v1Api("/attendance/check-in", {
          method: "POST",
          body: JSON.stringify({ studentId: sid, note: "常规课程消耗", classDate: rDate })
        });
        nb = Number(res.newBalance);
        await load();
      } else {
        nb = Math.max(0, student.balance - 1);
        const ns = db.students.map((s) => s.id === sid ? { ...s, balance: nb, lastActive: todayISO() } : s);
        await save({ ...db, students: ns, logs: [mkLog(sname, "上课签到", -1, "常规课程消耗", 0, { studentId: sid }), ...db.logs] });
      }
      if (selS?.id === sid) setSelS((p) => ({ ...p, balance: nb }));
      const confirmMsg = nb === 0 ? `${sname} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～ 🎨` : `${sname} 今日已完成签到 ✓ 当前剩余 ${nb} 课时。Studio 感谢您的支持！🎨`;
      const act = { label: "📋 复制签到确认（发家长）", onClick: () => copyText(confirmMsg, "签到确认已复制") };
      if (nb === 0) showToast(`${sname} 课时已清零！请提醒续课 🔔`, "warn", act);
      else showToast(`${sname} 签到 ✓ 剩余 ${nb} 课时`, "success", act);
    } catch (e) {
      showToast(`签到失败：${e.message}`, "error");
    } finally {
      setBusy(false);
    }
  };
  const undoCheckIn = (sid, sname) => {
    confirm(`撤销 ${sname} 的最近一次签到记录，并恢复 1 课时。`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        if (TENANT_SLUG) {
          const entry = db.logs.find((l) => l.studentId === sid && l.action === "上课签到" && l.attendanceId);
          if (!entry) {
            showToast("未找到签到记录", "warn");
            return;
          }
          await v1Api(`/attendance/${entry.attendanceId}/void`, {
            method: "POST",
            body: JSON.stringify({ note: "管理员撤销" })
          });
          await load();
        } else {
          const idx = db.logs.findIndex((l) => (l.studentId === sid || !l.studentId && l.studentName === sname) && l.action === "上课签到");
          if (idx === -1) {
            showToast("未找到签到记录", "warn");
            return;
          }
          const ns = db.students.map((s) => s.id === sid ? { ...s, balance: (parseInt(s.balance, 10) || 0) + 1 } : s);
          const nl = db.logs.filter((_, i) => i !== idx);
          await save({ ...db, students: ns, logs: [mkLog(sname, "撤销签到", "+1", "管理员撤销", 0, { studentId: sid }), ...nl] });
        }
        if (selS?.id === sid) setSelS((p) => ({ ...p, balance: (parseInt(p.balance, 10) || 0) + 1 }));
        showToast(`已撤销 ${sname} 签到`, "warn");
      } catch (e) {
        showToast(`撤销失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    }, { confirmText: "确认撤销" });
  };
  const rosterDone = useMemo(() => {
    const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    const prefix = m ? `${m[3]}/${m[2]}/${m[1]}` : "__none__";
    const done = /* @__PURE__ */ new Set();
    db.logs.forEach((l) => {
      if (l.action === "上课签到" && String(l.date).startsWith(prefix)) {
        if (l.studentId) done.add(l.studentId);
        else {
          const s = db.students.find((x) => x.name === l.studentName);
          if (s) done.add(s.id);
        }
      }
    });
    return done;
  }, [db.logs, db.students, rDate]);
  const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const loadSchedules = async () => {
    if (!TENANT_SLUG) return;
    try {
      const d = await v1Api("/class-schedules");
      setSchedules(d.schedules || []);
    } catch (e) {
    }
    try {
      const dash = await v1Api("/dashboard");
      setBizStats((dash.dashboard || {}).business || null);
    } catch (e) {
    }
  };
  const saveSchedule = async () => {
    if (!schedEdit || busy) return;
    if (!schedEdit.label.trim()) {
      showToast("请输入班次名称（如：周三素描班）", "error");
      return;
    }
    setBusy(true);
    try {
      const body = JSON.stringify({
        label: schedEdit.label.trim(),
        weekday: Number(schedEdit.weekday),
        startTime: schedEdit.startTime,
        durationMinutes: Number(schedEdit.durationMinutes) || 60,
        capacity: Number(schedEdit.capacity) || 10,
        studentIds: schedEdit.studentIds
      });
      const d = schedEdit.id ? await v1Api(`/class-schedules/${schedEdit.id}`, { method: "PATCH", body }) : await v1Api("/class-schedules", { method: "POST", body });
      setSchedules(d.schedules || []);
      setSchedEdit(null);
      showToast("每周课表已保存");
    } catch (e) {
      showToast(`课表保存失败：${e.message}`, "error");
    } finally {
      setBusy(false);
    }
  };
  const deleteSchedule = (sc) => {
    confirm(`删除班次「${sc.label}」？（不影响任何学员和签到记录）`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        const d = await v1Api(`/class-schedules/${sc.id}`, { method: "DELETE" });
        setSchedules(d.schedules || []);
        if (schedEdit && schedEdit.id === sc.id) setSchedEdit(null);
        showToast(`班次「${sc.label}」已删除`, "warn");
      } catch (e) {
        showToast(`删除失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    }, { danger: true, confirmText: "确认删除" });
  };
  const groupToSchedule = () => {
    const ids = (db.groups || {})[grpSel] || [];
    if (!grpSel || !ids.length) {
      showToast("请先选择一个班组模板", "warn");
      return;
    }
    setSchedEdit({
      label: grpSel,
      weekday: (/* @__PURE__ */ new Date()).getDay(),
      startTime: "16:00",
      durationMinutes: 60,
      capacity: Math.max(10, ids.length),
      studentIds: ids
    });
    showToast("已带入模板学员，请确认周几与时间后保存");
  };
  const batchCheckIn = () => {
    const ids = dayIds;
    const already = ids.filter((id) => rosterDone.has(id)).length;
    const elig = ids.filter((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.balance > 0 && !rosterDone.has(id);
    });
    if (!elig.length) {
      showToast(already ? "今日排班学员均已签到 ✓" : "今日无可消课学员", "warn");
      return;
    }
    const skipNote = already ? `，${already} 人已单独签到将跳过` : "";
    confirm(`确认对今日 ${elig.length} 名学员执行全员消课？（余额为 0、已归档${skipNote}）`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        if (TENANT_SLUG) {
          const failed = [];
          for (const id of elig) {
            const s = db.students.find((x) => x.id === id);
            if (!s) continue;
            try {
              await v1Api("/attendance/check-in", {
                method: "POST",
                body: JSON.stringify({ studentId: id, note: "全员消课", classDate: rDate })
              });
            } catch (e) {
              failed.push(s.name);
            }
          }
          await load();
          if (failed.length) showToast(`全员消课完成，${failed.length} 人失败：${failed.join("、")}`, "warn");
          else showToast(`全员消课完成，共 ${elig.length} 人`);
        } else {
          let cur = { ...db };
          const base = Date.now();
          elig.forEach((id, i) => {
            const s = cur.students.find((x) => x.id === id);
            if (!s) return;
            const nb = Math.max(0, s.balance - 1);
            cur = {
              ...cur,
              students: cur.students.map((x) => x.id === id ? { ...x, balance: nb, lastActive: todayISO() } : x),
              logs: [{ ...mkLog(s.name, "上课签到", -1, "全员消课", 0, { studentId: id }), id: base + i }, ...cur.logs]
            };
          });
          await save(cur);
          showToast(`全员消课完成，共 ${elig.length} 人`);
        }
      } finally {
        setBusy(false);
      }
    }, { confirmText: `消课 ${elig.length} 人` });
  };
  const saveGroup = () => {
    const ids = db.rosters[rDate] || [];
    if (!ids.length) {
      showToast("当前日期没有排班可保存", "warn");
      return;
    }
    const name = (window.prompt("模板名称（如：周六上午班）") || "").trim();
    if (!name) return;
    save({ ...db, groups: { ...db.groups || {}, [name]: ids } });
    showToast(`模板「${name}」已保存（${ids.length} 人）`);
  };
  const applyGroup = async () => {
    if (!grpSel) return;
    const ids = (db.groups || {})[grpSel] || [];
    const cur = db.rosters[rDate] || [];
    const add = ids.filter((id) => !cur.includes(id) && db.students.some((s) => s.id === id && !s.archived));
    if (!add.length) {
      showToast("模板学员均已在当前排班中", "warn");
      return;
    }
    await save({ ...db, rosters: { ...db.rosters, [rDate]: [...cur, ...add] } });
    showToast(`已套用「${grpSel}」，新增 ${add.length} 人`);
  };
  const deleteGroup = () => {
    if (!grpSel) return;
    confirm(`删除模板「${grpSel}」？（不影响任何排班和学员数据）`, async () => {
      const g = { ...db.groups || {} };
      delete g[grpSel];
      await save({ ...db, groups: g });
      setGrpSel("");
      showToast("模板已删除", "warn");
    }, { danger: true, confirmText: "删除模板" });
  };
  const openGrowthReport = (s) => {
    const logs = db.logs.filter((l) => l.studentId === s.id || !l.studentId && l.studentName === s.name);
    const parseD = (d) => {
      const m = String(d).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
      return m ? /* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`) : null;
    };
    const checkins = logs.filter((l) => l.action === "上课签到");
    const dates = logs.map((l) => parseD(l.date)).filter(Boolean).sort((a, b) => a - b);
    const joinDate = dates.length ? dates[0] : null;
    const days = joinDate ? Math.max(1, Math.round((Date.now() - joinDate) / 864e5)) : 0;
    const bal = parseInt(s.balance, 10) || 0;
    const port = s.portfolio || [];
    const now = /* @__PURE__ */ new Date();
    const months = Array.from({ length: 6 }, (_, i) => {
      const d = new Date(now.getFullYear(), now.getMonth() - 5 + i, 1);
      return { k: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, l: `${d.getMonth() + 1}月`, n: 0 };
    });
    const mIdx = Object.fromEntries(months.map((m, i) => [m.k, i]));
    checkins.forEach((l) => {
      const d = parseD(l.date);
      if (!d) return;
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      if (k in mIdx) months[mIdx[k]].n++;
    });
    const maxM = Math.max(1, ...months.map((m) => m.n));
    const esc = (t) => String(t || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    const fmtD = (d) => d ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}` : "—";
    const isNew = checkins.length === 0;
    const shareMsg = isNew ? `欢迎 ${s.name} 加入 Studio！艺术之旅刚刚启程，期待用画笔记录每一份成长与快乐 🎨` : `${s.name} 在 Studio 已经学习了 ${days} 天，累计上课 ${checkins.length} 次，完成作品 ${port.length} 幅！每一笔都是成长的印记，期待继续陪伴 TA 用画笔探索世界 🎨`;
    const portHTML = port.length ? port.map((p) => `
            <figure class="art">
                <img src="${portfolioImgSrc(s.id, p)}" alt="作品"/>
                <figcaption>${esc(p.note) || "　"}<span>${esc((p.date || "").split("-").reverse().join("/"))}</span></figcaption>
            </figure>`).join("") : '<p class="empty">暂无作品记录 · 上传作品后报告会更精彩 🎨</p>';
    const barsHTML = months.map((m) => `
            <div class="bar"><span class="bn">${m.n || ""}</span><div class="fill" style="height:${Math.max(3, Math.round(m.n / maxM * 76))}px"></div><span class="bl">${m.l}</span></div>`).join("");
    const photoHTML = s.photo ? `<img class="avatar" src="${mediaSrc(s.photo)}" alt=""/>` : `<div class="avatar ph">${esc((s.name || "?").slice(0, 1))}</div>`;
    const reportBrand = window.STUDIOSAAS_BRAND || {};
    const reportSlogan = reportBrand.slogan || "Learn, grow, and feel confident.";
    const reportStudioName = reportBrand.name || "Studio";
    const reportJoinText = reportBrand.category === "art" ? "艺术之旅刚刚启程" : "学习旅程刚刚启程";
    const html = `<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(s.name)} · 成长报告 · Studio</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#efeae2;color:#3a3a44;padding:24px}
.sheet{max-width:760px;margin:0 auto;background:#fffdf9;border-radius:18px;overflow:hidden;box-shadow:0 10px 36px rgba(60,50,40,.10)}
.brandbar{display:flex;flex-direction:column;align-items:center;gap:7px;padding:32px 30px 18px}
.brandbar img{height:86px;width:auto}
.slogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:20px;color:#b08d57}
.hero{display:flex;align-items:center;gap:22px;padding:6px 36px 26px;border-bottom:1px solid #ece6db}
.avatar{width:90px;height:90px;border-radius:50%;object-fit:cover;border:3px solid #e6ddcd;flex-shrink:0}
.avatar.ph{display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:800;background:#f0ece4;color:#6f6f7c}
.hero h1{font-size:28px;color:#2f2c33;margin-bottom:5px}
.hero .sub{color:#8a857d;font-size:14px}
.hero .sub b{color:#b08d57}
.hero .tag{display:inline-block;font-size:11px;letter-spacing:2px;color:#b08d57;text-transform:uppercase;margin-bottom:7px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:24px 36px;background:#faf7f1}
.stat{text-align:center;break-inside:avoid}
.stat .v{font-size:30px;font-weight:800;color:#b08d57;line-height:1}
.stat .l{font-size:12px;color:#9a958c;margin-top:6px}
.sec{padding:24px 36px;border-top:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.sec.gal{break-inside:auto;page-break-inside:auto}
.sec h2{font-size:15px;margin-bottom:16px;color:#4a4751;letter-spacing:.5px;display:flex;align-items:center;gap:7px}
.chart{display:flex;align-items:flex-end;gap:16px;padding-top:4px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.bn{font-size:12px;font-weight:700;color:#b08d57;height:18px}
.fill{width:58%;background:#c4ad84;border-radius:5px 5px 0 0}
.bl{font-size:11px;color:#a8a299;margin-top:7px}
.gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.art{border-radius:12px;overflow:hidden;background:#f7f4ee;border:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.art img{width:100%;height:150px;object-fit:cover;display:block}
.art figcaption{font-size:12px;color:#5b5750;padding:8px 10px;display:flex;flex-direction:column;gap:2px}
.art figcaption span{font-size:11px;color:#a8a299}
.empty{color:#a8a299;text-align:center;padding:24px;font-size:14px}
.msg{background:#faf6ee;border-left:3px solid #b08d57;border-radius:0 12px 12px 0;padding:18px 22px;font-size:15px;line-height:1.8;color:#4a4751}
.foot{text-align:center;padding:22px;color:#aba89f;font-size:12px}
.foot .fslogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:16px;color:#b08d57;margin-bottom:4px}
.toolbar{max-width:760px;margin:0 auto 16px;display:flex;gap:10px;justify-content:flex-end}
.toolbar button{border:0;border-radius:12px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer}
.b1{background:#6f5b3e;color:#fff}.b2{background:#fffdf9;color:#6f5b3e;border:1px solid #ddd0bb}
@media print{body{background:#fff;padding:0}.toolbar{display:none}.sheet{box-shadow:none;border-radius:0}}
@media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}.gallery{grid-template-columns:repeat(2,1fr)}.hero{padding:6px 22px 22px}.sec{padding:20px 22px}}
</style></head><body>
<div class="toolbar">
  <button class="b2" id="copybtn">📋 复制成长寄语</button>
  <button class="b1" onclick="window.print()">🖨 保存为 PDF / 打印</button>
</div>
<div class="sheet">
  <div class="brandbar">
    <img src="/logo.png" alt="Studio"/>
	    <div class="slogan">${esc(reportSlogan)}</div>
  </div>
  <div class="hero">
    ${photoHTML}
    <div>
      <span class="tag">学员成长报告 · Growth Report</span>
      <h1>${esc(s.name)}</h1>
	      <div class="sub">${isNew ? `${esc(reportJoinText)} · 欢迎加入 ${esc(reportStudioName)}` : `已在 ${esc(reportStudioName)} 成长陪伴 <b>${days}</b> 天 · 入学于 ${fmtD(joinDate)}`}</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><div class="v">${checkins.length}</div><div class="l">累计上课</div></div>
    <div class="stat"><div class="v">${port.length}</div><div class="l">完成作品</div></div>
    <div class="stat"><div class="v">${bal}</div><div class="l">剩余课时</div></div>
    <div class="stat"><div class="v">${isNew ? "—" : days}</div><div class="l">陪伴天数</div></div>
  </div>
  <div class="sec">
    <h2>📈 近 6 个月上课足迹</h2>
    <div class="chart">${barsHTML}</div>
  </div>
  <div class="sec gal">
    <h2>🖼 作品集（${port.length} 幅）</h2>
    <div class="gallery">${portHTML}</div>
  </div>
  <div class="sec">
    <h2>💛 老师寄语</h2>
    <div class="msg">${esc(shareMsg)}</div>
  </div>
  <div class="foot">
	    <div class="fslogan">${esc(reportSlogan)}</div>
	    报告生成于 ${fmtD(/* @__PURE__ */ new Date())} · ${esc(reportStudioName)}
  </div>
</div>
<script>
/* C1+C2: 安全嵌入文本（不再用引号嵌套的内联 onclick）+ http 环境降级复制 */
var MSG = ${JSON.stringify(shareMsg)};
document.getElementById('copybtn').addEventListener('click', function(){
  var btn = this;
  var ok = function(){ btn.textContent = '✓ 已复制寄语'; };
  var fallback = function(){
    try {
      var ta = document.createElement('textarea');
      ta.value = MSG; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
      document.body.appendChild(ta); ta.focus(); ta.select();
      var done = document.execCommand('copy');
      document.body.removeChild(ta);
      done ? ok() : (btn.textContent = '复制失败，请长按选择');
    } catch(e) { btn.textContent = '复制失败，请长按选择'; }
  };
  if (navigator.clipboard && window.isSecureContext)
    navigator.clipboard.writeText(MSG).then(ok).catch(fallback);
  else fallback();
});
<\/script>
</body></html>`;
    const w = window.open("", "_blank");
    if (!w) {
      showToast("请允许弹出窗口以查看报告", "warn");
      return;
    }
    w.document.write(html);
    w.document.close();
  };
  const archiveStudent = (sid, sname, archive) => {
    confirm(
      archive ? `将 "${sname}" 移入归档库，不影响历史记录，随时可恢复。` : `将 "${sname}" 从归档库恢复为活跃学员。`,
      async () => {
        if (busy) return;
        setBusy(true);
        try {
          const ns = db.students.map((s) => s.id === sid ? { ...s, archived: archive } : s);
          await save({ ...db, students: ns, logs: [mkLog(sname, archive ? "归档学员" : "恢复学员", "0", archive ? "移入归档库" : "从归档库恢复", 0, { studentId: sid }), ...db.logs] });
          setSelS(null);
          setEditP(false);
          showToast(`${sname} 已${archive ? "归档" : "恢复"}`, "warn");
        } finally {
          setBusy(false);
        }
      },
      { confirmText: archive ? "确认归档" : "确认恢复" }
    );
  };
  const handleTopUp = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const credits = parseInt(fd.get("credits"), 10);
    const fee = parseFloat(fd.get("fee")) || 0;
    if (!tuStu) {
      showToast("请选择学员", "error");
      return;
    }
    if (isNaN(credits) || credits <= 0) {
      showToast("请输入有效课时数", "error");
      return;
    }
    const tuRemark = (fd.get("tuRemark") || "").trim();
    const doTopUp = async () => {
      if (busy) return;
      setBusy(true);
      try {
        const s = db.students.find((x) => x.id === tuStu);
        if (!s) return;
        const noteStr = [`套餐: ${tuPkg || "自定义"}`, `付款: ${tuPay}`, ...tuRemark ? [tuRemark] : []].join(" | ");
        if (TENANT_SLUG) {
          await v1Api(`/students/${s.id}/credit-transactions`, {
            method: "POST",
            body: JSON.stringify({
              transactionType: "purchase",
              amount: credits,
              feeAudCents: Math.round(fee * 100),
              note: noteStr
            })
          });
          await load();
        } else {
          const ns = db.students.map((x) => x.id === tuStu ? { ...x, balance: (parseInt(x.balance, 10) || 0) + credits, lastActive: todayISO() } : x);
          await save({ ...db, students: ns, logs: [mkLog(s.name, "充值购课", `+${credits}`, noteStr, fee, { payMethod: tuPay, studentId: s.id }), ...db.logs] });
        }
        e.target.reset();
        setTuCr("");
        setTuFee("");
        setTuPkg("");
        setTuPay("微信");
        setTuStu(null);
        const newBal = (parseInt(s.balance, 10) || 0) + credits;
        const cMsg = `${s.name} 您好！已为您成功充值 ${credits} 课时${fee ? `（实收 $${fee}）` : ""}，当前账户共 ${newBal} 课时。感谢您对 Studio 的信任！🎨`;
        showToast(
          `${s.name} 充值 ${credits} 课时 / $${fee}`,
          "success",
          { label: "📋 复制充值确认（发家长）", onClick: () => copyText(cMsg, "充值确认已复制") }
        );
      } catch (err) {
        showToast(`充值失败：${err.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const s0 = db.students.find((x) => x.id === tuStu);
    confirm(
      `确认为 ${s0 ? s0.name : ""} 充值 ${credits} 课时，实收 $${fee}（${tuPay}）${fee === 0 ? "——免费充课" : ""}？`,
      doTopUp,
      { confirmText: fee === 0 ? "确认免费充课" : "确认入账" }
    );
  };
  const handleRefund = async (e) => {
    e.preventDefault();
    const credits = parseInt(rfCr, 10);
    const amt = parseFloat(rfAmt) || 0;
    const s = db.students.find((x) => x.id === tuStu);
    if (!s) {
      showToast("请选择学员", "error");
      return;
    }
    if (isNaN(credits) || credits <= 0) {
      showToast("请输入有效退课节数", "error");
      return;
    }
    if (credits > (parseInt(s.balance, 10) || 0)) {
      showToast(`退课节数不能超过剩余课时（${s.balance}）`, "error");
      return;
    }
    if (amt < 0) {
      showToast("退款金额无效", "error");
      return;
    }
    if (!rfReason.trim()) {
      showToast("请填写退款原因", "error");
      return;
    }
    confirm(`确认为 ${s.name} 退课 ${credits} 节、退款 $${amt}（${tuPay}）？余额将从 ${s.balance} 减为 ${(parseInt(s.balance, 10) || 0) - credits}。`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        await v1Api(`/students/${s.id}/credit-transactions`, {
          method: "POST",
          body: JSON.stringify({
            transactionType: "refund",
            legacy_type: "refund_out",
            amount: credits,
            feeAudCents: Math.round(amt * 100),
            note: `退款退课 | 原因: ${rfReason.trim()} | 方式: ${tuPay}`
          })
        });
        await load();
        setRfCr("");
        setRfAmt("");
        setRfReason("");
        setTuStu(null);
        const cMsg = `${s.name} 您好！已为您办理退课 ${credits} 节${amt ? `、退款 $${amt}（${tuPay}）` : ""}，当前剩余 ${(parseInt(s.balance, 10) || 0) - credits} 课时。感谢您的理解与支持。`;
        showToast(
          `${s.name} 退课 ${credits} 节 / 退款 $${amt}`,
          "warn",
          { label: "📋 复制退款确认（发家长）", onClick: () => copyText(cMsg, "退款确认已复制") }
        );
      } catch (err) {
        showToast(`退款失败：${err.message}`, "error");
      } finally {
        setBusy(false);
      }
    }, { danger: true, confirmText: `确认退课 ${credits} 节` });
  };
  const handleAddStudent = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const firstName = fd.get("firstName").trim();
    const lastName = fd.get("lastName").trim();
    if (!firstName) {
      showToast("First Name 不能为空", "error");
      return;
    }
    const fullName = lastName ? `${firstName} ${lastName}` : firstName;
    const mobile = fd.get("mobile").trim();
    const email = fd.get("email").trim();
    const wechat = (fd.get("wechat") || "").trim();
    const balance = parseInt(fd.get("balance") || "0", 10);
    const remark = fd.get("remark") || "";
    const preferences = collectPreferences(fd);
    const legacyPrefs = legacyPreferenceValues(preferences, fd);
    const birthday = (fd.get("birthday") || "").trim();
    const doCreate = async () => {
      if (busy) return;
      setBusy(true);
      try {
        const ns = {
          id: Date.now(),
          firstName,
          lastName,
          name: fullName,
          mobile,
          email,
          wechat,
          photo: formPhoto,
          preferences,
          ...legacyPrefs,
          birthday,
          balance,
          remark,
          lastActive: todayISO(),
          archived: false
        };
        await save({ ...db, students: [ns, ...db.students], logs: [mkLog(fullName, "新生注册", `+${balance}`, "系统建档", 0, { studentId: ns.id }), ...db.logs] });
        e.target.reset();
        setFormPhoto("");
        setTab("students");
        setSrch("");
        showToast(`${fullName} 已建档`);
      } finally {
        setBusy(false);
      }
    };
    if (db.students.some((s) => s.name.toLowerCase() === fullName.toLowerCase())) {
      confirm(`已存在同名学员 "${fullName}"，仍要继续建档？`, doCreate, { confirmText: "继续建档" });
    } else {
      doCreate();
    }
  };
  const handleUpdateStudent = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const firstName = fd.get("firstName").trim();
    if (!firstName) {
      showToast("First Name 不能为空", "error");
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const lastName = fd.get("lastName").trim();
      const newName = lastName ? `${firstName} ${lastName}` : firstName;
      const mobile = fd.get("mobile").trim();
      const email = fd.get("email").trim();
      const wechat = (fd.get("wechat") || "").trim();
      const balance = parseInt(fd.get("balance") || String(selS.balance ?? 0), 10) || 0;
      const remark = fd.get("remark") || "";
      const preferences = collectPreferences(fd);
      const legacyPrefs = legacyPreferenceValues(preferences, fd, selS);
      const birthday = (fd.get("birthday") || "").trim();
      const diff = balance - (parseInt(selS.balance, 10) || 0);
      const oldName = selS.name;
      const ns = db.students.map((s) => s.id === selS.id ? { ...s, firstName, lastName, name: newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, photo: editPhoto, ...diff !== 0 ? { lastActive: todayISO() } : {} } : s);
      const otherSameName = db.students.some((s) => s.id !== selS.id && (s.name || "").toLowerCase() === oldName.toLowerCase());
      const nl = oldName !== newName ? db.logs.map((l) => {
        if (l.studentId === selS.id) return { ...l, studentName: newName };
        if (!l.studentId && !otherSameName && l.studentName === oldName) return { ...l, studentName: newName };
        return l;
      }) : db.logs;
      const changeStr = diff !== 0 ? diff > 0 ? `+${diff}` : `${diff}` : "0";
      const noteStr = diff !== 0 ? "管理端校准" : oldName !== newName ? `改名: ${oldName}→${newName}` : "信息修改";
      if (TENANT_SLUG) {
        await save({ ...db, students: ns, logs: nl });
        if (diff !== 0) {
          await v1Api(`/students/${selS.id}/credit-transactions`, {
            method: "POST",
            body: JSON.stringify({
              transactionType: "adjustment",
              legacy_type: diff > 0 ? "adjustment_in" : "adjustment_out",
              amount: Math.abs(diff),
              note: "管理端校准"
            })
          });
          await load();
        }
      } else {
        await save({ ...db, students: ns, logs: [mkLog(newName, diff !== 0 ? "调整课时" : "更新档案", changeStr, noteStr, 0, { studentId: selS.id }), ...nl] });
      }
      setSelS({ ...selS, firstName, lastName, name: newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, photo: editPhoto, ...diff !== 0 ? { lastActive: todayISO() } : {} });
      setEditP(false);
      showToast("档案已更新");
    } finally {
      setBusy(false);
    }
  };
  const handleDelete = (sid, sname) => {
    confirm(`永久删除 "${sname}" 及其排课记录。历史日志将保留，但此操作不可逆。建议优先使用「归档」。`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        const ns = db.students.filter((s) => s.id !== sid);
        const nr = { ...db.rosters };
        Object.keys(nr).forEach((d) => {
          nr[d] = nr[d].filter((id) => id !== sid);
        });
        await save({ ...db, students: ns, rosters: nr, logs: [mkLog(sname, "彻底删除档案", "0", "管理员移除", 0, { studentId: sid }), ...db.logs] });
        setSelS(null);
        setEditP(false);
        showToast(`${sname} 已移除`, "warn");
      } finally {
        setBusy(false);
      }
    }, { danger: true, confirmText: "永久删除" });
  };
  const portfolioDoUpload = async (file, note, date) => {
    if (!selS) return;
    setPortBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("studentId", String(selS.id));
      fd.append("note", note || "");
      fd.append("date", date || todayISO());
      const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/upload`, {
        method: "POST",
        credentials: "include",
        body: fd
      });
      if (r.status === 401) {
        showToast("登录已过期", "error");
        return;
      }
      if (!r.ok) {
        showToast("上传失败，请重试", "error");
        return;
      }
      const res = await r.json();
      const newPort = [res.item, ...selS.portfolio || []];
      setSelS((p) => ({ ...p, portfolio: newPort }));
      setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS.id ? { ...s, portfolio: newPort } : s) }));
      showToast("🎨 作品已上传", "success");
      if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
      setPortUpload(false);
      setPortUpFile(null);
    } catch (e) {
      showToast("上传失败", "error");
    } finally {
      setPortBusy(false);
    }
  };
  const portfolioDoDelete = async (pid) => {
    if (!selS) return;
    confirm(`确认删除这张作品照片？此操作不可恢复。`, async () => {
      const sid = String(selS.id);
      try {
        const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(pid)}`, {
          method: "DELETE",
          credentials: "include"
        });
        if (r.status === 401) {
          showToast("登录已过期，请重新登录", "error");
          return;
        }
        if (!r.ok) {
          showToast("删除失败", "error");
          return;
        }
        const newPort = (selS.portfolio || []).filter((i) => String(i.id) !== String(pid));
        setSelS((p) => ({ ...p, portfolio: newPort }));
        setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS.id ? { ...s, portfolio: newPort } : s) }));
        if (portLB) {
          if (newPort.length === 0) setPortLB(null);
          else setPortLB((p) => ({ ...p, items: newPort, idx: Math.max(0, Math.min(p.idx, newPort.length - 1)) }));
        }
        showToast("已删除", "warn");
      } catch (e) {
        showToast("删除失败", "error");
      }
    }, { danger: true, confirmText: "删除" });
  };
  const portfolioDoUpdateNote = async () => {
    if (!portEdit) return;
    const { sid, item, note, date } = portEdit;
    try {
      const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(item.id)}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note, date })
      });
      if (r.status === 401) {
        showToast("登录已过期，请重新登录", "error");
        return;
      }
      if (!r.ok) {
        showToast("更新失败", "error");
        return;
      }
      const newPort = (selS?.portfolio || []).map((i) => String(i.id) === String(item.id) ? { ...i, note, date } : i);
      setSelS((p) => p ? { ...p, portfolio: newPort } : p);
      setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS?.id ? { ...s, portfolio: newPort } : s) }));
      setPortLB((p) => p ? { ...p, items: newPort } : null);
      setPortEdit(null);
      showToast("✅ 已更新", "success");
    } catch (e) {
      showToast("更新失败", "error");
    }
  };
  const addToRoster = async () => {
    if (!rPick || busy) return;
    setBusy(true);
    try {
      const cur = db.rosters[rDate] || [];
      if (!cur.includes(rPick)) await save({ ...db, rosters: { ...db.rosters, [rDate]: [...cur, rPick] } });
      setRPick(null);
    } finally {
      setBusy(false);
    }
  };
  const removeFromRoster = async (sid) => {
    if (busy) return;
    setBusy(true);
    try {
      await save({ ...db, rosters: { ...db.rosters, [rDate]: (db.rosters[rDate] || []).filter((id) => id !== sid) } });
    } finally {
      setBusy(false);
    }
  };
  const approveStudent = async (pid) => {
    const pen = (db.pending || []).find((p) => p.id === pid);
    if (!pen) return;
    if (busy) return;
    const credits = parseInt(approveCredits[pid] || "0", 10);
    const fn = pen.firstName || "", ln = pen.lastName || "";
    const fullName = ln ? `${fn} ${ln}` : fn;
    const doApprove = async () => {
      setBusy(true);
      try {
        if (TENANT_SLUG) {
          const res = await v1Api(`/registrations/${pid}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "approved" })
          });
          const newSid = res.student_id || res.registration && res.registration.student_id;
          if (credits > 0 && newSid) {
            await v1Api(`/students/${newSid}/credit-transactions`, {
              method: "POST",
              body: JSON.stringify({ transactionType: "migration", amount: credits, note: "注册审批初始课时" })
            });
          }
          await load();
          showToast(`${fullName} 已批准建档，家长将收到确认邮件`);
        } else {
          const ns = {
            id: Date.now(),
            firstName: fn,
            lastName: ln,
            name: fullName,
            mobile: pen.mobile || "",
            wechat: pen.wechat || "",
            email: pen.email || "",
            photo: pen.photo || "",
            preferences: pen.preferences || {},
            ...legacyPreferenceValues(pen.preferences || {}, null, pen),
            birthday: pen.birthday || "",
            balance: credits,
            remark: pen.message || "",
            lastActive: todayISO(),
            archived: false
          };
          const newPending = (db.pending || []).filter((p) => p.id !== pid);
          await save({
            ...db,
            students: [ns, ...db.students],
            pending: newPending,
            logs: [mkLog(fullName, "批准注册", `+${credits}`, `来自注册门户，管理员审批`, 0, { studentId: ns.id }), ...db.logs]
          });
          showToast(`${fullName} 已批准建档`);
        }
        setApproveCredits((p) => {
          const n = { ...p };
          delete n[pid];
          return n;
        });
      } catch (e) {
        showToast(`批准失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    if (db.students.some((s) => s.name.toLowerCase() === fullName.toLowerCase())) {
      confirm(`已存在同名学员 "${fullName}"，仍要继续建档？`, doApprove, { confirmText: "继续建档" });
    } else {
      doApprove();
    }
  };
  const rejectStudent = (pid) => {
    const pen = (db.pending || []).find((p) => p.id === pid);
    if (!pen) return;
    const name = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
    confirm(`拒绝 "${name}" 的注册申请？${TENANT_SLUG ? "（家长将收到通知邮件）" : "并删除该记录？"}`, async () => {
      if (busy) return;
      setBusy(true);
      try {
        if (TENANT_SLUG) {
          const note = (window.prompt("拒绝原因（将随通知邮件发送给家长，可留空）") || "").trim();
          await v1Api(`/registrations/${pid}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "rejected", reviewNote: note || "管理员拒绝注册申请" })
          });
          await load();
        } else {
          const newPending = (db.pending || []).filter((p) => p.id !== pid);
          await save({
            ...db,
            pending: newPending,
            logs: [mkLog(name, "拒绝注册", "0", "管理员拒绝注册申请"), ...db.logs]
          });
        }
        setApproveCredits((p) => {
          const n = { ...p };
          delete n[pid];
          return n;
        });
        showToast(`${name} 的申请已拒绝`, "warn");
      } catch (e) {
        showToast(`操作失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    }, { danger: true, confirmText: "确认拒绝" });
  };
  const dlCSV = (filename, rows) => {
    const bom = "\uFEFF";
    const csv = rows.map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([bom + csv], { type: "text/csv;charset=utf-8" }));
    a.download = filename;
    a.click();
  };
  const exportStudentsCSV = () => {
    const hdr = ["Full Name", "First Name", "Last Name", "Phone", "WeChat", "Email", "Birthday", "Balance", "Last Active", "Art Style", "Fav Artist", "Experience", "Goals", "Remark"];
    const rows = sortedFiltered.map((s) => [s.name, s.firstName, s.lastName, s.mobile, s.wechat, s.email, s.birthday ? fmtDate(s.birthday) : "", s.balance, fmtDate(s.lastActive), s.artStyle, s.favArtist, s.experience, s.goals, s.remark]);
    dlCSV(`Studio_Students_${todayISO()}.csv`, [hdr, ...rows]);
  };
  const exportRevenueCSV = () => {
    const hdr = ["Period", "Revenue (AUD)", "Check-ins", "Top-ups"];
    const rows = statsData.rows.map((r) => [sPeriod === "yearly" ? `${r.key}年` : fmtMK(r.key), r.revenue.toFixed(2), r.checkins, r.topups]);
    dlCSV(`Studio_Revenue_${todayISO()}.csv`, [hdr, ...rows]);
  };
  const exportLogsCSV = () => {
    const hdr = ["Date", "Student", "Action", "Change", "Fee (AUD)", "Pay Method", "Note"];
    const rows = filteredLogs.map((l) => [l.date, l.studentName, l.action, l.change, l.feePaid || 0, l.payMethod || "", l.note || ""]);
    dlCSV(`Studio_Logs_${todayISO()}.csv`, [hdr, ...rows]);
  };
  const changePin = () => {
    if (!/^\d{4}$/.test(newPin1)) {
      showToast("PIN 必须是 4 位数字", "error");
      return;
    }
    if (newPin1 !== newPin2) {
      showToast("两次输入不一致", "error");
      return;
    }
    savePin(newPin1);
    setNewPin1("");
    setNewPin2("");
    setShowSettings(false);
    showToast("PIN 码已更新");
  };
  const lockScreen = () => {
    if (!pinEnabled) {
      setShowSettings(false);
      confirm("确认退出登录？", doLogout, { confirmText: "退出登录" });
      return;
    }
    clearSess();
    setPinOK(false);
    setShowSettings(false);
  };
  if (!loggedIn) return /* @__PURE__ */ React.createElement(LoginScreen, { onLogin: () => setLoggedIn(true) });
  if (pinEnabled && !pinOK) return /* @__PURE__ */ React.createElement(PINScreen, { onUnlock: () => {
    markSess();
    setPinOK(true);
  } });
  if (!conn) return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gray-900 text-white p-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full" }, connErr ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "text-5xl mb-3" }, "⚠️"), /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-3" }, "连接失败"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-3 leading-relaxed" }, "请确认终端正在运行 ", /* @__PURE__ */ React.createElement("code", { className: "text-indigo-400 bg-gray-900 px-1 rounded" }, "python3 server.py")), /* @__PURE__ */ React.createElement("p", { className: "text-red-400 text-xs font-mono bg-gray-900 p-2 rounded mb-4" }, connErr), /* @__PURE__ */ React.createElement("button", { onClick: load, className: "bg-indigo-600 active:bg-indigo-700 px-8 py-3 rounded-xl font-bold w-full" }, "重新连接")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("span", { className: "sp mb-3 w-10 h-10 border-4 block mx-auto" }), /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mt-3" }, "连接中..."))));
  const pendingCount = (db.pending || []).length;
  const NAV = [
    { k: "dashboard", i: "📊", l: "工作台", s: "工作台" },
    { k: "roster", i: "📅", l: "每日排课", s: "排课" },
    { k: "students", i: "👥", l: "客户档案", s: "档案" },
    { k: "pending", i: "📋", l: "待审核", s: "审核", badge: pendingCount },
    { k: "topup", i: "💰", l: "充值结算", s: "充值" },
    { k: "logs", i: "📜", l: "操作日志", s: "日志" },
    { k: "stats", i: "📈", l: "商业洞察", s: "统计" }
  ];
  return /* @__PURE__ */ React.createElement("div", { className: "flex h-screen bg-gray-50" }, toast && /* @__PURE__ */ React.createElement(Toast, { key: toast.key, msg: toast.msg, type: toast.type, action: toast.action, onDone: () => setToast(null) }), /* @__PURE__ */ React.createElement(ConfirmDialog, { dialog: confirmDialog, onClose: () => setConfirmDialog(null) }), portLB && portLB.items.length > 0 && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "fixed inset-0 bg-black/95 z-[90] flex flex-col",
      style: { paddingBottom: "env(safe-area-inset-bottom,0px)", paddingTop: "env(safe-area-inset-top,0px)" },
      onTouchStart: (e) => {
        lbTouchX.current = e.touches[0].clientX;
        lbTouchX._y = e.touches[0].clientY;
      },
      onTouchEnd: (e) => {
        const dx = e.changedTouches[0].clientX - lbTouchX.current;
        const dy = e.changedTouches[0].clientY - (lbTouchX._y || 0);
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) setPortLB((p) => {
          if (!p) return p;
          const next = dx < 0 ? Math.min(p.items.length - 1, p.idx + 1) : Math.max(0, p.idx - 1);
          return { ...p, idx: next };
        });
      }
    },
    /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "flex justify-between items-center px-4 py-3 flex-shrink-0",
        style: { paddingTop: "max(12px,env(safe-area-inset-top,12px))" }
      },
      /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-white font-bold text-sm truncate" }, fmtDate(portLB.items[portLB.idx]?.date)), portLB.items[portLB.idx]?.note && /* @__PURE__ */ React.createElement("p", { className: "text-white/60 text-xs truncate" }, portLB.items[portLB.idx].note)),
      /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-shrink-0" }, /* @__PURE__ */ React.createElement("span", { className: "text-white/40 text-xs" }, portLB.idx + 1, " / ", portLB.items.length), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            const cur = portLB.items[portLB.idx];
            if (cur && selS) setPortEdit({ sid: String(selS.id), item: cur, note: cur.note || "", date: cur.date || todayISO() });
          },
          className: "text-white/80 active:text-white w-9 h-9 flex items-center justify-center text-base"
        },
        "✏️"
      ), /* @__PURE__ */ React.createElement("button", { onClick: () => setPortLB(null), className: "text-white text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×"))
    ),
    /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "flex-1 flex items-center justify-center px-2 min-h-0",
        onClick: () => setPortLB(null)
      },
      /* @__PURE__ */ React.createElement(
        "img",
        {
          src: portfolioImgSrc(selS?.id, portLB.items[portLB.idx]),
          className: "max-w-full max-h-full object-contain rounded-xl shadow-2xl",
          onClick: (e) => e.stopPropagation(),
          onError: (e) => {
            e.target.style.display = "none";
            e.target.nextSibling && (e.target.nextSibling.style.display = "flex");
          }
        }
      ),
      /* @__PURE__ */ React.createElement("div", { style: { display: "none" }, className: "flex-col items-center justify-center gap-2 text-white/50" }, /* @__PURE__ */ React.createElement("span", { className: "text-4xl" }, "🖼"), /* @__PURE__ */ React.createElement("span", { className: "text-sm" }, "图片加载失败"))
    ),
    /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center px-4 py-3 flex-shrink-0" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setPortLB((p) => ({ ...p, idx: Math.max(0, p.idx - 1) })),
        disabled: portLB.idx === 0,
        className: "py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]"
      },
      "← 上一张"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => portfolioDoDelete(String(portLB.items[portLB.idx]?.id)),
        className: "py-2.5 px-4 bg-red-500/80 active:bg-red-600/80 text-white rounded-xl text-sm min-h-[44px]"
      },
      "🗑"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setPortLB((p) => ({ ...p, idx: Math.min(p.items.length - 1, p.idx + 1) })),
        disabled: portLB.idx === portLB.items.length - 1,
        className: "py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]"
      },
      "下一张 →"
    ))
  ), portUpload && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "fixed inset-0 bg-black/70 z-[85] flex items-end sm:items-center justify-center sm:p-4",
      onClick: (e) => {
        if (e.target === e.currentTarget) {
          if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
          setPortUpload(false);
          setPortUpFile(null);
        }
      }
    },
    /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "bg-white w-full sm:rounded-3xl sm:max-w-md shadow-2xl overflow-hidden anim",
        style: { paddingBottom: "env(safe-area-inset-bottom,0px)" }
      },
      /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center px-5 pt-5 pb-3" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 text-lg" }, "🎨 上传作品"), /* @__PURE__ */ React.createElement("button", { onClick: () => {
        if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
        setPortUpload(false);
        setPortUpFile(null);
      }, className: "text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×")),
      /* @__PURE__ */ React.createElement("div", { className: "px-5 pb-5" }, !portUpFile ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-purple-300 rounded-2xl cursor-pointer active:bg-purple-50 hover:bg-purple-50 transition-colors" }, /* @__PURE__ */ React.createElement("span", { className: "text-3xl" }, "📷"), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-purple-700" }, "拍照"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "file",
          accept: "image/*",
          capture: "environment",
          className: "hidden",
          onChange: (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.size > 10 * 1024 * 1024) {
              showToast("文件太大，请先压缩", "error");
              return;
            }
            setPortUpFile({ file, dataUrl: URL.createObjectURL(file), note: "", date: todayISO() });
          }
        }
      )), /* @__PURE__ */ React.createElement("label", { className: "flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-indigo-300 rounded-2xl cursor-pointer active:bg-indigo-50 hover:bg-indigo-50 transition-colors" }, /* @__PURE__ */ React.createElement("span", { className: "text-3xl" }, "🖼"), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-indigo-700" }, "从相册"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "file",
          accept: "image/*",
          className: "hidden",
          onChange: (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.size > 10 * 1024 * 1024) {
              showToast("文件太大，请先压缩", "error");
              return;
            }
            setPortUpFile({ file, dataUrl: URL.createObjectURL(file), note: "", date: todayISO() });
          }
        }
      ))), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 text-center mt-3" }, "支持 JPG/PNG，最大 10 MB")) : /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("img", { src: portUpFile.dataUrl, className: "w-full h-52 object-cover rounded-2xl mb-4 bg-gray-100" }), /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1.5 block" }, "📅 作品日期"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "date",
          value: portUpFile.date,
          onChange: (e) => setPortUpFile((p) => ({ ...p, date: e.target.value })),
          className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
        }
      )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1.5 block" }, "💬 备注 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "text",
          value: portUpFile.note,
          onChange: (e) => setPortUpFile((p) => ({ ...p, note: e.target.value })),
          placeholder: "如：水彩练习 第1期",
          maxLength: 50,
          className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
        }
      ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 mt-4" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
            setPortUpFile(null);
          },
          className: "flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]"
        },
        "重新选择"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => portfolioDoUpload(portUpFile.file, portUpFile.note, portUpFile.date),
          disabled: portBusy,
          className: "flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold disabled:opacity-50 min-h-[50px]"
        },
        portBusy ? "上传中..." : "✅ 确认上传"
      ))))
    )
  ), portEdit && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "fixed inset-0 bg-black/60 z-[85] flex items-end sm:items-center justify-center sm:p-4",
      onClick: (e) => {
        if (e.target === e.currentTarget) setPortEdit(null);
      }
    },
    /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "bg-white w-full sm:rounded-3xl sm:max-w-sm rounded-t-3xl p-5 shadow-2xl anim",
        style: { paddingBottom: "max(20px,env(safe-area-inset-bottom,20px))" }
      },
      /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center mb-4" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 text-lg" }, "✏️ 编辑作品信息"), /* @__PURE__ */ React.createElement("button", { onClick: () => setPortEdit(null), className: "text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×")),
      /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1.5 block" }, "📅 作品日期"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "date",
          value: portEdit.date,
          onChange: (e) => setPortEdit((p) => ({ ...p, date: e.target.value })),
          className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
        }
      )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1.5 block" }, "💬 备注"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "text",
          value: portEdit.note,
          onChange: (e) => setPortEdit((p) => ({ ...p, note: e.target.value })),
          maxLength: 50,
          className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
        }
      ))),
      /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 mt-4" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setPortEdit(null),
          className: "flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]"
        },
        "取消"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: portfolioDoUpdateNote,
          className: "flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold min-h-[50px]"
        },
        "保存"
      ))
    )
  ), gOpen && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "fixed inset-0 bg-black/60 z-[80] flex items-start justify-center pt-[10vh] px-4 backdrop-blur-sm",
      onClick: () => {
        setGOpen(false);
        setGQ("");
      }
    },
    /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden anim", onClick: (e) => e.stopPropagation() }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 px-4 py-3 border-b" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xl" }, "🔍"), /* @__PURE__ */ React.createElement(
      "input",
      {
        autoFocus: true,
        type: "text",
        placeholder: "搜索学员姓名、电话、微信号...",
        value: gQ,
        onChange: (e) => setGQ(e.target.value),
        onKeyDown: (e) => {
          if (e.key === "Escape") {
            setGOpen(false);
            setGQ("");
          }
        },
        className: "flex-1 outline-none text-gray-800 text-sm bg-transparent placeholder-gray-400"
      }
    ), /* @__PURE__ */ React.createElement("kbd", { className: "hidden sm:inline text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded font-mono" }, "ESC")), /* @__PURE__ */ React.createElement("div", { className: "max-h-80 overflow-y-auto sl" }, !gQ.trim() && /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-8" }, "输入姓名、手机号或微信号搜索"), gQ.trim() && !gResults.length && /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-8" }, "未找到匹配学员"), gResults.map((s) => {
      const tag = getTag(s);
      return /* @__PURE__ */ React.createElement(
        "button",
        {
          key: s.id,
          className: "w-full flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 active:bg-indigo-100 border-b border-gray-50 text-left min-h-[56px]",
          onClick: () => {
            setTab("students");
            setSelS(s);
            setEditP(false);
            setGOpen(false);
            setGQ("");
          }
        },
        /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }),
        /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm truncate" }, s.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, s.mobile || "—", s.wechat ? ` · 💬 ${s.wechat}` : "")),
        /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-shrink-0" }, tag && /* @__PURE__ */ React.createElement("span", { className: `text-xs px-2 py-0.5 rounded-full font-bold ${tag.cls}` }, tag.icon, " ", tag.label), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }))
      );
    })), /* @__PURE__ */ React.createElement("div", { className: "px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t" }, "点击学员查看档案 · ", /* @__PURE__ */ React.createElement("kbd", { className: "bg-gray-200 px-1 rounded font-mono" }, "⌘K"), " 打开 / 关闭"))
  ), showSettings && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4",
      onClick: () => setShowSettings(false),
      style: { paddingTop: "max(16px, env(safe-area-inset-top, 16px))", paddingBottom: "max(16px, env(safe-area-inset-bottom, 16px))" }
    },
    /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl p-6 w-full max-w-xs shadow-2xl anim overflow-y-auto modal-scroll", style: { maxHeight: "90dvh" }, onClick: (e) => e.stopPropagation() }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center mb-5" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800" }, "⚙️ 系统设置"), /* @__PURE__ */ React.createElement("button", { onClick: () => setShowSettings(false), className: "text-gray-400 active:text-gray-700 text-xl p-1" }, "×")), TENANT_SLUG && /* @__PURE__ */ React.createElement(
      "a",
      {
        href: `/${TENANT_SLUG}/studio-admin`,
        target: "_blank",
        rel: "noopener",
        className: "block bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3 text-sm font-bold text-indigo-700 active:bg-indigo-100"
      },
      "🎨 品牌与网站设置（Studio Admin）→",
      /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-normal text-indigo-400 mt-0.5" }, "Logo、配色、注册表单、数据导出、作品分享链接")
    ), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "修改登录密码"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "password",
        placeholder: "当前密码",
        value: pwOld,
        onChange: (e) => setPwOld(e.target.value),
        className: "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"
      }
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "password",
        placeholder: "新密码（≥8位）",
        value: pwNew1,
        onChange: (e) => setPwNew1(e.target.value),
        className: "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"
      }
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "password",
        placeholder: "再次确认新密码",
        value: pwNew2,
        onChange: (e) => setPwNew2(e.target.value),
        className: "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"
      }
    ), pwMsg && /* @__PURE__ */ React.createElement("p", { className: `text-xs font-medium ${pwMsg.startsWith("✅") ? "text-green-600" : "text-red-500"}` }, pwMsg), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: changeWebPw,
        disabled: pwBusy,
        className: "w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
      },
      pwBusy ? "更新中..." : "更新密码"
    )), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-600" }, "启用屏幕锁（PIN）"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "关闭时「锁定」= 退出登录")), /* @__PURE__ */ React.createElement("button", { onClick: () => togglePin(!pinEnabled), className: `relative inline-flex h-6 w-11 items-center rounded-full transition ${pinEnabled ? "bg-indigo-600" : "bg-gray-300"}` }, /* @__PURE__ */ React.createElement("span", { className: `inline-block h-4 w-4 transform rounded-full bg-white transition ${pinEnabled ? "translate-x-6" : "translate-x-1"}` })))), pinEnabled && /* @__PURE__ */ React.createElement("div", { className: "space-y-3 mt-4 pt-4 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "修改 PIN 码"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "password",
        inputMode: "numeric",
        maxLength: 4,
        placeholder: "新 PIN（4位数字）",
        value: newPin1,
        onChange: (e) => setNewPin1(e.target.value.replace(/\D/, "").slice(0, 4)),
        className: "w-full p-3 border border-gray-300 rounded-xl outline-none tracking-widest text-center text-2xl focus:ring-2 focus:ring-indigo-500"
      }
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "password",
        inputMode: "numeric",
        maxLength: 4,
        placeholder: "再次确认",
        value: newPin2,
        onChange: (e) => setNewPin2(e.target.value.replace(/\D/, "").slice(0, 4)),
        className: "w-full p-3 border border-gray-300 rounded-xl outline-none tracking-widest text-center text-2xl focus:ring-2 focus:ring-indigo-500"
      }
    ), /* @__PURE__ */ React.createElement("button", { onClick: changePin, className: "w-full bg-indigo-600 active:bg-indigo-700 text-white py-3 rounded-xl font-bold text-sm" }, "更新 PIN")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "未到访预警天数"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, [60, 90, 120, 180].map((d) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: d,
        onClick: () => saveInactiveDays(d),
        className: `flex-1 py-2 rounded-xl text-xs font-bold border ${inactiveDays === d ? "bg-indigo-600 text-white border-indigo-600" : "bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100"}`
      },
      d,
      "天"
    )))), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "充值套餐管理"), (db.packages || []).map((pkg) => /* @__PURE__ */ React.createElement("div", { key: pkg.id, className: "flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-700 truncate" }, pkg.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, pkg.credits, "课时 · $", pkg.price)), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setPkgEditId(pkg.id);
          setPkgName(pkg.name);
          setPkgCredits(String(pkg.credits));
          setPkgPrice(String(pkg.price));
        },
        className: "text-xs text-indigo-600 font-bold px-2 py-1 active:text-indigo-800 flex-shrink-0"
      },
      "编辑"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          if ((db.packages || []).length <= 1) {
            showToast("至少保留一个套餐", "warn");
            return;
          }
          confirm(`删除套餐「${pkg.name}」？`, () => {
            const nd = { ...db, packages: (db.packages || []).filter((p) => p.id !== pkg.id) };
            save(nd);
            showToast("套餐已删除");
          }, { danger: true, confirmText: "删除" });
        },
        className: "text-xs text-red-500 font-bold px-2 py-1 active:text-red-700 flex-shrink-0"
      },
      "×"
    ))), pkgEditId === null ? /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setPkgEditId(0);
          setPkgName("");
          setPkgCredits("");
          setPkgPrice("");
        },
        className: "w-full border border-dashed border-indigo-300 text-indigo-600 rounded-xl py-2 text-xs font-bold active:bg-indigo-50"
      },
      "+ 添加套餐"
    ) : /* @__PURE__ */ React.createElement("div", { className: "space-y-2 bg-indigo-50 border border-indigo-200 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-indigo-700" }, pkgEditId === 0 ? "添加套餐" : "编辑套餐"), /* @__PURE__ */ React.createElement(
      "input",
      {
        placeholder: "套餐名称",
        value: pkgName,
        onChange: (e) => setPkgName(e.target.value),
        className: "w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        placeholder: "课时数",
        min: "1",
        value: pkgCredits,
        onChange: (e) => setPkgCredits(e.target.value),
        className: "w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"
      }
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        placeholder: "价格 $",
        min: "0",
        value: pkgPrice,
        onChange: (e) => setPkgPrice(e.target.value),
        className: "w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setPkgEditId(null);
          setPkgName("");
          setPkgCredits("");
          setPkgPrice("");
        },
        className: "flex-1 py-2 border border-gray-300 rounded-xl text-xs font-bold text-gray-600 active:bg-gray-100"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement("button", { onClick: () => {
      if (!pkgName.trim() || !pkgCredits || !pkgPrice) {
        showToast("请填写完整", "warn");
        return;
      }
      const cr = parseInt(pkgCredits, 10), pr = parseFloat(pkgPrice);
      if (isNaN(cr) || cr < 1 || isNaN(pr) || pr < 0) {
        showToast("课时数/价格无效", "warn");
        return;
      }
      let newPkgs;
      if (pkgEditId === 0) {
        const newId = Date.now();
        newPkgs = [...db.packages || [], { id: newId, name: pkgName.trim(), credits: cr, price: pr }];
      } else {
        newPkgs = (db.packages || []).map((p) => p.id === pkgEditId ? { ...p, name: pkgName.trim(), credits: cr, price: pr } : p);
      }
      save({ ...db, packages: newPkgs });
      setPkgEditId(null);
      setPkgName("");
      setPkgCredits("");
      setPkgPrice("");
      showToast(pkgEditId === 0 ? "套餐已添加" : "套餐已更新");
    }, className: "flex-1 py-2 bg-indigo-600 active:bg-indigo-700 text-white rounded-xl text-xs font-bold" }, "保存")))), (() => {
      const cutoffStr = (() => {
        const d = /* @__PURE__ */ new Date();
        d.setDate(d.getDate() - 90);
        return d.toISOString().slice(0, 10);
      })();
      const oldKeys = Object.keys(db.rosters || {}).filter((d) => d < cutoffStr);
      const cleanRosters = () => {
        if (!oldKeys.length) {
          showToast("没有需要清理的旧排课");
          return;
        }
        confirm(`清理 90 天前的排课记录（${oldKeys.length} 条）？
此操作不影响任何统计数据。`, () => {
          const nd = { ...db, rosters: { ...db.rosters } };
          oldKeys.forEach((k) => delete nd.rosters[k]);
          save(nd);
          showToast(`已清理 ${oldKeys.length} 条旧排课`);
        }, { confirmText: "清理" });
      };
      return /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "排课数据清理"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 flex items-center gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-500 flex-1" }, "90天前旧排课"), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold ${oldKeys.length > 0 ? "text-amber-600" : "text-green-600"}` }, oldKeys.length, " 条")), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: cleanRosters,
          disabled: oldKeys.length === 0,
          className: "w-full bg-amber-50 active:bg-amber-100 disabled:opacity-40 text-amber-700 border border-amber-200 py-2.5 rounded-xl font-bold text-sm"
        },
        "🧹 清理旧排课"
      ));
    })(), /* @__PURE__ */ React.createElement(
      MaintSection,
      {
        renewTh,
        saveRenewTh,
        onRestored: () => {
          setShowSettings(false);
          load();
        }
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "学员注册页面"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-500 flex-1 font-mono truncate" }, window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => copyText(window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`, "链接已复制"),
        className: "text-xs text-indigo-600 font-bold active:text-indigo-800 flex-shrink-0"
      },
      "复制"
    ))), /* @__PURE__ */ React.createElement("div", { className: "mt-3 pt-3 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("button", { onClick: lockScreen, className: "w-full bg-gray-100 active:bg-gray-200 text-gray-700 py-3 rounded-xl font-bold text-sm" }, pinEnabled ? "🔒 锁定屏幕" : "🔓 退出登录"), /* @__PURE__ */ React.createElement("div", { className: "md:hidden space-y-2 pt-2 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold text-gray-400 uppercase tracking-wide pb-0.5" }, "快捷操作"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          load();
          setShowSettings(false);
        },
        disabled: busy,
        className: "w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"
      },
      "🔄 刷新数据"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          exportDB();
          setShowSettings(false);
        },
        className: "w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"
      },
      "⬇️ 备份导出"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setShowSettings(false);
          confirm("确认退出登录？下次进入需重新输入密码。", doLogout, { confirmText: "退出登录" });
        },
        className: "w-full bg-red-50 active:bg-red-100 text-red-600 border border-red-200 py-3 rounded-xl font-bold text-sm"
      },
      "🔓 退出登录"
    ))))
  ), /* @__PURE__ */ React.createElement("div", { className: "md:hidden mobile-top-bar fixed top-0 left-0 right-0 z-40 bg-indigo-900 text-white flex items-center px-3 gap-2.5 shadow-lg" }, /* @__PURE__ */ React.createElement("img", { src: tenantLogoUrl, alt: tenantDisplayName, className: "h-8 w-auto max-w-[96px] object-contain flex-shrink-0" }), /* @__PURE__ */ React.createElement("span", { className: "font-bold text-base flex-1 truncate" }, tenantDisplayName, " CMS"), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => {
        setGOpen(true);
        setGQ("");
      },
      "aria-label": "搜索",
      className: "w-9 h-9 flex items-center justify-center rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-200 text-base flex-shrink-0"
    },
    "🔍"
  ), /* @__PURE__ */ React.createElement(
    "button",
    {
      onClick: () => setShowSettings(true),
      "aria-label": "设置",
      className: "w-9 h-9 flex items-center justify-center rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-200 text-base flex-shrink-0"
    },
    "⚙️"
  )), /* @__PURE__ */ React.createElement(
    "aside",
    {
      className: "hidden md:flex w-56 bg-indigo-900 text-white flex-col shadow-xl flex-shrink-0",
      style: { paddingTop: "env(safe-area-inset-top, 0px)" }
    },
    /* @__PURE__ */ React.createElement("div", { className: "p-4 border-b border-indigo-800 flex items-center gap-2.5" }, /* @__PURE__ */ React.createElement("img", { src: tenantLogoUrl, alt: tenantDisplayName, className: "h-9 w-auto max-w-[96px] object-contain flex-shrink-0" }), /* @__PURE__ */ React.createElement("h1", { className: "hidden md:block text-base font-bold tracking-wide flex-1 truncate" }, tenantDisplayName), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setGOpen(true);
          setGQ("");
        },
        title: "全局搜索 ⌘K",
        className: "hidden md:flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-300 hover:text-white text-base flex-shrink-0"
      },
      "🔍"
    )),
    /* @__PURE__ */ React.createElement("nav", { className: "flex-1 px-2 py-4 space-y-0.5 overflow-y-auto" }, NAV.map(({ k, i, l, badge }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: k,
        onClick: () => setTab(k),
        className: `w-full text-left px-2 py-3 rounded-xl transition flex items-center gap-2 text-sm min-h-[44px] ${tab === k ? "bg-indigo-700 font-bold" : "active:bg-indigo-800 text-indigo-200"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-base w-5 text-center flex-shrink-0" }, i),
      /* @__PURE__ */ React.createElement("span", null, l),
      k === "dashboard" && analytics.lowBalance.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "ml-auto bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full" }, analytics.lowBalance.length),
      badge > 0 && /* @__PURE__ */ React.createElement("span", { className: "ml-auto bg-amber-400 text-white text-xs font-bold px-1.5 py-0.5 rounded-full" }, badge)
    ))),
    /* @__PURE__ */ React.createElement("div", { className: "p-3 border-t border-indigo-800 space-y-1.5", style: { paddingBottom: "calc(env(safe-area-inset-bottom,0px) + 12px)" } }, /* @__PURE__ */ React.createElement("div", { className: "text-xs text-green-400 text-center bg-indigo-950 rounded-lg p-1.5 border border-indigo-800" }, "🟢 已连接"), db.logs.length > 1e3 && /* @__PURE__ */ React.createElement("div", { className: "text-xs text-amber-400 text-center bg-indigo-950 rounded-lg p-1.5 border border-amber-800/40" }, "⚠️ 日志 ", db.logs.length, " 条"), /* @__PURE__ */ React.createElement("button", { onClick: exportDB, className: "w-full bg-indigo-700 active:bg-indigo-600 p-2.5 rounded-xl text-xs font-bold min-h-[40px]" }, "⬇️ 备份导出"), /* @__PURE__ */ React.createElement("button", { onClick: load, disabled: busy, className: "w-full bg-indigo-800 active:bg-indigo-700 p-2.5 rounded-xl text-xs font-bold min-h-[40px]" }, "🔄 刷新"), /* @__PURE__ */ React.createElement("button", { onClick: () => setShowSettings(true), className: "w-full bg-indigo-800 active:bg-indigo-700 p-2.5 rounded-xl text-xs font-bold min-h-[40px]" }, "⚙️ 设置"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => confirm("确认退出登录？下次进入需重新输入密码。", doLogout, { confirmText: "退出登录" }),
        className: "w-full bg-indigo-950 active:bg-red-900 p-2.5 rounded-xl text-xs font-bold min-h-[40px] text-indigo-300 active:text-white"
      },
      "🔓 退出登录"
    ))
  ), /* @__PURE__ */ React.createElement(
    "main",
    {
      className: "flex-1 overflow-y-auto p-4 md:pt-6 md:p-6 md:pb-0 sl mobile-main-top mobile-pb",
      style: {
        paddingTop: "calc(1.5rem + env(safe-area-inset-top, 0px))",
        paddingBottom: "env(safe-area-inset-bottom, 0px)"
      }
    },
    tab === "dashboard" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-5" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "📊 工作台"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, [
      { l: "客户总数", v: `${analytics.totalStudents} 人`, c: "text-gray-800", action: () => {
        setSortBy("date-desc");
        setFilterBy("all");
        setTab("students");
      } },
      { l: "全部剩余课时", v: `${analytics.totalBalance} 课时`, c: "text-indigo-600", action: () => {
        setSortBy("bal-desc");
        setFilterBy("active");
        setTab("students");
      } },
      { l: "今日排班", v: `${TENANT_SLUG ? todayEffectiveCount : analytics.todayRoster.length} 人`, c: "text-gray-700", action: () => setTab("roster") },
      { l: "历史总营收", v: `$${analytics.totalRevenue.toFixed(0)}`, c: "text-emerald-600", action: () => setTab("stats") }
    ].map(({ l, v, c, action }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: l,
        onClick: action,
        className: "bg-white p-4 rounded-2xl shadow-sm border border-indigo-100 text-left w-full active:bg-indigo-50 transition"
      },
      /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, l, " ", /* @__PURE__ */ React.createElement("span", { className: "text-indigo-400" }, "→")),
      /* @__PURE__ */ React.createElement("p", { className: `text-2xl font-bold ${c}` }, v)
    ))), TENANT_SLUG && bizStats && /* @__PURE__ */ React.createElement("details", { className: "bg-white rounded-2xl shadow-sm border border-emerald-100" }, /* @__PURE__ */ React.createElement("summary", { className: "cursor-pointer px-4 py-3 font-bold text-sm text-gray-800 select-none" }, "📈 经营真账（估算） ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-gray-400" }, "已上课 ", bizStats.attended_total, " 人次 · 加权均价 $", bizStats.avg_price, "/课时")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 px-4 pb-4" }, [
      ["已上课人次", `${bizStats.attended_total} 次`, `本月 ${bizStats.attended_month} 次`, "text-gray-800"],
      ["已赚收入(估)", `$${bizStats.earned_revenue}`, "人次 × 加权均价", "text-emerald-600"],
      ["预收未耗(负债)", `$${bizStats.prepaid_liability}`, "剩余课时 × 均价", "text-amber-600"],
      ["净现金收入", `$${bizStats.cash_net}`, "充值 − 退款", "text-indigo-600"]
    ].map(([l, v, sub, c]) => /* @__PURE__ */ React.createElement("div", { key: l, className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, l), /* @__PURE__ */ React.createElement("p", { className: `text-xl font-bold ${c}` }, v), /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-400 mt-0.5" }, sub))))), (() => {
      const todoClear = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 0 && s.lastActive);
      const todoLast = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 1);
      const todoRisk = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.name] || 0) === 0);
      const now = /* @__PURE__ */ new Date();
      now.setHours(0, 0, 0, 0);
      const weekEnd = new Date(now);
      weekEnd.setDate(weekEnd.getDate() + 7);
      const todoBdayWeek = db.students.filter((s) => {
        if (!s.birthday || s.archived) return false;
        const bd = new Date(now.getFullYear(), parseInt(s.birthday.slice(5, 7), 10) - 1, parseInt(s.birthday.slice(8, 10), 10));
        return bd >= now && bd <= weekEnd;
      });
      const todoBdayMonth = db.students.filter((s) => {
        if (!s.birthday || s.archived) return false;
        return s.birthday.slice(5, 7) === String(now.getMonth() + 1).padStart(2, "0") && !todoBdayWeek.includes(s);
      });
      const total = todoClear.length + todoLast.length + todoRisk.length + todoBdayWeek.length + todoBdayMonth.length;
      if (!total) return null;
      const names = (arr, max = 4) => arr.slice(0, max).map((s) => s.name).join("、") + (arr.length > max ? ` 等${arr.length}人` : "");
      return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 bg-gray-50 border-b flex items-center justify-between" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "⏰ 今日待办"), /* @__PURE__ */ React.createElement("span", { className: "bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full" }, total, " 项")), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, todoClear.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-red-700" }, "🚨 课时已清零 · ", todoClear.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoClear))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("zero");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-red-600 font-bold bg-red-50 active:bg-red-100 border border-red-200 px-3 py-1.5 rounded-xl min-h-[34px]"
        },
        "查看 →"
      )), todoLast.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-orange-700" }, "⚡ 最后 1 课时 · ", todoLast.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoLast))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("low");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-orange-600 font-bold bg-orange-50 active:bg-orange-100 border border-orange-200 px-3 py-1.5 rounded-xl min-h-[34px]"
        },
        "查看 →"
      )), todoRisk.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-amber-700" }, "⚠️ 流失风险 · ", todoRisk.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoRisk))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("tag-risk");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-amber-600 font-bold bg-amber-50 active:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-xl min-h-[34px]"
        },
        "查看 →"
      )), todoBdayWeek.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-pink-600" }, "🎂 本周生日 · ", todoBdayWeek.length, " 人"), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            const msg = todoBdayWeek.map((s) => `🎂 祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join("\n");
            copyText(msg, "祝福语已复制");
          },
          className: "flex-shrink-0 text-xs text-pink-600 font-bold bg-pink-50 active:bg-pink-100 border border-pink-200 px-3 py-1.5 rounded-xl min-h-[34px]"
        },
        "复制祝福 →"
      )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, todoBdayWeek.map((s) => /* @__PURE__ */ React.createElement("span", { key: s.id, className: "inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700" }, s.name, s.mobile && /* @__PURE__ */ React.createElement("a", { href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent("🎂 祝 " + s.name + " 生日快乐！愿新的一年里画艺大进，心想事成！")}`, className: "text-pink-400 ml-0.5 active:text-pink-600" }, "💬"))))), todoBdayMonth.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-pink-400" }, "🎈 本月生日 · ", todoBdayMonth.length, " 人"), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            const msg = todoBdayMonth.map((s) => `🎂 祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join("\n");
            copyText(msg, "祝福语已复制");
          },
          className: "flex-shrink-0 text-xs text-pink-400 font-bold bg-pink-50 active:bg-pink-100 border border-pink-100 px-3 py-1.5 rounded-xl min-h-[34px]"
        },
        "复制祝福 →"
      )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, todoBdayMonth.map((s) => /* @__PURE__ */ React.createElement("span", { key: s.id, className: "inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700" }, s.name, s.mobile && /* @__PURE__ */ React.createElement("a", { href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent("🎂 祝 " + s.name + " 生日快乐！愿新的一年里画艺大进，心想事成！")}`, className: "text-pink-400 ml-0.5 active:text-pink-600" }, "💬")))))));
    })(), (db.pending || []).length > 0 && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setTab("pending"),
        className: "w-full bg-amber-50 border border-amber-300 rounded-2xl p-4 text-left active:bg-amber-100 transition"
      },
      /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "text-2xl" }, "📋"), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-amber-800 text-sm" }, "有待审核的注册申请"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-amber-600 mt-0.5" }, (db.pending || []).length, " 位学员等待审核，点击前往处理"))), /* @__PURE__ */ React.createElement("span", { className: "bg-amber-500 text-white text-sm font-bold px-3 py-1 rounded-full" }, (db.pending || []).length))
    ), analytics.inactive.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-blue-50 border border-blue-200 rounded-2xl p-4" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-blue-800 mb-2 text-sm" }, "📅 长期未到访 — ", analytics.inactive.length, " 名学员有余额但超过 ", inactiveDays, " 天未上课"), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, analytics.inactive.slice(0, 12).map((s) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: s.id,
        onClick: () => {
          setTab("students");
          setSrch(s.name);
        },
        className: "px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200 active:bg-blue-200 min-h-[36px]"
      },
      s.name,
      " (",
      s.balance,
      "课 · ",
      daysSince(s.lastActive),
      "天前)"
    )))), analytics.lowBalance.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-amber-50 border border-amber-200 rounded-2xl p-4" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-amber-800 mb-2 text-sm" }, "⚡ 课时预警 — ", analytics.lowBalance.length, " 名学员余额 ≤ 2 课时"), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, analytics.lowBalance.map((s) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: s.id,
        onClick: () => {
          setTab("students");
          setSrch(s.name);
        },
        className: `px-3 py-1.5 rounded-lg text-xs font-bold border min-h-[36px] ${parseInt(s.balance, 10) === 0 ? "bg-red-100 text-red-700 border-red-200" : "bg-amber-100 text-amber-800 border-amber-200"}`
      },
      s.name,
      " (",
      s.balance,
      ")"
    )))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b px-4 py-3 flex justify-between items-center" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "最近操作"), /* @__PURE__ */ React.createElement("button", { onClick: () => setTab("logs"), className: "text-indigo-500 text-xs active:text-indigo-700" }, "全部 →")), analytics.recentGroups.length === 0 && /* @__PURE__ */ React.createElement("div", { className: "p-8 text-center text-gray-400 text-sm" }, "暂无记录"), analytics.recentGroups.map(({ date, logs }) => /* @__PURE__ */ React.createElement("div", { key: date }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-1.5 bg-gray-50 border-b border-t border-gray-100" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-gray-400" }, date)), logs.map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "px-4 py-2.5 flex justify-between items-center border-b border-gray-50 last:border-0" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-800 text-sm" }, l.studentName), /* @__PURE__ */ React.createElement("span", { className: "ml-2 text-gray-400 text-xs" }, l.action), l.payMethod && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-blue-400 text-xs" }, l.payMethod)), /* @__PURE__ */ React.createElement("span", { className: `font-bold text-sm ${String(l.change).startsWith("-") ? "text-orange-500" : l.change === "0" || l.change === 0 ? "text-gray-400" : "text-green-500"}` }, l.change))))))),
    tab === "roster" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "📅 每日排课"), upcomingBirthdays.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-gradient-to-r from-pink-50 to-rose-50 border border-pink-200 rounded-2xl p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-2 flex-wrap mb-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-rose-700" }, "🎂 近 14 天生日（", upcomingBirthdays.length, " 人）")), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, upcomingBirthdays.map(({ s, in: days, md, age }) => /* @__PURE__ */ React.createElement("button", { key: s.id, onClick: () => {
      const msg = `${s.name} 您好！🎉 Studio 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、画笔生花～ 🎨🎂`;
      copyText(msg, `已复制给 ${s.name} 的生日祝福`);
    }, className: "bg-white border border-pink-200 active:bg-pink-50 rounded-xl px-3 py-2 text-left" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-800" }, s.name, " ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-rose-400" }, days === 0 ? "🎉今天" : `${md} (${days}天后)`)), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "点击复制生日祝福话术"))))), TENANT_SLUG && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm text-gray-800" }, "📆 每周课表 ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-gray-400" }, "固定班次按周几自动排入当日名单")), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSchedEdit({ label: "", weekday: (/* @__PURE__ */ new Date()).getDay(), startTime: "16:00", durationMinutes: 60, capacity: 10, studentIds: [] }),
        className: "bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[36px]"
      },
      "➕ 新增班次"
    )), schedules.length === 0 && !schedEdit && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排班里。"), schedules.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, schedules.map((sc) => /* @__PURE__ */ React.createElement("div", { key: sc.id, className: `border rounded-xl px-3 py-2 ${sc.weekday === (/* @__PURE__ */ new Date(`${rDate}T12:00:00`)).getDay() ? "border-indigo-300 bg-indigo-50" : "border-gray-200 bg-gray-50"}` }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-800" }, WEEKDAYS[sc.weekday], " ", sc.startTime, " · ", sc.label || "未命名班次"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mt-1" }, /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-500" }, sc.students.length, "/", sc.capacity, " 人 · ", sc.durationMinutes, " 分钟"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSchedEdit({ id: sc.id, label: sc.label, weekday: sc.weekday, startTime: sc.startTime, durationMinutes: sc.durationMinutes, capacity: sc.capacity, studentIds: sc.students.map((st) => st.id) }),
        className: "text-[11px] font-bold text-indigo-600 active:text-indigo-800"
      },
      "编辑"
    ), /* @__PURE__ */ React.createElement("button", { onClick: () => deleteSchedule(sc), className: "text-[11px] font-bold text-red-500 active:text-red-700" }, "删除"))))), schedEdit && /* @__PURE__ */ React.createElement("div", { className: "border-t border-gray-100 pt-3 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 lg:grid-cols-5 gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "班次名称"), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: schedEdit.label,
        onChange: (e) => setSchedEdit((p) => ({ ...p, label: e.target.value })),
        placeholder: "如：周三素描班",
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "周几"), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: schedEdit.weekday,
        onChange: (e) => setSchedEdit((p) => ({ ...p, weekday: Number(e.target.value) })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500"
      },
      WEEKDAYS.map((w, i) => /* @__PURE__ */ React.createElement("option", { key: i, value: i }, w))
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "开始时间"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "time",
        value: schedEdit.startTime,
        onChange: (e) => setSchedEdit((p) => ({ ...p, startTime: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "容量"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "1",
        value: schedEdit.capacity,
        onChange: (e) => setSchedEdit((p) => ({ ...p, capacity: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "班次学员（", schedEdit.studentIds.length, " 人）"), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5 mb-2" }, schedEdit.studentIds.map((id) => {
      const s = db.students.find((x) => x.id === id);
      return s ? /* @__PURE__ */ React.createElement("span", { key: id, className: "inline-flex items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full px-2.5 py-1 text-xs font-bold" }, s.name, /* @__PURE__ */ React.createElement("button", { onClick: () => setSchedEdit((p) => ({ ...p, studentIds: p.studentIds.filter((x) => x !== id) })), className: "text-indigo-400 active:text-red-500" }, "✕")) : null;
    })), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ.filter((s) => !schedEdit.studentIds.includes(s.id)), value: schedPick, onChange: setSchedPick, placeholder: "搜索并添加学员..." })), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          if (schedPick) {
            setSchedEdit((p) => ({ ...p, studentIds: [...p.studentIds, schedPick] }));
            setSchedPick(null);
          }
        },
        disabled: !schedPick,
        className: "bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-4 py-2.5 rounded-xl text-xs font-bold"
      },
      "加入班次"
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 justify-end" }, /* @__PURE__ */ React.createElement("button", { onClick: () => setSchedEdit(null), className: "bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50" }, "取消"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveSchedule,
        disabled: busy,
        className: "bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold"
      },
      schedEdit.id ? "保存修改" : "创建班次"
    )))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col lg:flex-row gap-3 items-end" }, /* @__PURE__ */ React.createElement("div", { className: "w-full lg:w-44" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "课程日期"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: rDate,
        onChange: (e) => setRDate(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-indigo-900 focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-1" }, fmtDate(rDate))), /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "添加学员"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: availRoster, value: rPick, onChange: setRPick, placeholder: "搜索并选择学员..." })), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: addToRoster,
        disabled: !rPick || busy,
        className: "bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-bold text-sm min-h-[50px]"
      },
      "加入"
    )))), /* @__PURE__ */ React.createElement("div", { className: "mt-3 pt-3 border-t border-gray-100 flex gap-2 items-center flex-wrap" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-gray-500" }, "📋 班组模板"), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: grpSel,
        onChange: (e) => setGrpSel(e.target.value),
        className: "px-2 py-2 border border-gray-300 rounded-xl bg-white text-sm font-medium min-h-[40px] outline-none focus:ring-2 focus:ring-indigo-500"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "-- 选择模板 --"),
      Object.keys(db.groups || {}).sort().map((g) => /* @__PURE__ */ React.createElement("option", { key: g, value: g }, g, "（", (db.groups[g] || []).length, "人）"))
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: applyGroup,
        disabled: !grpSel || busy,
        className: "bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]"
      },
      "套用到当前日期"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveGroup,
        disabled: busy,
        className: "bg-white text-gray-600 border border-gray-300 active:bg-gray-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]"
      },
      "保存当前为模板"
    ), grpSel && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: deleteGroup,
        disabled: busy,
        className: "bg-white text-red-500 border border-red-200 active:bg-red-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]"
      },
      "删除"
    ), TENANT_SLUG && grpSel && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: groupToSchedule,
        disabled: busy,
        className: "bg-indigo-600 active:bg-indigo-700 text-white px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]"
      },
      "📆 转为每周班次"
    ))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b px-4 py-3 flex justify-between items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm text-gray-800" }, fmtDate(rDate), " · ", dayIds.filter((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived;
    }).length, " 人", scheduledForDate.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-indigo-500 ml-1" }, "（课表 ", scheduledForDate.length, " 班）")), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, dayIds.length > 0 && /* @__PURE__ */ React.createElement("button", { onClick: () => {
      const ids = dayIds;
      const lines = ids.map((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && !s.archived ? `${s.name}（剩余${s.balance}课时）` : null;
      }).filter(Boolean);
      const text = `【今日上课 ${lines.length} 人 - ${fmtDate(rDate)}】
${lines.join("\n")}`;
      copyText(text, "日报已复制到剪贴板");
    }, className: "bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]" }, "📋 日报"), dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.mobile;
    }) && /* @__PURE__ */ React.createElement("button", { onClick: () => {
      const ids = dayIds;
      const msg = `提醒：您的上课时间是 ${fmtDate(rDate)}，请准时到课。Studio 期待见到您！`;
      const lines = ids.map((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && !s.archived && s.mobile ? `${s.name}（${s.mobile}）` : null;
      }).filter(Boolean);
      copyText(lines.map((l) => `${l}
${msg}`).join("\n\n"), `已复制 ${lines.length} 条提醒内容`);
    }, className: "bg-white border border-green-300 active:bg-green-50 text-green-700 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]" }, "💬 批量提醒"), dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.balance > 0;
    }) && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: batchCheckIn,
        disabled: busy,
        className: "bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[36px]"
      },
      "⚡ 全员消课"
    ))), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-100" }, !dayIds.length && /* @__PURE__ */ React.createElement("div", { className: "p-8 text-center text-gray-400 text-sm" }, "今日暂无排班", TENANT_SLUG ? "（可在上方「每周课表」建固定班次，命中当天自动排入）" : ""), dayIds.map((sid) => {
      const s = db.students.find((x) => x.id === sid);
      if (!s || s.archived) return null;
      const lowBal = (parseInt(s.balance, 10) || 0) <= renewTh;
      return /* @__PURE__ */ React.createElement("div", { key: sid, className: `px-4 py-3 flex items-center hover-row gap-3 min-h-[64px] ${lowBal ? "bg-amber-50/60" : ""}` }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-900 truncate" }, s.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, s.mobile || "—", lowBal && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-amber-600 font-bold" }, "⚡ 余额告急"))), lowBal && /* @__PURE__ */ React.createElement("button", { onClick: () => {
        const msg = `${s.name} 家长您好！温馨提醒：当前剩余 ${s.balance} 课时${(parseInt(s.balance, 10) || 0) === 0 ? "（已用完）" : ""}，为不影响后续上课，欢迎联系老师续课～ 🎨`;
        copyText(msg, `已复制给 ${s.name} 的催费提醒`);
      }, className: "px-3 py-2.5 bg-amber-100 active:bg-amber-200 text-amber-700 border border-amber-300 rounded-xl text-xs font-bold min-h-[44px] flex-shrink-0" }, "💬 催费"), rosterDone.has(s.id) && /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-bold text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5 flex-shrink-0" }, "✓ 已签"), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }), /* @__PURE__ */ React.createElement("div", { className: "flex gap-1.5 flex-shrink-0" }, s.mobile && /* @__PURE__ */ React.createElement(
        "a",
        {
          href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent(`提醒：您的上课时间是 ${fmtDate(rDate)}，请准时到课。Studio 期待见到您！`)}`,
          className: "px-3 py-2.5 bg-green-50 active:bg-green-100 text-green-700 border border-green-200 rounded-xl text-xs font-bold min-h-[44px] flex items-center"
        },
        "💬"
      ), (db.rosters[rDate] || []).includes(s.id) ? /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => removeFromRoster(s.id),
          disabled: busy,
          className: "px-3 py-2.5 bg-gray-100 active:bg-gray-200 text-gray-600 rounded-xl text-xs font-bold min-h-[44px] min-w-[44px]"
        },
        "移出"
      ) : /* @__PURE__ */ React.createElement("span", { className: "px-3 py-2.5 text-indigo-500 bg-indigo-50 border border-indigo-100 rounded-xl text-xs font-bold min-h-[44px] flex items-center flex-shrink-0", title: "来自每周课表" }, "📆"), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => undoCheckIn(s.id, s.name),
          disabled: busy,
          className: "hidden md:block px-3 py-2.5 bg-amber-50 active:bg-amber-100 text-amber-700 border border-amber-200 rounded-xl text-xs font-bold min-h-[44px]"
        },
        "↩"
      ), rosterDone.has(s.id) ? /* @__PURE__ */ React.createElement("button", { disabled: true, className: "px-4 py-2.5 rounded-xl text-sm font-bold text-green-700 bg-green-50 border border-green-200 min-h-[44px] cursor-default" }, "✓") : /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => checkIn(s.id, s.name),
          disabled: busy || s.balance <= 0,
          className: `px-4 py-2.5 rounded-xl text-sm font-bold text-white min-h-[44px] ${s.balance > 0 ? "bg-green-600 active:bg-green-700" : "bg-gray-300 cursor-not-allowed"}`
        },
        "✅"
      )));
    })))),
    tab === "students" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "客户档案 (", sortedFiltered.length, ")"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportStudentsCSV,
        className: "bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm min-h-[44px]"
      },
      "⬇️ CSV"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setTab("new_student"),
        className: "bg-indigo-600 active:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md min-h-[44px]"
      },
      "➕ 新建"
    ))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        placeholder: "🔍 搜索姓名 / 电话 / 微信 / 邮箱...",
        value: srch,
        onChange: (e) => setSrch(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1 pb-1" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 items-center", style: { minWidth: "max-content" } }, /* @__PURE__ */ React.createElement(
      "select",
      {
        value: sortBy,
        onChange: (e) => setSortBy(e.target.value),
        className: "px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-sm min-h-[40px] flex-shrink-0"
      },
      /* @__PURE__ */ React.createElement("option", { value: "name-az" }, "名 A→Z"),
      /* @__PURE__ */ React.createElement("option", { value: "name-za" }, "名 Z→A"),
      /* @__PURE__ */ React.createElement("option", { value: "last-az" }, "姓 A→Z"),
      /* @__PURE__ */ React.createElement("option", { value: "last-za" }, "姓 Z→A"),
      /* @__PURE__ */ React.createElement("option", { value: "bal-desc" }, "课时 高→低"),
      /* @__PURE__ */ React.createElement("option", { value: "bal-asc" }, "课时 低→高"),
      /* @__PURE__ */ React.createElement("option", { value: "date-desc" }, "最近活跃")
    ), [["all", "全部"], ["active", "有余额"], ["low", `低余额≤${renewTh}`], ["zero", "已清零"], ["archived", "归档库"], ["tag-hot", "🔥 活跃"], ["tag-low", "💤 低频"], ["tag-risk", "⚠️ 流失风险"]].map(([v, l]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: v,
        onClick: () => setFilterBy(v),
        className: `px-4 py-2 rounded-xl text-xs font-bold border min-h-[40px] transition flex-shrink-0 ${filterBy === v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-300 active:border-indigo-300"}`
      },
      l
    ))))), filterBy === "low" && sortedFiltered.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-orange-700" }, "⚡ 待续课学员 ", sortedFiltered.length, " 人（余额 ≤", renewTh, " 节）"), /* @__PURE__ */ React.createElement("button", { onClick: () => {
      const lines = sortedFiltered.map((s) => `${s.name} 您好～您在 Studio 的剩余课时为 ${s.balance} 节，为不影响后续上课安排，欢迎随时联系老师续课哦 🎨`);
      copyText(lines.join("\n\n"), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
    }, className: "bg-orange-600 active:bg-orange-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[40px]" }, "📋 复制全部提醒话术")), !sortedFiltered.length && /* @__PURE__ */ React.createElement("div", { className: "text-center py-10 text-gray-400" }, "无匹配学员"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" }, sortedFiltered.map((s) => /* @__PURE__ */ React.createElement("div", { key: s.id, className: `bg-white rounded-2xl p-4 shadow-sm border hover-row transition flex flex-col justify-between print-card ${s.archived ? "border-gray-200 opacity-70" : parseInt(s.balance, 10) === 0 ? "border-red-100" : parseInt(s.balance, 10) <= 2 ? "border-orange-100" : "border-gray-100"}` }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-start mb-2 gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2.5 min-w-0" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 break-words leading-snug" }, s.name), s.archived && /* @__PURE__ */ React.createElement("span", { className: "text-xs bg-gray-100 text-gray-500 px-1.5 rounded mt-0.5 inline-block" }, "归档"))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-end gap-1 flex-shrink-0" }, /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }), (() => {
      const t = getTag(s);
      return t ? /* @__PURE__ */ React.createElement("span", { className: `text-xs px-2 py-0.5 rounded-full font-bold ${t.cls}` }, t.icon, " ", t.label) : null;
    })())), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm" }, "📞 ", s.mobile || "—"), s.email && /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm" }, "✉️ ", s.email), s.artStyle && /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm" }, "🎨 ", s.artStyle), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mt-0.5" }, "🗓 ", fmtDate(s.lastActive), daysSince(s.lastActive) < 9999 ? ` · ${daysSince(s.lastActive)}天前` : "")), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 mt-3" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setSelS(s);
          setEditP(false);
        },
        className: "flex-1 bg-gray-50 active:bg-gray-100 border border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-bold min-h-[44px]"
      },
      "详情"
    ), !s.archived && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setTuStu(s.id);
          setTab("topup");
        },
        title: "快速充值",
        className: "px-3.5 py-3 rounded-xl text-base font-bold bg-emerald-50 active:bg-emerald-100 text-emerald-700 border border-emerald-200 min-h-[44px]"
      },
      "💰"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => checkIn(s.id, s.name),
        disabled: s.balance <= 0 || busy,
        className: `flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[44px] ${s.balance > 0 ? "bg-green-600 active:bg-green-700" : "bg-gray-200 text-gray-400 cursor-not-allowed"}`
      },
      "✅ 消课"
    )))))), sortedFiltered.length > 15 && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          const m = document.querySelector("main");
          if (m) m.scrollTo({ top: 0, behavior: "smooth" });
          else window.scrollTo({ top: 0, behavior: "smooth" });
        },
        className: "fixed bottom-24 right-4 md:bottom-8 z-40 w-11 h-11 bg-indigo-600 active:bg-indigo-700 text-white rounded-full shadow-lg flex items-center justify-center text-lg",
        title: "回到顶部",
        "aria-label": "回到顶部"
      },
      "↑"
    )),
    tab === "new_student" && /* @__PURE__ */ React.createElement("div", { className: "anim bg-white rounded-2xl p-6 max-w-xl mx-auto shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold mb-5 text-gray-800" }, "➕ 新建客户档案"), /* @__PURE__ */ React.createElement("form", { onSubmit: handleAddStudent, className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-2 block" }, "照片 Photo ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(PhotoUploader, { value: formPhoto, onChange: setFormPhoto })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "First Name (名) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        required: true,
        name: "firstName",
        placeholder: "如 Holly",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "Last Name (姓) ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "lastName",
        placeholder: "如 Chen",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "电话"), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "mobile",
        placeholder: "04xx xxx xxx",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "初始课时"), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "balance",
        type: "number",
        min: "0",
        defaultValue: "0",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "微信号 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "wechat",
        placeholder: "如 wechat_id",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "邮箱 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "email",
        type: "email",
        placeholder: "example@email.com",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100" }, preferenceProfile().title, " ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填 / Optional")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, preferenceProfile().fields.map((field) => /* @__PURE__ */ React.createElement("div", { key: field.key }, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, field.label), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: `pref_${field.key}`,
        placeholder: field.placeholder,
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "生日 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        name: "birthday",
        min: "1920-01-01",
        max: "2099-12-31",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注"), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        name: "remark",
        rows: "3",
        placeholder: "备注信息...",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 pt-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "submit",
        disabled: busy,
        className: "flex-1 bg-indigo-600 active:bg-indigo-700 text-white py-3.5 rounded-xl font-bold text-sm shadow-md min-h-[52px]"
      },
      "确认建档"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          setTab("students");
          setFormPhoto("");
        },
        className: "px-6 py-3.5 bg-gray-100 active:bg-gray-200 text-gray-700 rounded-xl font-bold text-sm min-h-[52px]"
      },
      "取消"
    )))),
    tab === "pending" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "📋 待审核注册 (", (db.pending || []).length, ")"), !(db.pending || []).length && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "text-4xl mb-3" }, "✅"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-600" }, "暂无待审核申请"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mt-1" }, "学员通过注册页面提交后会显示在这里")), (db.pending || []).map((pen) => {
      const fullName = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
      return /* @__PURE__ */ React.createElement("div", { key: pen.id, className: "bg-white rounded-2xl shadow-sm border border-amber-200 p-5 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start gap-4" }, pen.photo ? /* @__PURE__ */ React.createElement("img", { src: mediaSrc(pen.photo), className: "w-16 h-16 rounded-full object-cover flex-shrink-0 border-2 border-indigo-100", alt: fullName }) : /* @__PURE__ */ React.createElement("div", { className: "w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-2xl font-bold text-indigo-600 flex-shrink-0" }, (pen.firstName || "?")[0].toUpperCase()), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-lg font-bold text-gray-800" }, fullName), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500" }, "📞 ", pen.mobile || "—", pen.wechat ? ` · 💬 ${pen.wechat}` : "", pen.email ? ` · ✉️ ${pen.email}` : ""), pen.birthday && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-pink-500 mt-0.5" }, "🎂 ", fmtDate(pen.birthday)), pen.mobile && (() => {
        const normP = (p) => (p || "").replace(/[\s\-\(\)]+/g, "");
        const match = db.students.filter((s) => !s.archived && normP(s.mobile) === normP(pen.mobile));
        return match.length > 0 ? /* @__PURE__ */ React.createElement("p", { className: "text-xs text-blue-500 mt-0.5" }, "📱 此电话已有学员：", match.map((s) => s.firstName && s.lastName ? `${s.firstName} ${s.lastName}` : s.name || "").join("、")) : null;
      })(), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "提交时间: ", pen.submittedAt || "—"))), preferenceRows(pen).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2 text-sm" }, preferenceRows(pen).map((row) => /* @__PURE__ */ React.createElement("div", { key: row.key, className: "bg-gray-50 rounded-2xl p-4 border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, row.label), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, row.value)))), pen.message && /* @__PURE__ */ React.createElement("div", { className: "bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-gray-700" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-amber-500 font-bold mb-1" }, "💬 留言"), /* @__PURE__ */ React.createElement("p", null, pen.message)), /* @__PURE__ */ React.createElement("div", { className: "flex items-end gap-3 pt-2 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "初始课时数"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "number",
          min: "0",
          placeholder: "0",
          value: approveCredits[pen.id] ?? "",
          onChange: (e) => setApproveCredits((p) => ({ ...p, [pen.id]: e.target.value })),
          className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl font-bold text-xl focus:ring-2 focus:ring-indigo-500 outline-none text-indigo-700"
        }
      )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-shrink-0" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => rejectStudent(pen.id),
          disabled: busy,
          className: "px-4 py-2.5 bg-red-50 active:bg-red-100 text-red-700 border border-red-200 font-bold rounded-xl text-sm min-h-[44px]"
        },
        "❌ 拒绝"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => approveStudent(pen.id),
          disabled: busy,
          className: "px-5 py-2.5 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm min-h-[44px]"
        },
        "✅ 批准建档"
      ))));
    })),
    tab === "topup" && /* @__PURE__ */ React.createElement("div", { className: "anim bg-white rounded-2xl shadow-sm border border-gray-100 p-6 max-w-2xl mx-auto" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold mb-4 text-gray-800" }, "💰 充值 & 结算"), TENANT_SLUG && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 mb-5" }, [["topup", "💰 充值"], ["refund", "💸 退款退课"]].map(([m, l]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: m,
        type: "button",
        onClick: () => setSettleMode(m),
        className: `flex-1 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${settleMode === m ? m === "refund" ? "border-red-400 bg-red-50 text-red-700" : "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-gray-200 bg-white text-gray-500 active:border-indigo-300"}`
      },
      l
    ))), /* @__PURE__ */ React.createElement("form", { onSubmit: settleMode === "refund" ? handleRefund : handleTopUp, className: "space-y-5" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "选择学员"), /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: tuStu, onChange: setTuStu, placeholder: "搜索学员姓名..." }), tuStu && (() => {
      const s = db.students.find((x) => x.id === tuStu);
      return s ? /* @__PURE__ */ React.createElement("div", { className: "mt-2 flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm truncate" }, s.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, s.mobile || "—", s.wechat ? ` · 💬 ${s.wechat}` : "")), /* @__PURE__ */ React.createElement("div", { className: "text-right flex-shrink-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "当前余额"), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }))) : null;
    })(), tuStu && (() => {
      const s = db.students.find((x) => x.id === tuStu);
      const recent = !s ? [] : db.logs.filter((l) => (l.studentId === s.id || !l.studentId && l.studentName === s.name) && (l.action === "充值购课" || l.action === "退款退课")).slice(0, 3);
      if (!recent.length) return null;
      return /* @__PURE__ */ React.createElement("div", { className: "mt-2 border border-gray-100 rounded-xl divide-y divide-gray-50 text-xs" }, recent.map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "flex items-center justify-between px-3 py-2" }, /* @__PURE__ */ React.createElement("span", { className: l.action === "退款退课" ? "text-red-500 font-bold" : "text-gray-600 font-bold" }, l.action), /* @__PURE__ */ React.createElement("span", { className: `font-bold ${l.action === "退款退课" ? "text-red-500" : "text-gray-700"}` }, String(l.change), " 课时 · $", l.feePaid || 0), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, String(l.date).split(",")[0]))));
    })()), settleMode === "refund" ? /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退课节数 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "1",
        required: true,
        value: rfCr,
        onChange: (e) => setRfCr(e.target.value),
        className: "w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退款金额 (AUD) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        step: "0.01",
        required: true,
        value: rfAmt,
        onChange: (e) => setRfAmt(e.target.value),
        className: "w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"
      }
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "退款方式"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, ["现金", "微信", "银行转账", "其他"].map((pm) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pm,
        type: "button",
        onClick: () => setTuPay(pm),
        className: `px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay === pm ? "border-red-400 bg-red-50 text-red-700" : "border-gray-200 bg-white text-gray-600 active:border-red-300"}`
      },
      pm
    )))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退款原因 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        required: true,
        value: rfReason,
        onChange: (e) => setRfReason(e.target.value),
        placeholder: "如 搬家、时间冲突、课程不合适...",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm"
      }
    )), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 bg-red-50 border border-red-100 rounded-xl px-3 py-2" }, "退款金额将以负数计入营收（净额自动核减）；退课节数直接从剩余课时扣减。此操作会记入账本与操作日志。")) : /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "套餐快选"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 lg:grid-cols-3 gap-2 mb-4" }, (db.packages || []).map((pkg) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pkg.id,
        type: "button",
        onClick: () => {
          if (tuPkg === String(pkg.id)) {
            setTuCr("");
            setTuFee("");
            setTuPkg("");
          } else {
            setTuCr(String(pkg.credits));
            setTuFee(String(pkg.price));
            setTuPkg(String(pkg.id));
          }
        },
        className: `py-3 px-2 border-2 rounded-xl text-sm font-bold min-h-[50px] ${tuPkg === String(pkg.id) ? "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-indigo-200 bg-indigo-50 active:bg-indigo-100 text-indigo-800"}`
      },
      pkg.name,
      /* @__PURE__ */ React.createElement("br", null),
      /* @__PURE__ */ React.createElement("span", { className: "font-normal text-xs" }, pkg.credits, "课时 · $", pkg.price)
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3 mb-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "课时数 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        name: "credits",
        min: "1",
        required: true,
        value: tuCr,
        onChange: (e) => setTuCr(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "实收金额 (AUD) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        name: "fee",
        min: "0",
        step: "0.01",
        required: true,
        value: tuFee,
        onChange: (e) => setTuFee(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-green-700"
      }
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "付款方式"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, ["现金", "微信", "银行转账", "其他"].map((pm) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pm,
        type: "button",
        onClick: () => setTuPay(pm),
        className: `px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay === pm ? "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-gray-200 bg-white text-gray-600 active:border-indigo-300"}`
      },
      pm
    )))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        name: "tuRemark",
        placeholder: "如 节假日赠课、补偿调课...",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
      }
    ))), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "submit",
        disabled: busy || !tuStu,
        className: `w-full disabled:bg-gray-300 text-white py-4 rounded-xl font-bold text-sm shadow-xl min-h-[56px] ${settleMode === "refund" ? "bg-red-500 active:bg-red-600" : "bg-indigo-600 active:bg-indigo-700"}`
      },
      busy ? "处理中..." : settleMode === "refund" ? "确认退款退课" : "确认收款并入账"
    ))),
    tab === "logs" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "📜 操作日志"), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: lStu, onChange: setLStu, placeholder: "🔍 精确筛选学员...", showBal: false })), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: lAct,
        onChange: (e) => setLAct(e.target.value),
        className: "px-3 py-3 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none min-h-[50px]"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "全部操作"),
      logActions.map((a) => /* @__PURE__ */ React.createElement("option", { key: a, value: a }, a))
    )), !lStu && /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        placeholder: "🔍 或输入关键字搜索...",
        value: lSrch,
        onChange: (e) => setLSrch(e.target.value),
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, [
      { l: "本月", fn: () => {
        const n = /* @__PURE__ */ new Date();
        const y = n.getFullYear(), m = String(n.getMonth() + 1).padStart(2, "0");
        setLDateFrom(`${y}-${m}-01`);
        setLDateTo(`${y}-${m}-${String(new Date(y, n.getMonth() + 1, 0).getDate()).padStart(2, "0")}`);
      } },
      { l: "近30天", fn: () => {
        const t = /* @__PURE__ */ new Date(), f = new Date(t - 30 * 864e5);
        setLDateFrom(f.toLocaleDateString("en-CA"));
        setLDateTo(t.toLocaleDateString("en-CA"));
      } },
      { l: "本年", fn: () => {
        const y = (/* @__PURE__ */ new Date()).getFullYear();
        setLDateFrom(`${y}-01-01`);
        setLDateTo(`${y}-12-31`);
      } }
    ].map(({ l, fn }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: l,
        type: "button",
        onClick: fn,
        className: "px-3 py-1.5 bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold min-h-[36px]"
      },
      l
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center gap-2 text-sm w-full sm:w-auto" }, /* @__PURE__ */ React.createElement("span", { className: "font-medium text-gray-500" }, "日期范围"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: lDateFrom,
        onChange: (e) => setLDateFrom(e.target.value),
        className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px] text-sm"
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, "至"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: lDateTo,
        onChange: (e) => setLDateTo(e.target.value),
        className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px] text-sm"
      }
    ))), (lStu || lSrch || lAct || lDateFrom || lDateTo) && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setLStu(null);
          setLSrch("");
          setLAct("");
          setLDateFrom("");
          setLDateTo("");
        },
        className: "px-3 py-2 bg-gray-100 active:bg-gray-200 text-gray-500 rounded-xl text-xs font-bold min-h-[40px]"
      },
      "✕ 清除"
    ), /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-400" }, filteredLogs.length, " 条"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportLogsCSV,
        className: "ml-auto bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-xs min-h-[40px]"
      },
      "⬇️ CSV"
    ))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-left" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "border-b-2 border-gray-100 text-gray-400 text-xs" }, /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "时间"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "学员"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "操作"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "变动"))), /* @__PURE__ */ React.createElement("tbody", null, pagedLogs.map((l) => /* @__PURE__ */ React.createElement("tr", { key: l.id, className: "border-b border-gray-50 hover-row" }, /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-400 text-xs font-mono whitespace-nowrap" }, l.date), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-gray-800 text-sm" }, l.studentName), /* @__PURE__ */ React.createElement("td", { className: "p-3" }, /* @__PURE__ */ React.createElement("span", { className: `px-1.5 py-0.5 rounded text-xs font-bold border ${l.action === "充值购课" ? "bg-green-100 text-green-700 border-green-200" : l.action === "上课签到" ? "bg-indigo-100 text-indigo-700 border-indigo-200" : l.action && l.action.includes("手动") ? "bg-orange-100 text-orange-700 border-orange-200" : l.action && (l.action.includes("拒绝") || l.action.includes("删除")) ? "bg-red-100 text-red-700 border-red-200" : "bg-gray-100 text-gray-700 border-gray-200"}` }, l.action), l.payMethod && /* @__PURE__ */ React.createElement("span", { className: "ml-1 bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-xs" }, l.payMethod), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 block mt-0.5" }, l.note), l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-green-600 font-bold" }, "$", l.feePaid)), /* @__PURE__ */ React.createElement("td", { className: `p-3 font-bold ${String(l.change).startsWith("-") ? "text-orange-500" : l.change === "0" || l.change === 0 ? "text-gray-400" : "text-green-500"}` }, l.change))), !pagedLogs.length && /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("td", { colSpan: "4", className: "p-8 text-center text-gray-400" }, "无记录"))))), logPageCount > 1 && /* @__PURE__ */ React.createElement("div", { className: "p-3 border-t flex items-center justify-center gap-1.5" }, /* @__PURE__ */ React.createElement("button", { disabled: lPage === 1, onClick: () => setLPage(1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]" }, "«"), /* @__PURE__ */ React.createElement("button", { disabled: lPage === 1, onClick: () => setLPage((p) => p - 1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]" }, "‹"), /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-600 px-2" }, lPage, " / ", logPageCount), /* @__PURE__ */ React.createElement("button", { disabled: lPage === logPageCount, onClick: () => setLPage((p) => p + 1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]" }, "›"), /* @__PURE__ */ React.createElement("button", { disabled: lPage === logPageCount, onClick: () => setLPage(logPageCount), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]" }, "»")))),
    tab === "stats" && /* @__PURE__ */ React.createElement("div", { className: "anim space-y-5" }, /* @__PURE__ */ React.createElement("h2", { className: "text-xl md:text-2xl font-bold text-gray-800" }, "📈 商业洞察"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gradient-to-br from-indigo-500 to-indigo-700 p-4 rounded-2xl text-white shadow-md" }, /* @__PURE__ */ React.createElement("p", { className: "text-indigo-100 text-xs mb-1" }, "历史总营收"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold" }, "$", analytics.totalRevenue.toFixed(0))), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "建档学员"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-gray-800" }, analytics.totalStudents)), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "累计消课"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-indigo-600" }, analytics.totalCheckins)), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "课时资产池"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-emerald-600" }, analytics.totalBalance))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "近 12 个月营收 (AUD)"), sStu && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg" }, "全局数据")), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1" }, /* @__PURE__ */ React.createElement("div", { style: { minWidth: "580px" } }, /* @__PURE__ */ React.createElement(BarChart, { items: analytics.chart12.map((d) => ({ v: d.rev, l: d.l })), color: "#6366f1", h: 130 })))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "近 12 个月消课次数"), sStu && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg" }, "全局数据")), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1" }, /* @__PURE__ */ React.createElement("div", { style: { minWidth: "580px" } }, /* @__PURE__ */ React.createElement(BarChart, { items: analytics.chart12.map((d) => ({ v: d.ci, l: d.l })), color: "#10b981", h: 130 }))))), payBreakdown.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm mb-3" }, "付款方式分布"), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-3" }, payBreakdown.map(([pm, d]) => /* @__PURE__ */ React.createElement("div", { key: pm, className: "bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 text-center min-w-[90px]" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, pm), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, "$", d.revenue.toFixed(0)), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, d.count, " 次"))))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "📊 经营月报（近 6 个月）"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportBizCSV,
        className: "bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]"
      },
      "⬇️ 导出 CSV"
    )), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-sm", style: { minWidth: "480px" } }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-xs text-gray-400 border-b" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-2 px-2" }, "月份"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "营收"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "充值"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "消课"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "新学员"))), /* @__PURE__ */ React.createElement("tbody", null, bizReport.rows.map((r) => /* @__PURE__ */ React.createElement("tr", { key: r.k, className: "border-b border-gray-50" }, /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 font-bold text-gray-700" }, r.label), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 font-bold text-indigo-700" }, "$", r.rev.toFixed(0)), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.topups, " 笔"), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.ci, " 次"), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.newStu || "—")))))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3 mt-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 mb-2" }, "课包销量排行（历史累计）"), bizReport.pkgRank.length === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "暂无充值记录"), bizReport.pkgRank.slice(0, 5).map(([name, d], i) => /* @__PURE__ */ React.createElement("div", { key: name, className: "flex items-center justify-between py-1 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-700" }, i + 1, ". ", name), /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-800" }, "$", d.revenue.toFixed(0), " ", /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 font-normal" }, "/ ", d.count, " 笔"))))), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 mb-2" }, "消课节奏（近 180 天）"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl font-bold text-emerald-600" }, bizReport.avgGap ? bizReport.avgGap.toFixed(1) : "—", " ", /* @__PURE__ */ React.createElement("span", { className: "text-sm font-normal text-gray-500" }, "天/次")), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-1" }, "规律上课学员 ", bizReport.regularStu, " 人的平均上课间隔。间隔变长 = 出勤率下降的早期信号")))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800" }, "财务明细报表"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportRevenueCSV,
        className: "bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-sm min-h-[40px]"
      },
      "⬇️ CSV"
    ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-1 bg-gray-100 p-1 rounded-xl" }, [["monthly", "月度"], ["yearly", "年度"], ["custom", "自定义"]].map(([v, l]) => /* @__PURE__ */ React.createElement("button", { key: v, onClick: () => setSPeriod(v), className: `px-3 py-2 rounded-lg text-sm font-bold min-h-[40px] ${sPeriod === v ? "bg-white shadow text-indigo-700" : "text-gray-500"}` }, l))))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-3 items-center" }, sPeriod === "monthly" && /* @__PURE__ */ React.createElement(
      "select",
      {
        value: sYear,
        onChange: (e) => setSYear(e.target.value),
        className: "px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-400 outline-none text-sm min-h-[40px]"
      },
      /* @__PURE__ */ React.createElement("option", { value: "all" }, "所有年份"),
      analytics.availYears.map((y) => /* @__PURE__ */ React.createElement("option", { key: y, value: y }, y, "年"))
    ), sPeriod === "custom" && /* Fix ⑩: type="month" gives YYYY-MM value, matches our monthKey format exactly */
    /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center gap-2 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "font-medium text-gray-500" }, "自定义范围"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("input", { type: "month", value: sFrom, onChange: (e) => setSFrom(e.target.value), className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]" }), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, "至"), /* @__PURE__ */ React.createElement("input", { type: "month", value: sTo, onChange: (e) => setSTo(e.target.value), className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]" }))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 ml-auto" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-500" }, "筛选:"), /* @__PURE__ */ React.createElement("div", { className: "w-48" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: sStu, onChange: setSStu, placeholder: "全部学员", showBal: false })))), statsData.rows.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex gap-4 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "合计: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold text-green-600" }, "$", statsData.totalRev.toFixed(2))), /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "消课: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold text-indigo-600" }, statsData.totalCI, " 次")), statsData.totalCI > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "均价/课: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, "$", (statsData.totalRev / statsData.totalCI).toFixed(1))))), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-left" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "border-b border-gray-100 text-gray-400 text-xs" }, /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "周期"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "入账流水"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "消课"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "充值次数"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "均价/课"))), /* @__PURE__ */ React.createElement("tbody", null, statsData.rows.map((r) => /* @__PURE__ */ React.createElement("tr", { key: r.key, className: "border-b border-gray-50 hover-row text-sm" }, /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-gray-700" }, sPeriod === "yearly" ? `${r.key}年` : fmtMK(r.key)), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-green-600" }, "$", r.revenue.toFixed(2)), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-indigo-600" }, r.checkins), /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-600" }, r.topups), /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-500" }, r.checkins > 0 ? `$${(r.revenue / r.checkins).toFixed(1)}` : "-"))), !statsData.rows.length && /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("td", { colSpan: "5", className: "p-8 text-center text-gray-400" }, "暂无数据")))))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b p-4" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 mb-3" }, "学员个人分析"), /* @__PURE__ */ React.createElement("div", { className: "max-w-xs" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: sStu2, onChange: setSStu2, placeholder: "选择学员查看详情...", showBal: true }))), studentStats ? /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3" }, [
      { l: "当前余额", v: `${studentStats.student.balance} 课时`, c: "text-indigo-700" },
      { l: "累计消课", v: `${studentStats.checkins} 次`, c: "text-gray-700" },
      { l: "累计购课", v: `${studentStats.totalBought} 课时`, c: "text-gray-700" },
      { l: "累计消费", v: `$${studentStats.totalSpent.toFixed(0)}`, c: "text-green-600" },
      { l: "充值次数", v: `${studentStats.topupCount} 次`, c: "text-gray-700" }
    ].map(({ l, v, c }) => /* @__PURE__ */ React.createElement("div", { key: l, className: "bg-gray-50 p-3 rounded-xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, l), /* @__PURE__ */ React.createElement("p", { className: `text-lg font-bold ${c}` }, v)))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3 text-sm text-gray-500" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl" }, "📞 ", studentStats.student.mobile || "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl" }, "✉️ ", studentStats.student.email || "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl" }, "🎯 首次: ", studentStats.first ? String(studentStats.first).split(",")[0] : "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl" }, "🕐 最近: ", studentStats.last ? String(studentStats.last).split(",")[0] : "—")), studentStats.student.remark && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl text-sm text-gray-600 border border-gray-100" }, "📝 ", studentStats.student.remark), /* @__PURE__ */ React.createElement("div", { className: "border border-gray-100 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 px-3 py-2 text-xs font-bold text-gray-600 border-b" }, "交易记录 (", studentStats.logs.length, ")"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50 max-h-56 overflow-y-auto sl" }, studentStats.logs.slice(0, 50).map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "px-3 py-2.5 flex justify-between text-sm min-h-[44px] items-center" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "font-medium text-gray-700" }, l.action), " ", l.payMethod && /* @__PURE__ */ React.createElement("span", { className: "text-blue-500 ml-1 text-xs" }, l.payMethod), " ", /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, l.note)), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 flex-shrink-0" }, l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-green-600 font-bold text-xs" }, "$", l.feePaid), /* @__PURE__ */ React.createElement("span", { className: `font-bold text-xs ${String(l.change).startsWith("-") ? "text-orange-500" : "text-green-500"}` }, l.change), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, String(l.date).split(",")[0]))))))) : /* @__PURE__ */ React.createElement("div", { className: "p-10 text-center text-gray-400 text-sm" }, "选择一名学员查看个人数据"))),
    selS && /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full sm:rounded-3xl sm:max-w-lg shadow-2xl overflow-hidden anim border-t sm:border border-gray-200" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center p-4 bg-gray-50 border-b" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2.5 min-w-0" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: selS.photo, name: selS.name, size: "sm" }), /* @__PURE__ */ React.createElement("h3", { className: "text-lg font-bold text-gray-900 truncate" }, selS.name), /* @__PURE__ */ React.createElement(BalBadge, { n: selS.balance }), selS.archived && /* @__PURE__ */ React.createElement("span", { className: "text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0" }, "归档")), /* @__PURE__ */ React.createElement("button", { onClick: () => {
      setSelS(null);
      setEditP(false);
    }, className: "text-gray-400 active:text-gray-700 text-2xl font-bold p-2 -mr-1 min-h-[44px] min-w-[44px] flex items-center justify-center" }, "×")), /* @__PURE__ */ React.createElement("div", { className: "p-5 modal-scroll", style: { maxHeight: "calc(100dvh - 80px)", paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 20px)" } }, !editP ? /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "First Name (名)"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.firstName || selS.name || "—")), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "Last Name (姓)"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.lastName || "—"))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "📞 电话"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.mobile || "—")), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "🗓 最近上课"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, fmtDate(selS.lastActive)))), (selS.wechat || selS.email) && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, selS.wechat && /* @__PURE__ */ React.createElement("div", { className: "bg-green-50 p-4 rounded-2xl border border-green-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-green-500 mb-1" }, "💬 微信号"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.wechat)), selS.email && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "✉️ 邮箱"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm break-all" }, selS.email))), selS.birthday && /* @__PURE__ */ React.createElement("div", { className: "bg-pink-50 p-4 rounded-2xl border border-pink-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-pink-400 mb-1" }, "🎂 生日"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, fmtDate(selS.birthday))), selS.remark && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "备注"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-700 whitespace-pre-wrap" }, selS.remark)), preferenceRows(selS).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2" }, preferenceRows(selS).map((row) => /* @__PURE__ */ React.createElement("div", { key: row.key, className: "bg-indigo-50 p-3 rounded-2xl border border-indigo-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-400 mb-0.5" }, row.label), /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-indigo-800" }, row.value)))), (() => {
      const topupsAll = db.logs.filter((l) => (l.studentId === selS.id || !l.studentId && l.studentName === selS.name) && l.action === "充值购课");
      const topups = topupsAll.slice(0, 10);
      if (!topupsAll.length) return null;
      return /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2" }, "💳 充值记录 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400 text-xs" }, "(", topupsAll.length, " 条", topupsAll.length > 10 ? " · 显示最近10条" : "", ")")), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, topups.map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "px-4 py-2.5 flex justify-between items-center text-sm" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-indigo-700" }, "+", l.change), /* @__PURE__ */ React.createElement("span", { className: "ml-2 text-xs text-gray-400" }, l.payMethod || ""), l.note && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-xs text-gray-400 truncate" }, l.note)), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 flex-shrink-0" }, l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-green-600 font-bold text-xs" }, "$", l.feePaid), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, String(l.date).split(",")[0]))))));
    })(), (() => {
      const items = selS.portfolio || [];
      return /* @__PURE__ */ React.createElement("div", { className: "border border-purple-100 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-purple-50 px-4 py-3 flex items-center justify-between" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-purple-700" }, "🎨 作品集", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-purple-400 text-xs ml-1" }, "(", items.length, " 张)")), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setPortUpload(true),
          className: "text-xs bg-purple-600 active:bg-purple-700 text-white px-3 py-1.5 rounded-lg font-bold"
        },
        "+ 上传"
      )), items.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "px-4 py-7 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "text-2xl mb-1" }, "🖼"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "还没有作品，点击「上传」添加第一张")) : /* @__PURE__ */ React.createElement("div", { className: "p-2.5 grid grid-cols-3 gap-2" }, items.map((item, idx) => /* @__PURE__ */ React.createElement(
        "div",
        {
          key: item.id,
          className: "port-thumb relative group cursor-pointer rounded-xl overflow-hidden bg-gray-100",
          style: { aspectRatio: "1" },
          onClick: () => setPortLB({ items, idx })
        },
        /* @__PURE__ */ React.createElement("div", { className: "img-skel absolute inset-0", id: `sk-${item.id}` }),
        /* @__PURE__ */ React.createElement(
          "img",
          {
            src: portfolioThumbSrc(selS.id, item),
            loading: "lazy",
            className: "w-full h-full object-cover relative",
            onLoad: (e) => {
              const sk = document.getElementById(`sk-${item.id}`);
              if (sk) sk.style.display = "none";
            },
            onError: (e) => {
              e.target.style.display = "none";
            }
          }
        ),
        /* @__PURE__ */ React.createElement("div", { className: "absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pt-4 pb-1" }, /* @__PURE__ */ React.createElement("p", { className: "text-white text-xs leading-tight truncate" }, fmtDate(item.date)), item.note && /* @__PURE__ */ React.createElement("p", { className: "text-white/70 text-xs truncate" }, item.note)),
        /* @__PURE__ */ React.createElement("div", { className: "port-actions absolute top-0.5 right-0.5 hidden group-hover:flex gap-1 z-10" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: (e) => {
              e.stopPropagation();
              setPortEdit({ sid: String(selS.id), item, note: item.note || "", date: item.date || todayISO() });
            },
            className: "bg-white/90 rounded-lg p-2 text-xs shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"
          },
          "✏️"
        ), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: (e) => {
              e.stopPropagation();
              portfolioDoDelete(String(item.id));
            },
            className: "bg-red-500 rounded-lg p-2 text-white text-xs shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"
          },
          "🗑"
        ))
      ))));
    })(), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, !selS.archived && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => checkIn(selS.id, selS.name),
        disabled: selS.balance <= 0 || busy,
        className: `flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[50px] ${selS.balance > 0 ? "bg-green-600 active:bg-green-700" : "bg-gray-200 text-gray-400 cursor-not-allowed"}`
      },
      "✅ 消课"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => undoCheckIn(selS.id, selS.name),
        disabled: busy,
        className: "flex-1 py-3 rounded-xl text-sm font-bold bg-amber-50 active:bg-amber-100 text-amber-700 border border-amber-200 min-h-[50px]"
      },
      "↩ 撤销"
    )), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setEditP(true);
          setEditPhoto(selS.photo || "");
        },
        className: "flex-1 py-3 rounded-xl text-sm font-bold bg-white border-2 border-indigo-100 active:bg-indigo-50 text-indigo-700 min-h-[50px]"
      },
      "✏️ 编辑"
    )), !selS.archived && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setTuStu(selS.id);
          setSelS(null);
          setEditP(false);
          setTab("topup");
        },
        className: "w-full py-3 rounded-xl text-sm font-bold bg-white border border-gray-200 active:bg-gray-50 text-gray-700 min-h-[50px]"
      },
      "💰 快速充值"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => openGrowthReport(selS),
        className: "w-full py-3 rounded-xl text-sm font-bold bg-gradient-to-r from-purple-500 to-pink-500 active:from-purple-600 active:to-pink-600 text-white min-h-[50px] shadow-sm"
      },
      "🌟 生成成长报告（发给家长）"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => archiveStudent(selS.id, selS.name, !selS.archived),
        className: `w-full py-3 rounded-xl text-sm font-bold border min-h-[50px] ${selS.archived ? "bg-green-50 active:bg-green-100 text-green-700 border-green-200" : "bg-gray-50 active:bg-gray-100 text-gray-500 border-gray-200"}`
      },
      selS.archived ? "📤 恢复学员" : "📦 归档学员"
    )) : /* @__PURE__ */ React.createElement("form", { onSubmit: handleUpdateStudent, className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-2 block" }, "照片 Photo ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(PhotoUploader, { value: editPhoto, onChange: setEditPhoto })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "First Name (名) *"), /* @__PURE__ */ React.createElement("input", { name: "firstName", defaultValue: selS.firstName || selS.name || "", required: true, className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "Last Name (姓) ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "lastName", defaultValue: selS.lastName || "", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold" }))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "电话"), /* @__PURE__ */ React.createElement("input", { name: "mobile", defaultValue: selS.mobile, placeholder: "04xx xxx xxx", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-indigo-700 mb-1 block" }, "课时余额"), /* @__PURE__ */ React.createElement("input", { name: "balance", type: "number", min: "0", defaultValue: selS.balance, required: true, className: "w-full px-3 py-3 border border-indigo-300 bg-indigo-50 text-indigo-800 font-bold text-xl rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" }), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-amber-500 mt-1" }, "⚠️ 修改将记入日志"))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "微信号 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "wechat", defaultValue: selS.wechat || "", placeholder: "如 wechat_id", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "邮箱 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "email", type: "email", defaultValue: selS.email || "", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" }))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "🎂 生日 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        name: "birthday",
        defaultValue: selS.birthday || "",
        min: "1920-01-01",
        max: "2099-12-31",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注"), /* @__PURE__ */ React.createElement("textarea", { name: "remark", defaultValue: selS.remark, rows: "3", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none" })), /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100" }, preferenceProfile().title, " ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, preferenceProfile().fields.map((field) => /* @__PURE__ */ React.createElement("div", { key: field.key }, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, field.label), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: `pref_${field.key}`,
        defaultValue: preferenceValue(selS, field.key),
        placeholder: field.placeholder,
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center pt-3 border-t border-gray-100" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => handleDelete(selS.id, selS.name),
        disabled: busy,
        className: "px-4 py-3 bg-red-50 active:bg-red-100 text-red-700 font-bold rounded-xl text-sm border border-red-200 min-h-[50px]"
      },
      "🗑️ 永久删除"
    ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => confirm("放弃未保存的修改？", () => {
      setEditP(false);
      setEditPhoto("");
    }, { confirmText: "放弃修改" }), className: "px-4 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm min-h-[50px]" }, "取消"), /* @__PURE__ */ React.createElement("button", { type: "submit", disabled: busy, className: "px-6 py-3 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md min-h-[50px]" }, "💾 保存")))))))
  ), moreOpen && /* @__PURE__ */ React.createElement("div", { className: "md:hidden fixed inset-0 z-[45]", onClick: () => setMoreOpen(false) }), moreOpen && /* @__PURE__ */ React.createElement(
    "div",
    {
      className: "md:hidden fixed bottom-[calc(56px+env(safe-area-inset-bottom,0px))] left-0 right-0 z-[46] bg-indigo-900 border-t border-indigo-700 px-4 py-3 grid grid-cols-4 gap-2 anim",
      onClick: (e) => e.stopPropagation()
    },
    [{ k: "logs", i: "📜", s: "日志" }, { k: "stats", i: "📈", s: "统计" }, { k: "pending", i: "📋", s: "待审核", badge: pendingCount }, { k: "new_student", i: "➕", s: "新建" }].map(({ k, i, s, badge }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: k,
        onClick: () => {
          setTab(k);
          setMoreOpen(false);
        },
        className: `flex flex-col items-center justify-center py-2.5 gap-0.5 rounded-xl relative ${["logs", "stats", "pending", "new_student"].includes(tab) && tab === k ? "bg-indigo-700" : "active:bg-indigo-800"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-[22px] leading-none" }, i),
      /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold leading-none tracking-tight ${["logs", "stats", "pending", "new_student"].includes(tab) && tab === k ? "text-white" : "text-indigo-300"}` }, s),
      badge > 0 && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1 right-2 bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, badge)
    ))
  ), /* @__PURE__ */ React.createElement(
    "nav",
    {
      className: "md:hidden fixed bottom-0 left-0 right-0 z-40 bg-indigo-900 border-t border-indigo-800 flex",
      style: { paddingBottom: "env(safe-area-inset-bottom,0px)", transform: "translateZ(0)", willChange: "transform" }
    },
    [{ k: "dashboard", i: "📊", s: "工作台" }, { k: "roster", i: "📅", s: "排课" }, { k: "students", i: "👥", s: "档案" }, { k: "topup", i: "💰", s: "充值" }].map(({ k, i, s }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: k,
        onClick: () => {
          setTab(k);
          setMoreOpen(false);
        },
        className: `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative ${tab === k ? "bg-indigo-700" : "active:bg-indigo-800"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-[22px] leading-none" }, i),
      /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold leading-none tracking-tight ${tab === k ? "text-white" : "text-indigo-300"}` }, s),
      k === "dashboard" && analytics.lowBalance.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1.5 right-[18%] bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, analytics.lowBalance.length)
    )),
    /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setMoreOpen((o) => !o),
        className: `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative ${moreOpen || ["logs", "stats", "pending", "new_student"].includes(tab) ? "bg-indigo-700" : "active:bg-indigo-800"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-[22px] leading-none" }, moreOpen ? "✕" : "⋯"),
      /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold leading-none tracking-tight ${moreOpen || ["logs", "stats", "pending", "new_student"].includes(tab) ? "text-white" : "text-indigo-300"}` }, "更多"),
      pendingCount > 0 && !moreOpen && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1.5 right-[18%] bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, pendingCount)
    )
  ));
}
ReactDOM.createRoot(document.getElementById("root")).render(/* @__PURE__ */ React.createElement(App, null));
