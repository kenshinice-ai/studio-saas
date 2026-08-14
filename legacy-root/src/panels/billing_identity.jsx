/* 开票方是谁 —— 发票上必须载明的那一半。
 *
 * v10.0.0 把整个钱这一层做完了，却从没问过工作室自己是谁。
 * `billing_accounts` 上有 ABN 和地址，但那是**付款方**：被开票的家庭或学校。
 * 开票方的身份哪儿都没有，于是这个产品开出的单据，在它销售的国家里
 * 在法律上算不上税务发票。
 *
 * 澳洲的税务发票必须写明供应商身份与 ABN。没有 ABN，家长和他们的会计
 * 就抵扣不了这笔 GST —— 一张收了 GST 却不写 ABN 的发票，对收到的人来说
 * 比没有还糟，因为他还得回头找你重开。
 *
 * 所以「已注册 GST 但没填 ABN」不是提示，是拦截：0040 里有 CHECK 约束，
 * billing.issuing_blockers() 在开具时再拦一道。这里只是让人能填。
 */
const { useState, useEffect, useCallback } = React;

const TEXT_FIELDS = [
    ['legal_name', '法定主体名称', '开票主体的注册名，例如 Paradise Production Pty Ltd'],
    ['trading_name', '经营名称', '对外使用的工作室名，可与法定名称不同'],
    ['abn', 'ABN', '11 位澳洲商业号码'],
    ['address_line1', '地址第一行', ''],
    ['address_line2', '地址第二行', ''],
    ['suburb', '区/市', ''],
    ['state', '州', 'VIC / NSW / QLD …'],
    ['postcode', '邮编', ''],
    ['contact_email', '开票邮箱', '家长回信会到这里'],
    ['contact_phone', '开票电话', ''],
    ['bank_account_name', '收款户名', ''],
    ['bank_bsb', 'BSB', ''],
    ['bank_account_no', '银行账号', ''],
];

export function BillingIdentityPanel({ api, showToast, canManage }) {
    const [form, setForm] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        try {
            const res = await api('/billing/identity');
            setForm(res.identity);
            setError('');
        } catch (e) {
            setError(e.status === 403 ? '这个工作室尚未开通开票功能。' : `加载失败：${e.message}`);
        }
    }, [api]);

    useEffect(() => { load(); }, [load]);

    if (error) return <p className="text-sm text-red-600">{error}</p>;
    if (!form) return null;

    const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

    async function save() {
        setBusy(true);
        try {
            const res = await api('/billing/identity', { method: 'PUT', body: JSON.stringify(form) });
            setForm(res.identity);
            showToast('开票信息已保存', 'success');
        } catch (e) {
            showToast(e.message || '保存失败', 'error');
        } finally { setBusy(false); }
    }

    const gstWithoutAbn = form.gst_registered && !String(form.abn || '').trim();

    return (
        <div className="space-y-3">
            <p className="text-sm text-gray-500">
                这些内容会印在每一张发票上。没有它们，开具会被拒绝 ——
                一张收了 GST 却不写 ABN 的单据，家长的会计用不了。
            </p>

            {!form.configured && (
                <p className="text-xs font-bold text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
                    还没有填过。填完之前无法开具任何发票。
                </p>
            )}

            <label className={`flex items-center gap-3 min-h-[44px] px-4 rounded-xl border ${
                form.gst_registered ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'}`}>
                <input type="checkbox" checked={!!form.gst_registered} disabled={!canManage}
                       onChange={() => setForm(f => ({ ...f, gst_registered: !f.gst_registered }))} />
                <span className="text-sm font-bold text-gray-800">已注册 GST</span>
            </label>
            {gstWithoutAbn && (
                <p className="text-xs font-bold text-red-700">
                    勾了「已注册 GST」就必须填 ABN，否则保存会被拒绝。
                </p>
            )}
            {!form.gst_registered && (
                <p className="text-xs text-gray-500">
                    未注册 GST 时，发票行的税率请选「不计税」，单据也不会自称税务发票。
                </p>
            )}

            <div className="grid sm:grid-cols-2 gap-3">
                {TEXT_FIELDS.map(([key, label, hint]) => (
                    <label key={key} className="block text-xs text-gray-400">
                        {label}
                        <input value={form[key] || ''} onChange={set(key)} disabled={!canManage}
                               placeholder={hint}
                               className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800 disabled:bg-gray-50" />
                    </label>
                ))}
            </div>

            <label className="block text-xs text-gray-400">付款说明
                <textarea value={form.payment_note || ''} onChange={set('payment_note')} rows={2}
                          disabled={!canManage} placeholder="例如：请在到期日前转账，并在备注里写上发票号。"
                          className="block w-full mt-1 px-3 py-2 border border-gray-200 rounded-xl text-sm text-gray-800 disabled:bg-gray-50" />
            </label>

            {canManage && (
                <button type="button" onClick={save} disabled={busy}
                        className="min-h-[44px] px-5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
                    保存开票信息
                </button>
            )}
        </div>
    );
}
