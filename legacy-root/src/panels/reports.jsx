/* 记录与统计 — 操作日志、经营统计。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { BarChart, Icon, StudentPicker, fmtMK } from "../components.jsx";
import { FilterBar } from "./filter_bar.jsx";

export function LogsSection(props) {
    const {
        canManageOperations, displayNote, exportLogsCSV, filteredLogs, lAct, lDateFrom,
        lDateTo, lPage, lSrch, lStu, logActions, logPageCount,
        pagedLogs, setLAct, setLDateFrom, setLDateTo, setLPage, setLSrch,
        setLStu, sortedAZ,
    } = props;
    return (
<div className="anim space-y-4">
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="scroll" className="w-4 h-4"/>操作日志</h2>
    {/* 日志页接上共享筛选栏。它原本是六页里唯一自带「清除」的一页，
        其余四页各写各的 —— 现在计数与清除由 FilterBar 统一提供，
        学员选择器和操作下拉走 extra 插槽，一样能力不丢。 */}
    <FilterBar
        range={{start:lDateFrom, end:lDateTo}}
        onRange={(next)=>{ setLDateFrom(next.start||''); setLDateTo(next.end||''); }}
        query={lStu ? null : lSrch} onQuery={setLSrch}
        searchPlaceholder="或输入关键字搜索…"
        total={filteredLogs.length} totalNoun="条"
        extraDirty={Boolean(lStu || lAct)}
        onClearExtra={()=>{ setLStu(null); setLAct(''); }}
        extra={
            <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                    <StudentPicker students={sortedAZ} value={lStu} onChange={setLStu} placeholder="精确筛选学员…" showBal={false}/>
                </div>
                <select value={lAct} onChange={e=>setLAct(e.target.value)}
                    className="px-3 py-3 border border-gray-200 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none min-h-[44px]">
                    <option value="">全部操作</option>
                    {logActions.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
            </div>
        } />
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        {/* Quick date presets */}
        <div className="flex flex-wrap gap-2">
            {[
                {l:'本月',    fn:()=>{ const n=new Date(); const y=n.getFullYear(),m=String(n.getMonth()+1).padStart(2,'0'); setLDateFrom(`${y}-${m}-01`); setLDateTo(`${y}-${m}-${String(new Date(y,n.getMonth()+1,0).getDate()).padStart(2,'0')}`); }},
                {l:'近30天',  fn:()=>{ const t=new Date(),f=new Date(t-30*864e5); setLDateFrom(f.toLocaleDateString('en-CA')); setLDateTo(t.toLocaleDateString('en-CA')); }},
                {l:'本年',    fn:()=>{ const y=new Date().getFullYear(); setLDateFrom(`${y}-01-01`); setLDateTo(`${y}-12-31`); }},
            ].map(({l,fn})=>(
                <button key={l} type="button" onClick={fn}
                    className="px-3 py-1.5 bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold min-h-[44px]">{l}</button>
            ))}
        </div>
        {/* 日期范围、清除与计数都归 FilterBar 了；这里只留导出。 */}
        {canManageOperations && (
            <div className="flex">
                <button onClick={exportLogsCSV}
                    className="inline-flex items-center gap-1.5 ml-auto bg-white border border-gray-200 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-xs min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
            </div>
        )}
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead><tr className="border-b-2 border-gray-100 text-gray-400 text-xs">
                    <th className="p-3 font-bold">时间</th>
                    <th className="p-3 font-bold">学员</th>
                    <th className="p-3 font-bold">操作</th>
                    <th className="p-3 font-bold">变动</th>
                </tr></thead>
                <tbody>
                    {pagedLogs.map(l => (
                        <tr key={l.id} className="border-b border-gray-50 hover-row">
                            <td className="p-3 text-gray-400 text-xs font-mono whitespace-nowrap">{l.date}</td>
                            <td className="p-3 font-bold text-gray-800 text-sm">{l.studentName}</td>
                            <td className="p-3">
                                <span className={`px-1.5 py-0.5 rounded text-xs font-bold border ${l.action==='充值购课'?'bg-green-100 text-green-700 border-green-200':l.action==='上课签到'?'bg-indigo-100 text-indigo-700 border-indigo-200':l.action&&l.action.includes('手动')?'bg-orange-100 text-orange-700 border-orange-200':l.action&&(l.action.includes('拒绝')||l.action.includes('删除'))?'bg-red-100 text-red-700 border-red-200':'bg-gray-100 text-gray-700 border-gray-200'}`}>{l.action}</span>
                                {l.payMethod && <span className="ml-1 bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-xs">{l.payMethod}</span>}
                                <span className="text-xs text-gray-400 block mt-0.5">{displayNote(l.note)}</span>
                                {l.actorEmail && <span className="text-xs text-gray-400 block">操作人：{l.actorEmail}</span>}
                                {l.feePaid>0 && <span className="text-xs text-green-600 font-bold">${l.feePaid}</span>}
                            </td>
                            <td className={`p-3 font-bold ${String(l.change).startsWith('-')?'text-orange-500':(l.change==='0'||l.change===0)?'text-gray-400':'text-green-500'}`}>{l.change}</td>
                        </tr>
                    ))}
                    {!pagedLogs.length && <tr><td colSpan="4" className="p-8 text-center text-gray-400">无记录</td></tr>}
                </tbody>
            </table>
        </div>
        {/* Fix #10: first/last page buttons */}
        {logPageCount>1 && (
            <div className="p-3 border-t flex items-center justify-center gap-1.5">
                <button disabled={lPage===1} onClick={()=>setLPage(1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">«</button>
                <button disabled={lPage===1} onClick={()=>setLPage(p=>p-1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">‹</button>
                <span className="text-sm text-gray-600 px-2">{lPage} / {logPageCount}</span>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(p=>p+1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">›</button>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(logPageCount)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">»</button>
            </div>
        )}
    </div>
</div>
    );
}


export function StatsSection(props) {
    const {
        analytics, bizReport, exportBizCSV, exportRevenueCSV, payBreakdown, sFrom,
        sPeriod, sStu, sStu2, sTo, sYear, setSFrom,
        setSPeriod, setSStu, setSStu2, setSTo, setSYear, sortedAZ,
        statsData, studentStats,
    } = props;
    return (
<div className="anim space-y-5">
    <h2 className="md:hidden text-xl font-bold text-gray-800 flex items-center gap-2"><Icon name="trend" className="w-6 h-6"/> 经营统计</h2>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 p-4 rounded-2xl text-white shadow-md">
            <p className="text-indigo-100 text-xs mb-1">历史总营收</p><p className="text-2xl md:text-3xl font-bold">${analytics.totalRevenue.toFixed(0)}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">建档学员</p><p className="text-2xl md:text-3xl font-bold text-gray-800">{analytics.totalStudents}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">累计消课</p><p className="text-2xl md:text-3xl font-bold text-indigo-600">{analytics.totalCheckins}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">课时资产池</p><p className="text-2xl md:text-3xl font-bold text-emerald-600">{analytics.totalBalance}</p></div>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
                <p className="font-bold text-gray-700 text-sm">近 12 个月营收 (AUD)</p>
                {sStu && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">全局数据</span>}
            </div>
            <div className="overflow-x-auto -mx-1 px-1"><div style={{minWidth:'580px'}}>
            <BarChart items={analytics.chart12.map(d=>({v:d.rev,l:d.l}))} color="var(--info)" h={130}/>
            </div></div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
                <p className="font-bold text-gray-700 text-sm">近 12 个月消课次数</p>
                {sStu && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">全局数据</span>}
            </div>
            <div className="overflow-x-auto -mx-1 px-1"><div style={{minWidth:'580px'}}>
            <BarChart items={analytics.chart12.map(d=>({v:d.ci,l:d.l}))} color="var(--success)" h={130}/>
            </div></div>
        </div>
    </div>
    {payBreakdown.length>0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <p className="font-bold text-gray-700 text-sm mb-3">付款方式分布</p>
            <div className="flex flex-wrap gap-3">
                {payBreakdown.map(([pm,d]) => (
                    <div key={pm} className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 text-center min-w-[90px]">
                        <p className="text-xs text-gray-400 mb-1">{pm}</p>
                        <p className="font-bold text-gray-800">${d.revenue.toFixed(0)}</p>
                        <p className="text-xs text-gray-400">{d.count} 次</p>
                    </div>
                ))}
            </div>
        </div>
    )}
    {/* F7: 经营月报 */}
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center justify-between mb-3">
            <p className="inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm"><Icon name="dashboard" className="w-4 h-4"/>经营月报（近 6 个月）</p>
            <button onClick={exportBizCSV}
                className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="download" className="w-4 h-4"/>导出 CSV</button>
        </div>
        <div className="overflow-x-auto"><table className="w-full text-sm" style={{minWidth:'480px'}}>
            <thead><tr className="text-xs text-gray-400 border-b">
                <th className="text-left py-2 px-2">月份</th><th className="text-right px-2">营收</th>
                <th className="text-right px-2">充值</th><th className="text-right px-2">消课</th>
                <th className="text-right px-2">新学员</th></tr></thead>
            <tbody>{bizReport.rows.map(r=>(
                <tr key={r.k} className="border-b border-gray-50">
                    <td className="py-2 px-2 font-bold text-gray-700">{r.label}</td>
                    <td className="text-right px-2 font-bold text-indigo-700">${r.rev.toFixed(0)}</td>
                    <td className="text-right px-2 text-gray-600">{r.topups} 笔</td>
                    <td className="text-right px-2 text-gray-600">{r.ci} 次</td>
                    <td className="text-right px-2 text-gray-600">{r.newStu||'—'}</td>
                </tr>))}</tbody>
        </table></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
            <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                <p className="text-xs font-bold text-gray-500 mb-2">课包销量排行（历史累计）</p>
                {bizReport.pkgRank.length===0 && <p className="text-xs text-gray-400">暂无充值记录</p>}
                {bizReport.pkgRank.slice(0,5).map(([name,d],i)=>(
                    <div key={name} className="flex items-center justify-between py-1 text-sm">
                        <span className="text-gray-700">{i+1}. {name}</span>
                        <span className="font-bold text-gray-800">${d.revenue.toFixed(0)} <span className="text-xs text-gray-400 font-normal">/ {d.count} 笔</span></span>
                    </div>))}
            </div>
            <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                <p className="text-xs font-bold text-gray-500 mb-2">消课节奏（近 180 天）</p>
                <p className="text-2xl font-bold text-emerald-600">{bizReport.avgGap ? bizReport.avgGap.toFixed(1) : '—'} <span className="text-sm font-normal text-gray-500">天/次</span></p>
                <p className="text-xs text-gray-400 mt-1">规律上课学员 {bizReport.regularStu} 人的平均上课间隔。间隔变长 = 出勤率下降的早期信号</p>
            </div>
        </div>
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                <h3 className="font-bold text-gray-800">财务明细报表</h3>
                <div className="flex items-center gap-2">
                    <button onClick={exportRevenueCSV}
                        className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-sm min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
                        {[['monthly','月度'],['yearly','年度'],['custom','自定义']].map(([v,l]) => (
                            <button key={v} onClick={()=>setSPeriod(v)} className={`px-3 py-2 rounded-lg text-sm font-bold min-h-[44px] ${sPeriod===v?'bg-white shadow text-indigo-700':'text-gray-500'}`}>{l}</button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap gap-3 items-center">
                {sPeriod==='monthly' && (
                    <select value={sYear} onChange={e=>setSYear(e.target.value)}
                        className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-400 outline-none text-sm min-h-[44px]">
                        <option value="all">所有年份</option>
                        {analytics.availYears.map(y=><option key={y} value={y}>{y}年</option>)}
                    </select>
                )}
                {sPeriod==='custom' && (
                    /* Fix ⑩: type="month" gives YYYY-MM value, matches our monthKey format exactly */
                    <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm">
                        <span className="font-medium text-gray-500">自定义范围</span>
                        <div className="flex items-center gap-2">
                            <input type="month" value={sFrom} onChange={e=>setSFrom(e.target.value)} className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]"/>
                            <span className="text-gray-400 text-xs">至</span>
                            <input type="month" value={sTo}   onChange={e=>setSTo(e.target.value)}   className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]"/>
                        </div>
                    </div>
                )}
                <div className="flex items-center gap-2 ml-auto">
                    <span className="text-sm text-gray-500">筛选:</span>
                    <div className="w-48"><StudentPicker students={sortedAZ} value={sStu} onChange={setSStu} placeholder="全部学员" showBal={false}/></div>
                </div>
            </div>
            {statsData.rows.length>0 && (
                <div className="flex gap-4 text-sm">
                    <span className="text-gray-500">合计: <span className="font-bold text-green-600">${statsData.totalRev.toFixed(2)}</span></span>
                    <span className="text-gray-500">消课: <span className="font-bold text-indigo-600">{statsData.totalCI} 次</span></span>
                    {statsData.totalCI>0 && <span className="text-gray-500">均价/课: <span className="font-bold">${(statsData.totalRev/statsData.totalCI).toFixed(1)}</span></span>}
                </div>
            )}
        </div>
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead><tr className="border-b border-gray-100 text-gray-400 text-xs">
                    <th className="p-3 font-bold">周期</th><th className="p-3 font-bold">入账流水</th>
                    <th className="p-3 font-bold">消课</th><th className="p-3 font-bold">充值次数</th><th className="p-3 font-bold">均价/课</th>
                </tr></thead>
                <tbody>
                    {statsData.rows.map(r => (
                        <tr key={r.key} className="border-b border-gray-50 hover-row text-sm">
                            <td className="p-3 font-bold text-gray-700">{sPeriod==='yearly'?`${r.key}年`:fmtMK(r.key)}</td>
                            <td className="p-3 font-bold text-green-600">${r.revenue.toFixed(2)}</td>
                            <td className="p-3 font-bold text-indigo-600">{r.checkins}</td>
                            <td className="p-3 text-gray-600">{r.topups}</td>
                            <td className="p-3 text-gray-500">{r.checkins>0?`$${(r.revenue/r.checkins).toFixed(1)}`:'-'}</td>
                        </tr>
                    ))}
                    {!statsData.rows.length && <tr><td colSpan="5" className="p-8 text-center text-gray-400">暂无数据</td></tr>}
                </tbody>
            </table>
        </div>
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b p-4">
            <h3 className="font-bold text-gray-800 mb-3">学员个人分析</h3>
            <div className="max-w-xs"><StudentPicker students={sortedAZ} value={sStu2} onChange={setSStu2} placeholder="选择学员查看详情..." showBal/></div>
        </div>
        {studentStats ? (
            <div className="p-4 space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    {[{l:'当前余额',v:`${studentStats.student.balance} 课时`,c:'text-indigo-700'},
                      {l:'累计消课',v:`${studentStats.checkins} 次`,c:'text-gray-700'},
                      {l:'累计购课',v:`${studentStats.totalBought} 课时`,c:'text-gray-700'},
                      {l:'累计消费',v:`$${studentStats.totalSpent.toFixed(0)}`,c:'text-green-600'},
                      {l:'充值次数',v:`${studentStats.topupCount} 次`,c:'text-gray-700'},
                    ].map(({l,v,c}) => (
                        <div key={l} className="bg-gray-50 p-3 rounded-xl border border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">{l}</p>
                            <p className={`text-lg font-bold ${c}`}>{v}</p>
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm text-gray-500">
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="phone" className="w-4 h-4"/>{studentStats.student.mobile||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="mail" className="w-4 h-4"/>{studentStats.student.email||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="target" className="w-4 h-4"/>首次: {studentStats.first?String(studentStats.first).split(',')[0]:'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="clock" className="w-4 h-4"/>最近: {studentStats.last?String(studentStats.last).split(',')[0]:'—'}</div>
                </div>
                {studentStats.student.remark && <div className="bg-gray-50 p-3 rounded-xl text-sm text-gray-600 border border-gray-100 inline-flex items-start gap-1.5"><Icon name="note" className="w-4 h-4"/>{studentStats.student.remark}</div>}
                <div className="border border-gray-100 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-3 py-2 text-xs font-bold text-gray-600 border-b">交易记录 ({studentStats.logs.length})</div>
                    <div className="divide-y divide-gray-50 max-h-56 overflow-y-auto sl">
                        {studentStats.logs.slice(0,50).map(l => (
                            <div key={l.id} className="px-3 py-2.5 flex justify-between text-sm min-h-[44px] items-center">
                                <div><span className="font-medium text-gray-700">{l.action}</span> {l.payMethod&&<span className="text-blue-500 ml-1 text-xs">{l.payMethod}</span>} <span className="text-gray-400 text-xs">{l.note}</span></div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                    {l.feePaid>0 && <span className="text-green-600 font-bold text-xs">${l.feePaid}</span>}
                                    <span className={`font-bold text-xs ${String(l.change).startsWith('-')?'text-orange-500':'text-green-500'}`}>{l.change}</span>
                                    <span className="text-gray-400 text-xs">{String(l.date).split(',')[0]}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        ) : <div className="p-10 text-center text-gray-400 text-sm">选择一名学员查看个人数据</div>}
    </div>
</div>
    );
}
