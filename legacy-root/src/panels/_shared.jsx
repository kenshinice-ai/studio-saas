/* 面板之间共享的小工具。
 *
 * 存在的理由是一个已经犯过两次的错：v1 接口返回的日期是 RFC 1123
 * （`Fri, 28 Aug 2026 00:00:00 GMT`），不是 ISO。对它做 slice(0, 10) 会得到
 * `Fri, 28 Au`，主文件的 fmtDate 对非 ISO 的兜底 split(' ')[0] 会得到 `Fri,`。
 * 两个面板各自写了一遍，各自错了一次。
 *
 * 所以格式化只留一份，放在 import 得到的地方 —— 下一个面板不会再想自己写。
 */

/** 金额：分 → 澳元。整数分进来，字符串出去，中间不经浮点。 */
export const aud = (cents) => (Number(cents || 0) / 100)
  .toLocaleString('en-AU', { style: 'currency', currency: 'AUD' });

/** 日期：同时认 ISO 与 RFC 1123，输出 DD/MM/YYYY（与 CMS 其余部分一致）。 */
export const fmtApiDate = (value) => {
  if (!value) return '—';
  const iso = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(parsed.getDate())}/${pad(parsed.getMonth() + 1)}/${parsed.getFullYear()}`;
};

/** 本月 1 号到今天，供默认报表区间使用。 */
export const monthRange = () => {
  const now = new Date();
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), to: iso(now) };
};

/** 日期 → `<input type="date">` 的 value（YYYY-MM-DD）；认 ISO 也认 RFC 1123。
 *
 * 和 fmtApiDate 分开是因为用途不同：那个给人看（DD/MM/YYYY），这个给控件读。
 * 控件只接受 YYYY-MM-DD，喂给它别的格式会静默显示为空 —— 而空的日期框在
 * 「更新联系状态」时会被当成用户要清除，把服务端已存的跟进计划抹掉。
 * 这正是 v10.15.0 之前的行为，所以这里不做任何 slice。
 *
 * 09:00 那个锚点时间由写入方决定；读回来时只取日期部分，不做时区换算 ——
 * 服务端以 UTC 存取，日期部分不会因为读的人在哪里而漂移。
 */
export const apiDateInputValue = (value) => {
  if (!value) return '';
  const iso = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`;
};
