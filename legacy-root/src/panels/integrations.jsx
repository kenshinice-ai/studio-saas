/* 集成 —— Xero 与支付通道。
 *
 * Xero 在界面上必须是三处，因为它在后端就是三处：
 *
 *   开关一 · 权利  平台侧授予（tenant_addons），租户这里只读
 *   开关二 · 连接  租户 owner 授权自己的 Xero 组织
 *   开关三 · 推送  一道闸，不是勾选框
 *
 * 合成一个开关的后果是三种正常情况互相误伤：加购到期会顺手断开连接，
 * 换会计看起来像退订，年末封账要去找平台方。
 *
 * 开关三的三个前置条件在数据库里是 CHECK 约束（0037），不是这里的判断。
 * 所以这个界面的工作不是"验证"，是把约束**说清楚** —— 灰掉的开关加一句
 * 还差什么，而不是一个点了会报错的按钮。
 */

import { fmtApiDate } from "./_shared.jsx";

const { useState, useEffect, useCallback } = React;

const BLOCKER_TEXT = {
  addon_not_active: '尚未开通 Xero 加购 —— 这一项由平台方授予',
  not_connected: '还没有连接到 Xero 组织',
  mapping_not_confirmed: '科目与税率映射还没有确认',
  demo_run_not_completed: '还没有在 Xero 测试组织跑通一个完整周期',
  single_entry_not_answered: '还没有回答「是否已有别的通道在同步」',
  transport_not_available: '当前版本尚未接入 Xero transport',
};

function Step({ n, done, active, title, children }) {
  const badge = done
    ? 'bg-green-50 text-green-700 border-green-200'
    : active
    ? 'bg-indigo-600 text-white border-indigo-600'
    : 'bg-gray-100 text-gray-500 border-gray-200';
  return (
    <div className={`flex gap-3 items-start p-3 rounded-xl border ${active ? 'border-indigo-200 bg-indigo-50' : 'border-gray-200 bg-white'}`}>
      <span className={`w-7 h-7 rounded-full grid place-items-center text-xs font-bold border flex-none ${badge}`}>
        {done ? '✓' : n}
      </span>
      <div className="text-xs min-w-0">
        <p className="font-bold mb-0.5">{title}</p>
        <div className="text-gray-600">{children}</div>
      </div>
    </div>
  );
}

export function IntegrationsPanel({ api, showToast, canManage }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [queue, setQueue] = useState(null);
  const [mapDraft, setMapDraft] = useState(null);
  const [demoReport, setDemoReport] = useState(null);
  const [reconcileReport, setReconcileReport] = useState(null);

  const load = useCallback(async () => {
    try {
      const st = await api('/integrations/xero');
      setState(st);
      setError('');
      /* 映射编辑器的草稿以服务端为准初始化一次；正在编辑时不覆盖。 */
      setMapDraft(prev => prev || Object.fromEntries(
        (st.mappableKinds || []).map(k => {
          const row = (st.mappings || []).find(m => m.item_kind === k) || {};
          return [k, { accountCode: row.account_code || '', taxType: row.tax_type || '' }];
        })
      ));
      if (st.transportAvailable) {
        try { setQueue(await api('/integrations/xero/queue')); } catch { /* 队列读不动不阻塞主状态 */ }
      }
    } catch (e) {
      /* 读路径不把设置页打挂：没开通加购只是"没买"，不是故障。 */
      setError(e.status === 403 ? '' : `集成状态加载失败：${e.message}`);
      setState(null);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  /* X2: the OAuth callback lands back here with ?xero=connected|cancelled|
     error. Toast once, then strip the params so a reload doesn't re-toast. */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const flag = params.get('xero');
    if (!flag) return;
    const message = params.get('xeroMessage') || '';
    if (flag === 'connected') showToast('Xero 已连接', 'success');
    else if (flag === 'cancelled') showToast('已取消 Xero 授权，未做任何更改', 'warn');
    else showToast(`Xero 连接失败：${message || '未知原因'}`, 'warn');
    params.delete('xero'); params.delete('xeroMessage');
    const rest = params.toString();
    window.history.replaceState({}, '', window.location.pathname + (rest ? `?${rest}` : ''));
    // The toast is enough; load() below already runs on mount and reflects state.
  }, []);

  const [armDisconnect, setArmDisconnect] = useState(false);
  const connectNow = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const d = await api('/integrations/xero/connect-url', { method: 'POST', body: '{}' });
      /* Full-page navigation, not a popup: Xero's consent screen owns the
         next step, and the callback route brings the operator back here. */
      window.location.href = d.url;
    } catch (e) {
      showToast(e.message, 'warn');
      setBusy(false);
    }
  };
  const disconnectNow = async () => {
    if (busy) return;
    if (!armDisconnect) { setArmDisconnect(true); return; }
    setBusy(true);
    try {
      await api('/integrations/xero/disconnect', { method: 'POST', body: '{}' });
      showToast('已断开 Xero 连接', 'success');
      await load();
    } catch (e) {
      showToast(e.message, 'warn');
    } finally { setBusy(false); setArmDisconnect(false); }
  };
  const refreshCheck = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api('/integrations/xero/refresh-check', { method: 'POST', body: '{}' });
      showToast('令牌有效（必要时已自动续期）', 'success');
      await load();
    } catch (e) {
      showToast(`令牌检查未通过：${e.message}`, 'warn');
      await load();
    } finally { setBusy(false); }
  };

  const step = async (name, extra = {}) => {
    if (busy) return;
    setBusy(true);
    try {
      const body = name === 'single_entry'
        ? JSON.stringify(extra)
        : JSON.stringify({ step: name });
      const path = name === 'single_entry'
        ? '/integrations/xero/single-entry'
        : '/integrations/xero/gate';
      await api(path, { method: 'POST', body });
      await load();
      showToast('已更新', 'success');
    } catch (e) {
      showToast(e.message, 'warn');
    } finally {
      setBusy(false);
    }
  };

  const saveMappings = async () => {
    if (busy || !mapDraft) return;
    setBusy(true);
    try {
      const mappings = Object.entries(mapDraft).map(([itemKind, v]) => ({
        itemKind, accountCode: v.accountCode.trim(), taxType: v.taxType.trim(),
      }));
      await api('/integrations/xero/mappings', { method: 'PUT', body: JSON.stringify({ mappings }) });
      showToast('映射已保存', 'success');
      await load();
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  const demoRun = async () => {
    if (busy) return;
    setBusy(true);
    setDemoReport(null);
    try {
      const r = await api('/integrations/xero/gate', { method: 'POST', body: JSON.stringify({ step: 'demo_run' }) });
      setDemoReport(r.demoRun || null);
      showToast(r.ok ? '试跑通过：全部推送成功，对账 0 差异' : '试跑未通过，看下方报告', r.ok ? 'success' : 'warn');
      await load();
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  const pushNow = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api('/integrations/xero/push-now', { method: 'POST', body: '{}' });
      showToast(`已处理 ${r.processed} 项：成功 ${r.sent}，失败 ${r.failed}，稍后重试 ${r.deferred}`, r.failed ? 'warn' : 'success');
      await load();
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  const backfillNow = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api('/integrations/xero/backfill', { method: 'POST', body: '{}' });
      showToast(`已排队 ${r.queued.total} 张（发票 ${r.queued.invoice} / 贷记 ${r.queued.credit_note} / 收款 ${r.queued.payment}）`, 'success');
      await load();
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  const replayJob = async (jobId) => {
    if (busy) return;
    setBusy(true);
    try {
      await api(`/integrations/xero/errors/${jobId}/replay`, { method: 'POST', body: '{}' });
      showToast('已重新入队（沿用同一幂等键）', 'success');
      await load();
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  const runReconcile = async () => {
    if (busy) return;
    setBusy(true);
    setReconcileReport(null);
    try {
      const r = await api('/integrations/xero/reconciliation');
      setReconcileReport(r);
      showToast(r.diffCount === 0 ? `对账通过：${r.checked} 张全部一致` : `发现 ${r.diffCount} 处差异`, r.diffCount === 0 ? 'success' : 'warn');
    } catch (e) { showToast(e.message, 'warn'); } finally { setBusy(false); }
  };

  if (error) return <p className="text-xs text-red-600">{error}</p>;
  if (!state) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <p className="text-xs font-bold mb-1">Xero 预接入（Preview）</p>
        <p className="text-[11px] text-gray-600">
          当前版本只展示接入准备状态，不会向 Xero 发送任何数据。
          映射、连接与 gate 状态会保留，真实 transport 上线后再开放生产操作。
        </p>
      </div>
    );
  }

  const s = state.settings || {};
  const blockers = state.blockers || [];
  const has = (key) => !blockers.includes(key);
  const transportAvailable = state.transportAvailable === true;
  const preview = !transportAvailable;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-bold">{preview ? 'Xero 预接入（Preview）' : 'Xero 集成'}</p>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap
          ${preview ? 'bg-blue-50 text-blue-700 border-blue-200' : state.pushEnabled ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-100 text-gray-600 border-gray-200'}`}>
          {preview ? '预览状态 · 不发送数据' : state.pushEnabled ? '推送已开启' : '推送未开启'}
        </span>
        {s.last_pushed_at && (
          <span className="text-[11px] text-gray-500">历史记录：上次推送 {fmtApiDate(s.last_pushed_at)}</span>
        )}
      </div>
      {preview ? (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-[11px] text-blue-900">
          <p className="font-bold mb-1">Xero 预接入说明</p>
          <p>可以连接 / 断开自己的 Xero 组织（建议先用 Demo Company 测试）；当前版本仍不会向 Xero 推送任何单据数据。</p>
        </div>
      ) : (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-[11px] text-blue-900">
          <p className="font-bold mb-1">单向推送</p>
          <p>已开具的发票、贷记单与收款按队列推入你的 Xero 组织；不做双向同步，不从 Xero 回改任何本地单据。
            先用 Demo Company 完成试跑，再连正式账套。</p>
        </div>
      )}

      {/* X2: the real connection card. Config comes from the server env, so
          an unconfigured install says which variable is missing instead of
          hiding the button — a blank here costs an accountant an afternoon. */}
      {(() => {
        const cx = state.connection || {};
        if (!cx.configured) return (
          <div className="rounded-xl border border-gray-200 bg-white p-4 text-[11px] text-gray-600">
            <p className="font-bold text-gray-800 mb-1">Xero 连接 · 服务器未配置</p>
            <p>缺少：{(cx.configMissing || []).join('、') || '凭据'}。请运营方在服务器上运行 deploy/aws/set_xero_env.sh 配置后重启。</p>
          </div>
        );
        if (cx.connected) return (
          <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-[11px] text-green-900">
            <p className="font-bold mb-1">已连接 Xero · {cx.orgName || '组织'}</p>
            <p className="mb-2">连接于 {cx.connectedAt ? cx.connectedAt.slice(0, 10) : '—'}；访问令牌到期后会自动续期。</p>
            {canManage && (
              <span className="flex gap-2 flex-wrap">
                <button type="button" onClick={refreshCheck} disabled={busy}
                        className="min-h-[44px] px-3 rounded-lg border border-green-300 bg-white text-[11px] font-bold text-green-800 disabled:opacity-50">测试令牌自愈</button>
                <button type="button" onClick={disconnectNow} disabled={busy}
                        className={`min-h-[44px] px-3 rounded-lg border text-[11px] font-bold disabled:opacity-50 ${armDisconnect ? 'bg-red-600 text-white border-red-600' : 'border-red-200 bg-white text-red-700'}`}>
                  {armDisconnect ? '再点一次，确认断开' : '断开连接'}
                </button>
                {armDisconnect && <button type="button" onClick={() => setArmDisconnect(false)}
                        className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-[11px] font-bold text-gray-600">取消</button>}
              </span>
            )}
          </div>
        );
        return (
          <div className={`rounded-xl border p-4 text-[11px] ${cx.status === 'expired' || cx.status === 'error' ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-gray-200 bg-white text-gray-700'}`}>
            <p className="font-bold mb-1">
              {cx.status === 'expired' ? 'Xero 连接已过期，需要重新授权'
                : cx.status === 'error' ? 'Xero 连接出错，需要重新授权'
                : cx.status === 'revoked' ? 'Xero 已断开' : '尚未连接 Xero'}
            </p>
            {cx.lastError && <p className="mb-2 text-[10px] opacity-80">{cx.lastError}</p>}
            <p className="mb-2">授权后本工作室即与你的 Xero 组织建立连接（建议先选 Demo Company）；连接本身不推送任何数据。</p>
            {canManage
              ? <button type="button" onClick={connectNow} disabled={busy}
                        className="min-h-[44px] px-4 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50">
                  {cx.status === 'expired' || cx.status === 'error' || cx.status === 'revoked' ? '重新连接 Xero' : '连接 Xero'}
                </button>
              : <p className="text-[10px] text-gray-500">需要 Owner / Manager 权限发起连接。</p>}
          </div>
        );
      })()}

      {/* φ：左边是进度（次要），右边是当前要做的事（主体）。 */}
      <div className="ui-golden-split">
        <div className="grid gap-2 min-w-0">
          <Step n={1} done={state.entitled} title="加购权利">
            {state.entitled ? '已开通' : '由平台方授予，租户侧只读'}
          </Step>
          <Step n={2} done={state.connection?.connected || state.connected}
                active={state.entitled && !(state.connection?.connected || state.connected)} title="连接 Xero">
            {state.connection?.connected
              ? `已连接 ${state.connection.orgName || ''}`
              : '用上方「连接 Xero」按钮授权自己的组织（先用 Demo Company）'}
          </Step>
          <Step n={3} done={has('mapping_not_confirmed')} active={state.connected && !has('mapping_not_confirmed')} title="科目与税率映射">
            {state.missingMappings?.length
              ? `还差：${state.missingMappings.join('、')}`
              : has('mapping_not_confirmed') ? '会计已确认' : '填完后由会计确认'}
          </Step>
          <Step n={4} done={has('demo_run_not_completed')} title="测试组织试跑">
            {has('demo_run_not_completed')
              ? '已跑通一个完整周期'
              : (preview ? '预览版只显示准备状态，不会发起试跑' : '先在 Xero 测试组织跑通，再连生产账套')}
          </Step>
          <Step n={5} done={has('single_entry_not_answered')} title="单一入口">
            {has('single_entry_not_answered')
              ? (s.single_entry_decision === 'clearing_account'
                  ? `走清算账户 ${s.clearing_account_code}`
                  : '已关闭其他通道的同步')
              : '还没有回答'}
          </Step>
        </div>

        <div className="grid gap-3 min-w-0">
          {/* 单一入口的问题必须在开推送之前问出来 —— 两条通道写同一笔钱，
              在正式账套里收拾起来比手工录入还贵。 */}
          {!has('single_entry_not_answered') && state.connected && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-xs font-bold text-red-700 mb-1">先回答这个</p>
              <p className="text-[11px] text-gray-700 mb-2">
                你们的收款渠道（比如 Square）是不是<strong>已经在往同一个 Xero 组织同步</strong>？
                如果是，我们再推一遍，Xero 里就会出现两套记录。
              </p>
              {canManage && !preview && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" disabled={busy}
                          onClick={() => step('single_entry', { decision: 'ours_only' })}
                          className="min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold">
                    已关掉对方的同步
                  </button>
                  <button type="button" disabled={busy}
                          onClick={() => {
                            const code = window.prompt('清算账户科目号');
                            if (code) step('single_entry', { decision: 'clearing_account', clearingAccountCode: code });
                          }}
                          className="min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold">
                    保留，走清算账户
                  </button>
                  </div>
              )}
              {preview && <p className="text-[11px] text-gray-500">预览阶段只读显示，不修改 gate。</p>}
            </div>
          )}

          {/* X3：科目与税率映射编辑器。tuition 与 bank 是硬前置；lesson/manual
              行按 tuition 科目入账（声明的规则，不是静默兜底）。 */}
          {!preview && state.connection?.connected && mapDraft && (
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <p className="text-xs font-bold mb-1">科目与税率映射</p>
              <p className="text-[11px] text-gray-500 mb-2">
                科目号与税率代码来自你的 Xero 账套（会计提供）。必填：tuition（学费收入）、bank（收款入账账户）；
                lesson / manual 行按 tuition 科目入账。
              </p>
              <div className="grid gap-1.5">
                {(state.mappableKinds || []).map(kind => (
                  <div key={kind} className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[11px] w-28 flex-none ${state.requiredKinds?.includes(kind) ? 'font-bold' : 'text-gray-500'}`}>
                      {kind}{state.requiredKinds?.includes(kind) ? ' *' : ''}
                    </span>
                    <input value={mapDraft[kind]?.accountCode || ''} disabled={!canManage || busy}
                           onChange={e => setMapDraft({ ...mapDraft, [kind]: { ...mapDraft[kind], accountCode: e.target.value } })}
                           placeholder="科目号，如 200"
                           className="w-28 min-h-[44px] px-2 rounded-lg border border-gray-300 text-[11px]" />
                    <input value={mapDraft[kind]?.taxType || ''} disabled={!canManage || busy}
                           onChange={e => setMapDraft({ ...mapDraft, [kind]: { ...mapDraft[kind], taxType: e.target.value } })}
                           placeholder="税率代码，如 OUTPUT"
                           className="w-32 min-h-[44px] px-2 rounded-lg border border-gray-300 text-[11px]" />
                  </div>
                ))}
              </div>
              {canManage && (
                <div className="flex gap-2 mt-2 flex-wrap">
                  <button type="button" onClick={saveMappings} disabled={busy}
                          className="min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50">保存映射</button>
                  <button type="button" onClick={() => step('confirm_mapping')} disabled={busy || !!state.missingMappings?.length}
                          className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50">
                    会计已确认映射
                  </button>
                </div>
              )}
              {!!state.missingMappings?.length && (
                <p className="text-[11px] text-amber-700 mt-1.5">还差必填映射：{state.missingMappings.join('、')}</p>
              )}
            </div>
          )}

          {/* X3：测试组织试跑 —— 真推送 + 真对账，干净才算过。 */}
          {!preview && state.connection?.connected && (
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <p className="text-xs font-bold mb-1">测试组织试跑</p>
              <p className="text-[11px] text-gray-600 mb-2">
                把已开具的单据全部推入当前连接的组织（应为 Demo Company），随后逐张读回对账。
                推送成功且对账 0 差异，这一步才算完成。
              </p>
              {canManage && (
                <button type="button" onClick={demoRun} disabled={busy || !has('mapping_not_confirmed')}
                        className="min-h-[44px] px-4 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50">
                  {has('demo_run_not_completed') ? '再跑一次（推送新增单据）' : '开始试跑'}
                </button>
              )}
              {!has('mapping_not_confirmed') && (
                <p className="text-[11px] text-gray-500 mt-1.5">先完成并确认上方映射。</p>
              )}
              {demoReport && (
                <div className={`mt-2 rounded-lg border p-3 text-[11px] ${demoReport.clean ? 'border-green-200 bg-green-50 text-green-900' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>
                  <p className="font-bold">
                    {demoReport.clean ? '试跑通过' : '试跑未通过'} ·
                    排队 {demoReport.queued?.total ?? 0} / 推送 {demoReport.pushed} / 失败 {demoReport.failed} ·
                    对账差异 {demoReport.reconciliation?.diffCount ?? '—'}
                  </p>
                  {(demoReport.jobs || []).filter(j => j.outcome !== 'sent').slice(0, 5).map(j => (
                    <p key={j.id} className="mt-1 opacity-80">{j.kind}: {j.error}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-xs font-bold mb-2">Xero 推送</p>
            {preview ? (
              <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-[11px] text-blue-900">
                <p className="font-bold">当前版本尚未开放生产推送</p>
                <p className="mt-1">Xero transport 尚未上线；不会向 Xero 发送任何数据。</p>
              </div>
            ) : state.canEnablePush ? (
              canManage ? (
                <button type="button" disabled={busy}
                        onClick={() => step(state.pushEnabled ? 'disable_push' : 'enable_push')}
                        className={`min-h-[44px] px-4 rounded-lg text-xs font-bold
                          ${state.pushEnabled ? 'bg-white border border-gray-300 text-gray-700' : 'bg-indigo-600 text-white'}`}>
                  {state.pushEnabled ? '暂停推送' : '开启推送'}
                </button>
              ) : <p className="text-[11px] text-gray-500">需要 owner 权限。</p>
            ) : (
              <>
                {/* 灰掉并说明还差什么，而不是给一个点了会报错的按钮 ——
                    前置条件是 CHECK 约束，点下去只会拿到一个约束错误。 */}
                <button type="button" disabled
                        className="min-h-[44px] px-4 rounded-lg bg-gray-100 text-gray-400 text-xs font-bold cursor-not-allowed">
                  还不能开启
                </button>
                <ul className="mt-2 text-[11px] text-gray-600 list-disc pl-4">
                  {blockers.map(b => <li key={b}>{BLOCKER_TEXT[b] || b}</li>)}
                </ul>
              </>
            )}
            <p className="mt-2 text-[11px] text-gray-500">
              {preview
                ? '已有映射、ID 对应表与错误队列仍可查看；真实 transport 上线后再开放推送。'
                : '暂停只停新的推送。连接、映射、ID 对应表与错误队列都保留，年末封账可以放心用。'}
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-xs font-bold mb-1">推送队列</p>
            {preview ? (
              <p className="text-[11px] text-gray-600">预接入阶段只保留已有历史记录与映射状态；不会创建新的 Xero 推送任务。</p>
            ) : (
              <>
                <p className="text-[11px] text-gray-600 mb-2">
                  队列每 5 分钟自动处理一次。失败的单据带原因列在下面，修好后一键重放 ——
                  重放沿用同一个幂等键，不会在 Xero 里产生第二张。
                  <strong>原因几乎总是会计要改的一处映射。</strong>
                </p>
                {queue?.counts && (
                  <p className="text-[11px] text-gray-700 mb-2">
                    待推 {queue.counts.queued ?? 0} · 失败 {queue.counts.failed ?? 0} · 已推 {queue.counts.sent ?? 0}
                  </p>
                )}
                {canManage && (
                  <div className="flex gap-2 flex-wrap mb-2">
                    <button type="button" onClick={backfillNow} disabled={busy}
                            className="min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50">排队积压单据</button>
                    <button type="button" onClick={pushNow} disabled={busy}
                            className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50">立即推送</button>
                    <button type="button" onClick={runReconcile} disabled={busy}
                            className="min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50">逐张对账</button>
                  </div>
                )}
                {(queue?.jobs || []).filter(j => j.status === 'failed').slice(0, 8).map(j => (
                  <div key={j.id} className="rounded-lg border border-red-200 bg-red-50 p-2 mb-1.5 text-[11px] text-red-900">
                    <p className="font-bold">{j.local_kind} · 第 {j.attempts} 次尝试失败</p>
                    <p className="opacity-90 break-all">{j.last_error}</p>
                    {canManage && (
                      <button type="button" onClick={() => replayJob(j.id)} disabled={busy}
                              className="mt-1 min-h-[44px] px-2.5 rounded-lg border border-red-300 bg-white text-[11px] font-bold text-red-700 disabled:opacity-50">修好了，重放</button>
                    )}
                  </div>
                ))}
                {reconcileReport && (
                  <div className={`rounded-lg border p-2 text-[11px] ${reconcileReport.diffCount === 0 ? 'border-green-200 bg-green-50 text-green-900' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>
                    <p className="font-bold">对账：检查 {reconcileReport.checked} 张，差异 {reconcileReport.diffCount} 处</p>
                    {(reconcileReport.diffs || []).slice(0, 6).map((d, i) => (
                      <p key={i} className="mt-0.5 opacity-90">{d.kind} {d.number} · {d.field}：本地 {String(d.local)} ↔ Xero {String(d.xero)}</p>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
