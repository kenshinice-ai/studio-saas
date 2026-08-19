/* 充值结算 — 课时充值与耗课记录。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { BalBadge, Icon, PhotoAvatar, StudentPicker, TENANT_SLUG, v1Api } from "../components.jsx";
import { BillingAccountPicker } from "./billing.jsx";

export function TopupSection(props) {
    const {
        archivePackage, busy, canManageOperations, canRefund, canRegisterSettlementPayment, canSyncRefund,
        canUseSettlementBilling, db, handleRefund, handleTopUp, pkgCredits, pkgEditId,
        pkgName, pkgPrice, refundSourceError, refundSources, refundSourcesBusy, resetPackageEditor,
        rfAdjustDocuments, rfAmountTouched, rfAmt, rfCr, rfReason, rfSourceId,
        savePackage, setPkgCredits, setPkgEditId, setPkgName, setPkgPrice, setRfAdjustDocuments,
        setRfAmountTouched, setRfAmt, setRfCr, setRfReason, setRfSourceId, setSettleMode,
        setSettlementPayer, setSettlementPayerError, setSettlementPayerState, setTuCr, setTuCreateInvoice, setTuFee,
        setTuPay, setTuPaymentReceived, setTuPkg, setTuStu, settleMode, settlementAccounts,
        settlementPayerError, settlementPayerIntentRef, settlementPayerState, settlementResolvedAccountRef, settlementTaxCodes, sortedAZ,
        tuCr, tuCreateInvoice, tuFee, tuPay, tuPaymentReceived, tuPkg,
        tuStu,
    } = props;
    return (
<div className="anim bg-white rounded-2xl shadow-sm border border-gray-100 p-6 max-w-2xl mx-auto">
    <div className="flex items-start justify-between gap-3 mb-4"><div><h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="money" className="w-4 h-4"/>充值与退款</h2><p className="text-sm text-gray-500 mt-1">先选择学员，再完成充值或退款；支付渠道只记录实际收款方式，不在 CMS 内接入在线支付。</p></div></div>
    {canManageOperations && <details open className="mb-5 rounded-2xl border border-indigo-100 bg-indigo-50/60 overflow-hidden">
        <summary className="cursor-pointer select-none px-4 py-3 min-h-[48px] inline-flex items-center gap-2 text-sm font-bold text-indigo-900"><Icon name="card" className="w-4 h-4"/>套餐管理 <span className="text-xs font-normal text-indigo-500">{`${(db.packages||[]).length} 个套餐`}</span></summary>
        <div className="p-4 pt-1 space-y-3">
            <p className="text-xs text-indigo-700 leading-relaxed">这里定义前台充值时可快速选择的课包。修改套餐不会改动历史充值记录；删除前请确认它不再需要被新收款使用。</p>
            {(db.packages||[]).map(pkg=><div key={pkg.id} className="flex items-center gap-3 rounded-xl border border-indigo-100 bg-white px-3 py-2.5"><div className="min-w-0 flex-1"><p className="text-sm font-bold text-gray-800 truncate">{pkg.name}</p><p className="text-xs text-gray-500 mt-0.5">{pkg.credits} 课时 · AUD {Number(pkg.price||0).toFixed(2)}</p></div><button type="button" onClick={()=>{setPkgEditId(pkg.id);setPkgName(pkg.name);setPkgCredits(String(pkg.credits));setPkgPrice(String(pkg.price));}} className="min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-50">编辑</button><button type="button" onClick={()=>archivePackage(pkg)} aria-label={`删除套餐 ${pkg.name}`} className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50"><Icon name="trash" className="w-4 h-4"/></button></div>)}
            {pkgEditId === null && <button type="button" onClick={()=>{setPkgEditId(0);setPkgName('');setPkgCredits('');setPkgPrice('');}} className="w-full min-h-[44px] rounded-xl border border-dashed border-indigo-300 bg-white text-indigo-700 text-xs font-bold hover:bg-indigo-50"><Icon name="plus" className="w-4 h-4 inline mr-1"/>添加套餐</button>}
            {pkgEditId !== null && <div className="rounded-xl border border-indigo-200 bg-white p-3 space-y-3"><p className="text-sm font-bold text-indigo-900">{pkgEditId===0?'添加套餐':'编辑套餐'}</p><div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><label className="text-xs font-bold text-gray-600">套餐名称 *<input type="text" value={pkgName} onChange={e=>setPkgName(e.target.value)} placeholder="例如：10 课时包" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label><label className="text-xs font-bold text-gray-600">课时数 *<input type="number" min="1" value={pkgCredits} onChange={e=>setPkgCredits(e.target.value)} placeholder="10" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label><label className="text-xs font-bold text-gray-600">价格（AUD） *<input type="number" min="0" step="0.01" value={pkgPrice} onChange={e=>setPkgPrice(e.target.value)} placeholder="500.00" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label></div><p className="text-[11px] text-gray-400">价格仅供内部入账和套餐快选显示；银行转账仍由工作室线下核对。</p><div className="flex gap-2"><button type="button" onClick={resetPackageEditor} className="flex-1 min-h-[44px] rounded-xl border border-gray-300 text-xs font-bold text-gray-600">取消</button><button type="button" onClick={savePackage} disabled={busy} className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">{busy?'保存中…':'保存套餐'}</button></div></div>}
        </div>
    </details>}
    {/* E: refunds require credits:refund (owner/manager) — other roles only see the top-up form */}
    {TENANT_SLUG && canRefund && (
        <div className="flex gap-2 mb-5">
            {[['topup','充值'],['refund','退款退课']].map(([m,l]) => (
                <button key={m} type="button" onClick={()=>setSettleMode(m)}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${settleMode===m?(m==='refund'?'border-red-400 bg-red-50 text-red-700':'border-indigo-500 bg-indigo-100 text-indigo-900'):'border-gray-200 bg-white text-gray-500 active:border-indigo-300'}`}>{l}</button>
            ))}
        </div>
    )}
    <form onSubmit={settleMode==='refund'?handleRefund:handleTopUp} className="space-y-5">
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1.5 block">选择学员</label>
            <StudentPicker students={sortedAZ} value={tuStu} onChange={next=>{
                setTuStu(next);
                setSettlementPayerState({mode:'student', accountId:'', createPayload:null, linkedStudentIds:next?[next]:[]});
                settlementResolvedAccountRef.current = '';
                settlementPayerIntentRef.current = '';
            }} placeholder="搜索学员姓名..."/>
            {tuStu && (()=>{const s=db.students.find(x=>x.id===tuStu); return s?(
                <div className="mt-2 flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
                    <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                    <div className="flex-1 min-w-0">
                        <p className="font-bold text-gray-800 text-sm truncate">{s.name}</p>
                        <p className="text-xs text-gray-500">{s.mobile||'—'}{s.wechat ? ` · ${s.wechat}` : ''}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                        <p className="text-xs text-gray-400">当前余额</p>
                        <BalBadge n={s.balance}/>
                    </div>
                </div>
            ):null;})()}
            {tuStu && (()=>{
                /* A4: 最近 3 笔充值/退款流水，动手前先核对（v4.7 + v5.5） */
                const s = db.students.find(x=>x.id===tuStu);
                const recent = !s ? [] : db.logs.filter(l =>
                    (l.studentId===s.id || (!l.studentId && l.studentName===s.name)) &&
                    (l.action==='充值购课' || l.action==='退款退课')).slice(0,3);
                if (!recent.length) return null;
                return (
                    <div className="mt-2 border border-gray-100 rounded-xl divide-y divide-gray-50 text-xs">
                        {recent.map(l => (
                            <div key={l.id} className="flex items-center justify-between px-3 py-2">
                                <span className={l.action==='退款退课'?'text-red-500 font-bold':'text-gray-600 font-bold'}>{l.action}</span>
                                <span className={`font-bold ${l.action==='退款退课'?'text-red-500':'text-gray-700'}`}>{String(l.change)} 课时 · ${l.feePaid||0}</span>
                                <span className="text-gray-400">{String(l.date).split(',')[0]}</span>
                            </div>
                        ))}
                    </div>
                );
            })()}
        </div>
        {settleMode==='refund' ? (
        <div className="space-y-4">
            <div className="rounded-2xl border border-red-100 bg-red-50/50 p-3 space-y-2">
                <p className="text-sm font-bold text-red-900">先选择原充值</p>
                <p className="text-[11px] text-red-700">退款必须从一笔明确的 purchase 开始；系统不会按学员余额猜来源。</p>
                {refundSourcesBusy && <p className="text-xs text-gray-500">正在加载可退充值…</p>}
                {refundSourceError && <p className="text-xs text-red-600" role="alert">{refundSourceError}</p>}
                {!refundSourcesBusy && !refundSources.filter(source => Number(source.availableCredits || 0) > 0).length && !refundSourceError && (
                    <p className="text-xs text-gray-500">没有剩余课时可退的原充值。已全部退完的来源会保留在账本中，但不会再出现在可选列表。</p>
                )}
                <div className="space-y-2">
                    {refundSources.filter(source => Number(source.availableCredits || 0) > 0).map(source => {
                        const selected = String(source.sourceTransactionId) === String(rfSourceId);
                        return (
                            <button key={source.sourceTransactionId} type="button"
                                onClick={()=>{
                                    setRfSourceId(String(source.sourceTransactionId));
                                    setRfCr(String(source.availableCredits || ''));
                                    setRfAmt((Number(source.availableAmountCents || 0) / 100).toFixed(2));
                                    setRfAmountTouched(false);
                                    setRfAdjustDocuments(Boolean(source.syncAvailable && canSyncRefund));
                                }}
                                className={`w-full text-left rounded-xl border p-3 min-h-[68px] ${selected ? 'border-red-400 bg-white ring-2 ring-red-100' : 'border-gray-200 bg-white'}`}>
                                <div className="flex items-start gap-2">
                                    <span className="flex-1 min-w-0">
                                        <span className="block text-xs font-bold text-gray-800 truncate">
                                            {source.invoiceNumber || 'Credits-only purchase'} · {source.purchasedCredits} 课时
                                        </span>
                                        <span className="block text-[11px] text-gray-500 mt-1">
                                            剩余 {source.availableCredits} 节 · 可退 ${(Number(source.availableAmountCents || 0) / 100).toFixed(2)} · 已退 {source.refundCount} 次
                                        </span>
                                    </span>
                                    <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${source.syncAvailable ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                                        {source.syncAvailable ? '可同步单据' : '无完整桥接'}
                                    </span>
                                </div>
                                <span className="block text-[11px] text-gray-400 mt-1">
                                    发票 {source.invoiceStatus || '—'} · 付款 {source.paymentStatus || '—'}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">退课节数 *</label>
                    <input type="number" min="0.01" step="0.01" required value={rfCr} onChange={e=>{
                        const next = e.target.value;
                        setRfCr(next);
                        if (!rfAmountTouched) {
                            const selectedSource = refundSources.find(item => String(item.sourceTransactionId) === String(rfSourceId));
                            const credits = Number(next || 0);
                            const availableCredits = Number(selectedSource?.availableCredits || 0);
                            const availableAmount = Number(selectedSource?.availableAmountCents || 0);
                            if (selectedSource && availableCredits > 0) setRfAmt((availableAmount * credits / availableCredits / 100).toFixed(2));
                        }
                    }}
                        className="w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"/>
                </div>
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">退款金额 (AUD) *</label>
                    <input type="number" min="0" step="0.01" required value={rfAmt} onChange={e=>{ setRfAmountTouched(true); setRfAmt(e.target.value); }}
                    className="w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"/>
                </div>
            </div>
            {(() => {
                const source = refundSources.find(item => String(item.sourceTransactionId) === String(rfSourceId));
                const credits = Number(rfCr || 0);
                const availableCredits = Number(source?.availableCredits || 0);
                const suggested = source && availableCredits > 0
                    ? Math.round(Number(source.availableAmountCents || 0) * credits / availableCredits)
                    : 0;
                const actual = Math.round((parseFloat(rfAmt) || 0) * 100);
                const variance = actual - suggested;
                return source && Number.isFinite(variance) && Math.abs(variance) > 0 ? (
                    <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2" role="status">
                        按原充值未退比例建议退款 {`$${(suggested / 100).toFixed(2)}`}；当前人工金额 {`$${(actual / 100).toFixed(2)}`}，偏差 {`${variance > 0 ? '+' : ''}$${(variance / 100).toFixed(2)}`}。请确认有效单价并填写退款原因，系统不会替你猜税务决定。
                    </p>
                ) : null;
            })()}
            {(() => {
                const source = refundSources.find(item => String(item.sourceTransactionId) === String(rfSourceId));
                return (
                    <label className="flex items-start gap-2.5 min-h-[44px] rounded-xl border border-red-100 bg-white p-3 cursor-pointer">
                        <input type="checkbox" checked={rfAdjustDocuments}
                            disabled={!canSyncRefund || !source?.syncAvailable}
                            onChange={event=>setRfAdjustDocuments(event.target.checked)}
                            className="mt-1 w-5 h-5 accent-red-600" />
                        <span className="flex-1 text-sm font-bold text-red-900">
                            同步处理原发票与付款
                            <span className="block text-[11px] font-normal text-red-700 mt-0.5">
                                {!source ? '先选择一笔原充值。' : source.syncAvailable && canSyncRefund ? '将同时开具贷记单、登记付款退款并保留桥接证据。' : '没有完整 bridge，或当前角色缺少 credits:refund / payments:refund / billing:issue。'}
                            </span>
                        </span>
                    </label>
                );
            })()}
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1.5 block">退款方式</label>
                <div className="flex gap-2 flex-wrap">
                    {['现金','微信','银行转账','其他'].map(pm => (
                        <button key={pm} type="button" onClick={()=>setTuPay(pm)}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay===pm?'border-red-400 bg-red-50 text-red-700':'border-gray-200 bg-white text-gray-600 active:border-red-300'}`}>{pm}</button>
                    ))}
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">退款原因 *</label>
                <input type="text" required value={rfReason} onChange={e=>setRfReason(e.target.value)} placeholder="如 搬家、时间冲突、课程不合适..."
                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm"/>
            </div>
            <p className="text-xs text-gray-400 bg-red-50 border border-red-100 rounded-xl px-3 py-2">勾选同步时会生成贷记单并调整付款；不勾选时只改课时账本和现金净额，不会改变发票或付款记录。所有操作都会记入账本与操作日志。</p>
        </div>
        ) : (
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1.5 block">套餐快选</label>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mb-4">
                {(db.packages||[]).map(pkg => (
                    <button key={pkg.id} type="button" onClick={()=>{
                        if (tuPkg===String(pkg.id)) { setTuCr(''); setTuFee(''); setTuPkg(''); }
                        else { setTuCr(String(pkg.credits)); setTuFee(String(pkg.price)); setTuPkg(String(pkg.id)); }
                    }}
                        className={`py-3 px-2 border-2 rounded-xl text-sm font-bold min-h-[50px] ${tuPkg===String(pkg.id)?'border-indigo-500 bg-indigo-100 text-indigo-900':'border-indigo-200 bg-indigo-50 active:bg-indigo-100 text-indigo-800'}`}>
                        {pkg.name}<br/><span className="font-normal text-xs">{pkg.credits}课时 · ${pkg.price}</span>
                    </button>
                ))}
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">课时数 *</label>
                    <input type="number" name="credits" min="1" required value={tuCr} onChange={e=>setTuCr(e.target.value)}
                        className="w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                </div>
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">实收金额 (AUD) *</label>
                    <input type="number" name="fee" min="0" step="0.01" required value={tuFee} onChange={e=>setTuFee(e.target.value)}
                        className="w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-green-700"/>
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1.5 block">付款方式</label>
                <div className="flex gap-2 flex-wrap">
                    {['现金','微信','银行转账','其他'].map(pm => (
                        <button key={pm} type="button" onClick={()=>setTuPay(pm)}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay===pm?'border-indigo-500 bg-indigo-100 text-indigo-900':'border-gray-200 bg-white text-gray-600 active:border-indigo-300'}`}>{pm}</button>
                    ))}
                </div>
            </div>
            {TENANT_SLUG && canUseSettlementBilling && (
                <div className="space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-3">
                    <label className="flex items-start gap-2.5 min-h-[44px] cursor-pointer">
                        <input type="checkbox" checked={tuCreateInvoice}
                            disabled={Number(tuFee || 0) <= 0}
                            onChange={event=>setTuCreateInvoice(event.target.checked)}
                            className="mt-1 w-5 h-5 accent-indigo-600" />
                        <span className="flex-1 text-sm font-bold text-indigo-900">
                            同时创建发票
                            <span className="block text-[11px] font-normal text-indigo-700 mt-0.5">只有金额大于 0 才能开票；开具后金额和抬头会冻结。</span>
                        </span>
                    </label>
                    {tuCreateInvoice && (
                        <>
                            <BillingAccountPicker api={v1Api} accounts={settlementAccounts}
                                students={sortedAZ} studentPicker={StudentPicker}
                                initialStudentId={tuStu || ''} hideStudentSelector
                                value={settlementPayerState.accountId}
                                onStateChange={setSettlementPayer}
                                payerError={settlementPayerError}
                                onPayerError={setSettlementPayerError} />
                            <p className="text-[11px] text-indigo-700">
                                {settlementTaxCodes.length
                                    ? `税码：${(settlementTaxCodes.find(code=>code.is_default)||settlementTaxCodes[0]).code} · ${Number((settlementTaxCodes.find(code=>code.is_default)||settlementTaxCodes[0]).rate_bp || 0) / 100}%`
                                    : '当前未配置税码，发票将按 0% 税率计算。'}
                            </p>
                            <label className="flex items-start gap-2.5 min-h-[44px] cursor-pointer">
                                <input type="checkbox" checked={tuPaymentReceived}
                                    disabled={!canRegisterSettlementPayment || Number(tuFee || 0) <= 0}
                                    onChange={event=>setTuPaymentReceived(event.target.checked)}
                                    className="mt-1 w-5 h-5 accent-indigo-600" />
                                <span className="flex-1 text-sm font-bold text-indigo-900">
                                    款项已经收到，同时登记付款
                                    <span className="block text-[11px] font-normal text-indigo-700 mt-0.5">关闭后只开具未付款发票，不会猜测或冲销旧发票。</span>
                                </span>
                            </label>
                        </>
                    )}
                </div>
            )}
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">备注 <span className="font-normal text-gray-400">选填</span></label>
                <input type="text" name="tuRemark" placeholder="如 节假日赠课、补偿调课..."
                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"/>
            </div>
        </div>
        )}
        <button type="submit" disabled={busy||!tuStu}
            className={`w-full disabled:bg-gray-300 text-white py-4 rounded-xl font-bold text-sm shadow-xl min-h-[56px] ${settleMode==='refund'?'bg-red-500 active:bg-red-600':'bg-indigo-600 active:bg-indigo-700'}`}>
            {busy?'处理中...':(settleMode==='refund'?'确认退款退课':'确认收款并入账')}
        </button>
    </form>
</div>
    );
}
