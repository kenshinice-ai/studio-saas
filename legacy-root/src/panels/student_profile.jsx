/* 学员档案弹窗 — 资料、课时、时间线、作品。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { BalBadge, EmptyState, Icon, PhotoAvatar, PhotoUploader, StudentTimeline } from "../components.jsx";
import { TENANT_SLUG, TabPanel, Tabs, fmtDate, portfolioSrcSet, portfolioThumbSrc } from "../components.jsx";
import { todayISO, v1Api } from "../components.jsx";
import { StudentBillingAccount, StudentProgressReports } from "./student_reports.jsx";

export function StudentProfileModal(props) {
    const {
        accessCodeResult, archiveStudent, attHistory, busy, canPublishProgress, canUseSettlementBilling,
        canWriteAttendance, canWriteCredits, canWritePortfolio, canWriteProgress, canWriteStudents, consentEdit,
        copyText, db, editP, editPhoto, generateStudentAccessCode, handleDelete,
        handleUpdateStudent, isStudentScheduledOn, notify, openGrowthReport, portfolioDoDelete, preferenceProfile,
        preferenceRows, preferenceValue, profileDialogRef, revokeStudentAccessCode, save, savePublicationConsent,
        scheduleStudentToday, selS, setConsentEdit, setEditP, setEditPhoto, setPortEdit,
        setPortLB, setPortUpload, setSelS, setStudentProfileTab, setTab, setTuStu,
        showToast, studentProfileTab, tab, withdrawPublicationConsent, workNoun,
    } = props;
    return (
    <div ref={profileDialogRef} className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm"
        role="dialog" aria-modal="true" aria-labelledby="student-profile-title">
        {/* Fix #7: slide-up sheet on mobile, centered modal on iPad.
            Three fixed bands + one scrolling band: identity / tabs / panel /
            actions. The actions used to be the last thing in the scroll, so
            "加入今日排课" — the most frequent action in the app — sat below a
            portfolio grid and a consent panel. */}
        <div className="bg-white w-full sm:rounded-3xl shadow-2xl overflow-hidden anim border-t sm:border border-gray-200 flex flex-col cms-profile-sheet">
            <div className="flex justify-between items-center p-4 bg-gray-50 border-b flex-shrink-0">
                <div className="flex items-center gap-2.5 min-w-0">
                    <PhotoAvatar photo={selS.photo} name={selS.name} size="sm"/>
                    <h3 id="student-profile-title" className="text-lg font-bold text-gray-900 truncate">{selS.name}</h3>
                    <BalBadge n={selS.balance}/>
                    {selS.archived && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0">归档</span>}
                </div>
                <button onClick={()=>{setSelS(null);setEditP(false);}} aria-label="关闭" className="text-gray-400 active:text-gray-700 text-2xl font-bold p-2 -mr-1 min-h-[44px] min-w-[44px] flex items-center justify-center">×</button>
            </div>
            {/* Grouped by the question being answered, not by field type:
                概览 = who do I call and when were they last here (what the
                front desk needs in the first five seconds); 资料 = is their
                record correct; 记录 = what happened; 作品 = what have they
                made and may we publish it — the consent panel lives HERE
                because consent only ever means "may this piece go public",
                and splitting the two is what made the old stack a wall;
                专区 = can the parent log in, a different audience entirely. */}
            {!editP && <Tabs idBase="student-profile" label="学员档案分类"
                value={studentProfileTab} onChange={setStudentProfileTab}
                className="px-2 bg-white flex-shrink-0"
                items={[
                    {value:'profile', label:'概览', icon:'users'},
                    {value:'details', label:'资料', icon:'clipboard'},
                    {value:'records', label:'记录', icon:'calendar'},
                    ...(canWritePortfolio ? [{value:'portfolio', label:`${workNoun}集`, icon:'image'}] : []),
                    ...(TENANT_SLUG && canWriteStudents ? [{value:'portal', label:'专区', icon:'lock'}] : []),
                ]}/>}
            {/* Fix ⑧: modal-scroll + safe-area bottom padding for iPad Home bar */}
            <div className="modal-scroll cms-profile-body flex-1 min-h-0">
                {!editP ? (
                    <div className="space-y-3">
                        <TabPanel idBase="student-profile" name="profile" active={studentProfileTab==='profile'}>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="phone" className="w-4 h-4"/>电话</p><p className="font-bold text-gray-800">{selS.mobile||'—'}</p></div>
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="calendar" className="w-4 h-4"/>最近上课</p><p className="font-bold text-gray-800">{fmtDate(selS.lastActive)}</p></div>
                        </div>
                        {(selS.wechat||selS.email) && (
                            <div className="grid grid-cols-2 gap-3">
                                {selS.wechat && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="chat" className="w-4 h-4"/>微信号</p><p className="font-bold text-gray-800">{selS.wechat}</p></div>}
                                {selS.email  && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="mail" className="w-4 h-4"/>邮箱</p><p className="font-bold text-gray-800 text-sm break-all">{selS.email}</p></div>}
                            </div>
                        )}
                        {/* 「谁付账、欠多少」和「打给谁」是同一个问题的两半，
                            前台在头五秒里两个都要。归属为空就整块不渲染。 */}
                        {TENANT_SLUG && <StudentBillingAccount api={v1Api} studentId={selS.id}
                            onOpenBilling={(id)=>{ setSelS(null); setTab('billing', {recordId: id}); }} />}
                        {selS.remark && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">备注</p><p className="text-sm text-gray-700 whitespace-pre-wrap">{selS.remark}</p></div>}
                        {!selS.mobile && !selS.wechat && !selS.email && !selS.remark &&
                            <EmptyState icon={<Icon name="phone" className="w-8 h-8"/>} main="还没有联系方式" sub="点击下方「编辑」补充电话、微信或邮箱"/>}
                        </TabPanel>

                        <TabPanel idBase="student-profile" name="details" active={studentProfileTab==='details'}>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                                <p className="text-xs text-gray-400 mb-1">First Name (名)</p>
                                <p className="font-bold text-gray-800">{selS.firstName||selS.name||'—'}</p>
                            </div>
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                                <p className="text-xs text-gray-400 mb-1">Last Name (姓)</p>
                                <p className="font-bold text-gray-800">{selS.lastName||'—'}</p>
                            </div>
                        </div>
                        {(selS.birthday||selS.enrollmentDate) && <div className="grid grid-cols-2 gap-3">
                            {selS.birthday && <div className="bg-pink-50 p-4 rounded-2xl border border-pink-100"><p className="inline-flex items-center gap-1.5 text-xs text-pink-400 mb-1"><Icon name="cake" className="w-4 h-4"/>生日</p><p className="font-bold text-gray-800">{fmtDate(selS.birthday)}</p></div>}
                            {selS.enrollmentDate && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">入学日期</p><p className="font-bold text-gray-800">{fmtDate(selS.enrollmentDate)}</p></div>}
                        </div>}
	                        {preferenceRows(selS).length > 0 && (
	                            <div className="grid grid-cols-2 gap-2">
	                                {preferenceRows(selS).map(row => (
	                                    <div key={row.key} className="bg-indigo-50 p-3 rounded-2xl border border-indigo-100">
	                                        <p className="text-xs text-indigo-400 mb-0.5">{row.label}</p>
	                                        <p className="text-sm font-bold text-indigo-800">{row.value}</p>
	                                    </div>
	                                ))}
	                            </div>
	                        )}
                        {/* Archiving is a lifecycle decision taken a handful of
                            times a year. It used to be the last button in the
                            scroll, one thumb-width below 生成成长报告 — the
                            classic mis-tap. It belongs at the end of the record
                            it changes, not next to the daily actions. */}
                        {canWriteStudents && <button onClick={()=>archiveStudent(selS.id,selS.name,!selS.archived)}
                            className={`w-full py-3 rounded-xl text-sm font-bold border min-h-[50px] ${selS.archived?'bg-green-50 active:bg-green-100 text-green-700 border-green-200':'bg-gray-50 active:bg-gray-100 text-gray-500 border-gray-200'}`}>
                            <span className="inline-flex items-center gap-1.5"><Icon name={selS.archived ? 'restore' : 'archiveBox'} className="w-4 h-4"/>{selS.archived ? '恢复学员' : '归档学员'}</span>
                        </button>
                        }
                        </TabPanel>

                        <TabPanel idBase="student-profile" name="records" active={studentProfileTab==='records'}>
                        {/* 报告排在充值与上课记录之前，因为它是唯一一件等着人做的事；
                            下面两块是它的证据，也是查阅用的历史。老师写评语时
                            要看的出勤和课堂笔记，就在同一屏上。 */}
                        {/* E1: the merged timeline sits first — it is the reading
                            view; the collapsibles below stay as the working
                            views (report editing, per-source detail). */}
                        {TENANT_SLUG && <StudentTimeline api={v1Api} studentId={selS.id}
                            openInvoice={canUseSettlementBilling ? (iid)=>{setSelS(null);setEditP(false);setTab('billing',{recordId:String(iid)});} : null} />}
                        {TENANT_SLUG && <StudentProgressReports api={v1Api} studentId={selS.id}
                            studentName={selS.name} canWrite={canWriteProgress}
                            canPublish={canPublishProgress} showToast={showToast} />}
                        {/* F2: Topup history collapsible */}
                        {canWriteCredits && (()=>{
                            const topupsAll = db.logs.filter(l=>(l.studentId===selS.id || (!l.studentId && l.studentName===selS.name))&&l.action==='充值购课');   /* D3 */
                            const topups = topupsAll.slice(0,10);
                            if (!topupsAll.length) return null;
                            return (
                                <details className="border border-gray-200 rounded-2xl overflow-hidden">
                                    <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2">
                                        <Icon name="card" className="w-4 h-4"/>充值记录 <span className="font-normal text-gray-400 text-xs">({topupsAll.length} 条{topupsAll.length>10?' · 显示最近10条':''})</span>
                                    </summary>
                                    <div className="divide-y divide-gray-50">
                                        {topups.map(l=>(
                                            <div key={l.id} className="px-4 py-2.5 flex justify-between items-center text-sm">
                                                <div>
                                                    <span className="font-bold text-indigo-700">+{l.change}</span>
                                                    <span className="ml-2 text-xs text-gray-400">{l.payMethod||''}</span>
                                                    {l.note && <span className="ml-1 text-xs text-gray-400 truncate">{l.note}</span>}
                                                </div>
                                                <div className="flex items-center gap-3 flex-shrink-0">
                                                    {l.feePaid>0 && <span className="text-green-600 font-bold text-xs">${l.feePaid}</span>}
                                                    <span className="text-gray-400 text-xs">{String(l.date).split(',')[0]}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            );
                        })()}
                        {/* B3: 上课记录（v4.6）— 按上课日期，撤销的标灰 */}
                        {TENANT_SLUG && attHistory && attHistory.length > 0 && (
                            <details className="border border-blue-100 rounded-2xl overflow-hidden">
                                <summary className="inline-flex items-center gap-1.5 bg-blue-50 px-4 py-3 cursor-pointer select-none text-sm font-bold text-blue-700"><Icon name="calendar" className="w-4 h-4"/>上课记录 <span className="font-normal text-blue-400 text-xs ml-1">(近 {attHistory.length} 次)</span></summary>
                                <div className="divide-y divide-gray-50 max-h-64 overflow-y-auto sl">
                                    {attHistory.map(a => (
                                        <div key={a.id} className={`px-4 py-2.5 flex items-center justify-between text-sm ${a.reversed_at?'opacity-50':''}`}>
                                            <span className="font-bold text-gray-700">{fmtDate(String(a.class_date||a.attended_at).slice(0,10))}</span>
                                            <span className="text-xs text-gray-400 flex-1 text-center truncate px-2">{a.note||'常规课程'}</span>
                                            <span className={`text-xs font-bold ${a.reversed_at?'text-gray-400':'text-green-600'}`}>{a.reversed_at?'已撤销':'✓ 已签'}</span>
                                        </div>
                                    ))}
                                </div>
                            </details>
                        )}
                        {!(canWriteCredits && db.logs.some(l=>(l.studentId===selS.id || (!l.studentId && l.studentName===selS.name))&&l.action==='充值购课'))
                            && !(TENANT_SLUG && attHistory && attHistory.length > 0) &&
                            <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="还没有记录" sub="充值与上课签到会自动出现在这里"/>}
                        </TabPanel>

                        {TENANT_SLUG && canWriteStudents && (
                          <TabPanel idBase="student-profile" name="portal" active={studentProfileTab==='portal'}>
                            <div className="border border-indigo-100 rounded-2xl overflow-hidden">
                                <div className="bg-indigo-50 px-4 py-3 flex items-center justify-between gap-3">
                                    <div>
                                        <p className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-800"><Icon name="lock" className="w-4 h-4"/>学员专区</p>
                                        <p className="text-xs text-indigo-500 mt-0.5">姓名、手机与独立 6 位访问码验证；访问码不会保存明文。</p>
                                    </div>
                                    <span className={`text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.hasAccessCode?'bg-emerald-100 text-emerald-700':'bg-gray-100 text-gray-500'}`}>
                                        {selS.hasAccessCode?'已启用':'未启用'}
                                    </span>
                                </div>
                                <div className="p-4 space-y-3">
                                    {!selS.mobile && <p className="text-xs rounded-xl bg-amber-50 border border-amber-100 text-amber-700 p-3">请先补充学员手机号码，再生成访问码。</p>}
                                    {accessCodeResult?.studentId===selS.id && (
                                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                                            <p className="text-xs font-bold text-amber-800">仅显示一次，请立即安全交给家长或成年学员</p>
                                            <div className="flex items-center gap-3 mt-2">
                                                <code className="text-2xl tracking-[0.3em] font-bold text-gray-900">{accessCodeResult.code}</code>
                                                <button onClick={()=>copyText(accessCodeResult.code,'访问码已复制')}
                                                    className="ml-auto px-3 py-2 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-800 min-h-[44px]">复制</button>
                                            </div>
                                        </div>
                                    )}
                                    {selS.accessCodeUpdatedAt && <p className="text-xs text-gray-400">最近更新：{fmtDate(selS.accessCodeUpdatedAt)}</p>}
                                    <div>
                                        <button disabled={busy||!selS.mobile}
                                            onClick={()=>selS.hasAccessCode
                                                ? confirm('生成新访问码后，旧访问码和现有登录会话会立即失效。继续？', generateStudentAccessCode, {confirmText:'生成新码'})
                                                : generateStudentAccessCode()}
                                            className="w-full py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold disabled:bg-gray-300 min-h-[44px]">
                                            {selS.hasAccessCode?'更换访问码':'生成访问码'}
                                        </button>
                                        {selS.hasAccessCode && (
                                            <details className="mt-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                                                <summary className="cursor-pointer text-xs font-bold text-gray-500 select-none">高级操作</summary>
                                                <div className="pt-3 flex items-center gap-3">
                                                    <p className="text-xs text-gray-500 flex-1">停用后，当前访问码和所有已登录会话会立即失效。</p>
                                                    <button disabled={busy} onClick={revokeStudentAccessCode}
                                                        className="px-3 py-2 rounded-lg bg-white border border-red-200 text-red-700 text-xs font-bold min-h-[44px]">停用学员专区</button>
                                                </div>
                                            </details>
                                        )}
                                    </div>
                                </div>
                            </div>
                          </TabPanel>
                        )}

                        {canWritePortfolio && (
                          <TabPanel idBase="student-profile" name="portfolio" active={studentProfileTab==='portfolio'}>
                        {/* The ground follows the consent status. It used to be emerald
                            whatever the badge said, so a student with NO consent on file sat
                            under a success-green header — the colour claimed the job was done
                            while the badge beside it read 未记录. A role colour that contradicts
                            the state it wraps is worse than no colour: green is now the reward
                            for confirmed, amber marks a withdrawal, and unrecorded is neutral,
                            which is what "nothing has happened yet" actually looks like. */}
                        {TENANT_SLUG && (
                            <div className={`border rounded-2xl overflow-hidden ${selS.publicationConsent?.status==='confirmed'?'border-emerald-100':selS.publicationConsent?.status==='withdrawn'?'border-amber-100':'border-gray-200'}`}>
                                <div className={`px-4 py-3 flex items-center justify-between gap-3 ${selS.publicationConsent?.status==='confirmed'?'bg-emerald-50':selS.publicationConsent?.status==='withdrawn'?'bg-amber-50':'bg-gray-50'}`}>
                                    <div>
                                        <p className="inline-flex items-center gap-1.5 text-sm font-bold text-gray-900"><Icon name="shield" className="w-4 h-4"/>官网作品公开授权</p>
                                        <p className="text-xs text-gray-500 mt-0.5">授权与撤回均追加为不可覆盖的审计记录。</p>
                                    </div>
                                    <span className={`text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.publicationConsent?.status==='confirmed'?'bg-emerald-600 text-white':selS.publicationConsent?.status==='withdrawn'?'bg-amber-100 text-amber-700':'bg-gray-100 text-gray-500'}`}>
                                        {selS.publicationConsent?.status==='confirmed'?'有效':selS.publicationConsent?.status==='withdrawn'?'已撤回':'未记录'}
                                    </span>
                                </div>
                                <div className="p-4 space-y-3">
                                    {selS.publicationConsent?.status==='confirmed' && (
                                        <div className="text-xs text-gray-600 space-y-1">
                                            <p>授权人：<span className="font-bold">{selS.publicationConsent.by||'—'}</span> · {selS.publicationConsent.relationship||'—'} · {selS.publicationConsent.method||'—'}</p>
                                            <p className="text-gray-400">记录时间：{fmtDate(selS.publicationConsent.at)} · 告知版本 {selS.publicationConsent.noticeVersion||'—'}</p>
                                        </div>
                                    )}
                                    {consentEdit?.mode==='confirm' && (
                                        <div className="space-y-2 rounded-xl bg-gray-50 border border-gray-100 p-3">
                                            <input value={consentEdit.by} onChange={e=>setConsentEdit(p=>({...p,by:e.target.value}))}
                                                placeholder="授权人姓名 *" maxLength={120}
                                                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-emerald-400"/>
                                            <div className="grid grid-cols-2 gap-2">
                                                <select value={consentEdit.relationship} onChange={e=>setConsentEdit(p=>({...p,relationship:e.target.value}))}
                                                    className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white">
                                                    <option value="">与学员关系 *</option><option>监护人</option><option>本人</option><option>其他授权人</option>
                                                </select>
                                                <select value={consentEdit.method} onChange={e=>setConsentEdit(p=>({...p,method:e.target.value}))}
                                                    className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white">
                                                    <option value="">授权方式 *</option><option>书面确认</option><option>电子确认</option><option>当面确认</option>
                                                </select>
                                            </div>
                                            <textarea value={consentEdit.note} onChange={e=>setConsentEdit(p=>({...p,note:e.target.value}))}
                                                placeholder="备注（可选，不要记录证件号码）" rows="2" maxLength={500}
                                                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm resize-none"/>
                                            <div className="flex gap-2">
                                                <button onClick={()=>setConsentEdit(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-bold text-gray-500">取消</button>
                                                <button disabled={busy} onClick={savePublicationConsent} className="flex-1 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">记录授权</button>
                                            </div>
                                        </div>
                                    )}
                                    {consentEdit?.mode==='withdraw' && (
                                        <div className="space-y-2 rounded-xl bg-red-50 border border-red-100 p-3">
                                            <textarea value={consentEdit.note} onChange={e=>setConsentEdit(p=>({...p,note:e.target.value}))}
                                                placeholder="撤回原因 *（将写入审计记录）" rows="2" maxLength={500}
                                                className="w-full px-3 py-2.5 border border-red-200 rounded-xl text-sm resize-none"/>
                                            <p className="text-xs text-red-600">确认后，该学员当前所有官网公开作品会立即下架，私人作品仍保留。</p>
                                            <div className="flex gap-2">
                                                <button onClick={()=>setConsentEdit(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-500">取消</button>
                                                <button disabled={busy} onClick={withdrawPublicationConsent} className="flex-1 py-2.5 rounded-xl bg-red-600 text-white text-sm font-bold disabled:opacity-50">撤回并下架</button>
                                            </div>
                                        </div>
                                    )}
                                    {!consentEdit && (
                                        <div className="flex gap-2">
                                            {/* An action, not a state. Green here said "this is done" about a
                                                button whose whole purpose is that something is NOT done yet — and
                                                it stayed green even once consent was on file, where the panel and
                                                the badge are already carrying the good news. Filled actions are
                                                the accent, the same as ＋上传 and 生成成长报告 beside it. */}
                                            <button onClick={()=>setConsentEdit({mode:'confirm',by:'',relationship:'',method:'',note:''})}
                                                className="flex-1 py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold min-h-[44px]">
                                                {selS.publicationConsent?.status==='confirmed'?'追加新授权记录':'记录授权'}
                                            </button>
                                            {selS.publicationConsent?.status==='confirmed' && <button onClick={()=>setConsentEdit({mode:'withdraw',note:''})}
                                                className="px-4 py-2.5 rounded-xl bg-white border border-red-200 text-red-700 text-sm font-bold min-h-[44px]">撤回</button>}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* ── Portfolio section ── */}
                        {(()=>{
                            const items = selS.portfolio || [];
                            return (
                                /* purple maps to the info role, and a section heading is not a
                                   state — it was painting a whole panel blue for no reason a reader
                                   could act on. Headings take the neutral ramp; the upload button is
                                   the primary action here and takes the accent, like every other
                                   filled action in this console. */
                                <div className="border border-gray-200 rounded-2xl overflow-hidden">
                                    <div className="bg-gray-50 px-4 py-3 flex items-center justify-between">
                                        <span className="text-sm font-bold text-gray-900 flex items-center gap-1.5"><Icon name="image" className="w-4 h-4"/> {workNoun}集
                                            <span className="font-normal text-gray-500 text-xs ml-1">{`(${items.length} 张)`}</span>
                                        </span>
                                        <button onClick={()=>setPortUpload(true)}
                                            className="text-xs bg-indigo-600 active:bg-indigo-700 text-white px-3 py-1.5 rounded-lg font-bold">
                                            + 上传
                                        </button>
                                    </div>
                                    {items.length === 0 ? (
                                        <div className="px-4 py-7 text-center">
                                            <p className="inline-flex items-center gap-1.5 text-2xl mb-1"><Icon name="image" className="w-4 h-4"/></p>
                                            <p className="text-xs text-gray-400">还没有作品，点击「上传」添加第一张</p>
                                        </div>
                                    ) : (
                                        <div className="p-2.5 grid grid-cols-3 gap-2">
                                            {items.map((item,idx)=>(
                                                <div key={item.id}
                                                    className="port-thumb relative group cursor-pointer rounded-xl overflow-hidden bg-gray-100"
                                                    style={{aspectRatio:'1'}}
                                                    role="button" tabIndex={0}
                                                    aria-label={`查看${item.title || fmtDate(item.date)}作品`}
                                                    onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();setPortLB({items,idx});}}}
                                                    onClick={()=>setPortLB({items,idx})}>
                                                    {/* M7: skeleton shown until image loads */}
                                                    <div className="img-skel absolute inset-0" id={`sk-${item.id}`}/>
                                                    <img
                                                        src={portfolioThumbSrc(selS.id, item)}
                                                        srcSet={portfolioSrcSet(selS.id, item)}
                                                        sizes="(max-width: 640px) 33vw, 220px"
                                                        alt={item.title || `${selS.name}的作品 ${idx + 1}`}
                                                        loading="lazy"
                                                        className="w-full h-full object-cover relative"
                                                        onLoad={e=>{const sk=document.getElementById(`sk-${item.id}`);if(sk)sk.style.display='none';}}
                                                        onError={e=>{e.target.style.display='none';}}/>
                                                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pt-4 pb-1">
                                                        {item.title && <p className="text-white text-xs font-bold leading-tight truncate">{item.title}</p>}
                                                        <p className="text-white text-xs leading-tight truncate">{fmtDate(item.date)}{item.note?' ·':''}</p>
                                                    </div>
                                                    {item.public && (
                                                        <span className="absolute top-1 left-1 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 shadow">
                                                            官网
                                                        </span>
                                                    )}
                                                    {/* B1: port-actions = hidden on mouse devices (hover:flex), always visible on touch (CSS override) */}
                                                    {/* Icon stays compact; the shared aria-label rule expands its hit box to 44px. */}
                                                    <div className="port-actions absolute top-0.5 right-0.5 hidden group-hover:flex gap-1 z-10">
                                                        <button
                                                            onClick={e=>{e.stopPropagation();setPortEdit({sid:String(selS.id),item,note:item.note||'',title:item.title||'',date:item.date||todayISO(),public:!!item.public});}}
                                                            aria-label="编辑" className="bg-white/90 rounded-lg p-2 shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"><Icon name="pencil" className="w-4 h-4"/></button>
                                                        <button
                                                            onClick={e=>{e.stopPropagation();portfolioDoDelete(String(item.id));}}
                                                            aria-label="删除" className="bg-red-500 rounded-lg p-2 text-white shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"><Icon name="trash" className="w-4 h-4"/></button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                        {/* The growth report is assembled FROM the portfolio, so
                            it is the one action that belongs to a tab rather
                            than to the student. */}
                        {canWritePortfolio && <button onClick={()=>openGrowthReport(selS)}
                            /* Was a purple→pink gradient: info blended into the support colour,
                               so the button's colour named two roles and therefore none. A filled
                               action is the accent. */
                            className="w-full py-3 rounded-xl text-sm font-bold bg-indigo-600 active:bg-indigo-700 text-white min-h-[50px] shadow-sm">
                            <span className="inline-flex items-center gap-1.5"><Icon name="star" className="w-4 h-4"/>生成成长报告（发给家长）</span>
                        </button>
                        }
                          </TabPanel>
                        )}
                    </div>
                ) : (
                    <form onSubmit={handleUpdateStudent} className="space-y-4">
                        <div>
                            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
                            <PhotoUploader value={editPhoto} onChange={setEditPhoto} notify={notify}/>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">First Name (名) *</label>
                                <input name="firstName" defaultValue={selS.firstName||selS.name||''} required className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">Last Name (姓) <span className="font-normal text-gray-400">选填</span></label>
                                <input name="lastName" defaultValue={selS.lastName||''} className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold"/></div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">电话</label>
                                <input name="mobile" defaultValue={selS.mobile} placeholder="04xx xxx xxx" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div>
                                <label className="text-sm font-bold text-indigo-700 mb-1 block">课时余额</label>
                                {/* White, not the indigo-50 fill: a tinted box next
                                    to white siblings reads as disabled, and this is
                                    the one field in the form that writes a ledger
                                    entry. The indigo border carries the emphasis. */}
                                <input name="balance" type="number" min="0" defaultValue={selS.balance} required className="w-full px-3 py-3 border-2 border-indigo-300 bg-white text-indigo-800 font-bold text-xl rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                                <p className="inline-flex items-center gap-1.5 text-xs text-amber-500 mt-1"><Icon name="warning" className="w-4 h-4"/>修改将记入日志</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">微信号 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="wechat" defaultValue={selS.wechat||''} placeholder="如 wechat_id" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">邮箱 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="email" type="email" defaultValue={selS.email||''} className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                        </div>
                        {/* Birthday and historical enrolment date remain first-class profile fields. */}
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="inline-flex items-center gap-1.5 text-sm font-bold text-gray-500 mb-1 block"><Icon name="cake" className="w-4 h-4"/>生日 <span className="font-normal text-gray-400">选填</span></label>
                                <input type="date" name="birthday" defaultValue={selS.birthday||''} min="1920-01-01" max="2099-12-31"
                                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">入学日期 <span className="font-normal text-gray-400">选填</span></label>
                                <input type="date" name="enrollmentDate" defaultValue={selS.enrollmentDate||''} min="1900-01-01" max={todayISO()}
                                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                                <p className="text-[11px] text-gray-400 mt-1">可补录系统启用前的真实入学日期</p></div>
                        </div>
                        <div><label className="text-sm font-bold text-gray-500 mb-1 block">备注</label>
                            <textarea name="remark" defaultValue={selS.remark} rows="3" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"></textarea></div>
	                        <details className="border border-gray-200 rounded-xl overflow-hidden">
	                            <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100">
	                                {preferenceProfile().title} <span className="font-normal text-gray-400">选填</span>
	                            </summary>
	                            <div className="p-4 space-y-3">
	                                {preferenceProfile().fields.map(field => (
	                                    <div key={field.key}>
	                                        <label className="text-sm font-bold text-gray-500 mb-1 block">{field.label}</label>
	                                        <input name={`pref_${field.key}`} defaultValue={preferenceValue(selS, field.key)} placeholder={field.placeholder}
	                                            className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
	                                    </div>
	                                ))}
	                            </div>
	                        </details>
                        <div className="flex justify-between items-center pt-3 border-t border-gray-100">
                            <button type="button" onClick={()=>handleDelete(selS.id,selS.name)} disabled={busy}
                                className="px-4 py-3 bg-red-50 active:bg-red-100 text-red-700 font-bold rounded-xl text-sm border border-red-200 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="trash" className="w-4 h-4"/>永久删除</span></button>
                            <div className="flex gap-2">
                                <button type="button" onClick={()=>confirm('放弃未保存的修改？', ()=>{setEditP(false);setEditPhoto('');}, {confirmText:'放弃修改'})} className="px-4 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm min-h-[50px]">取消</button>
                                <button type="submit" disabled={busy} className="inline-flex items-center gap-1.5 px-6 py-3 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md min-h-[50px]"><Icon name="save" className="w-4 h-4"/>保存</button>
                            </div>
                        </div>
                    </form>
                )}
            </div>
            {/* Outside the scroll, and outside the tabs. Three actions earn
                that: 加入今日排课 is performed many times a day, 快速充值 is
                what you reach for the moment the balance badge in the header
                reads low, and 编辑 is a mode switch that has to work from
                whichever tab you happen to be on. Everything else is either
                rare (归档) or belongs to one tab's subject (成长报告).
                Columns are 1.618 : 1 — the primary action wins the golden
                major share, the secondary takes the minor. */}
            {!editP && (
                <div className="cms-profile-actions flex-shrink-0 border-t border-gray-200 bg-gray-50">
                    <div className="cms-profile-actions-row">
                        {canWriteAttendance && !selS.archived &&
                            <button onClick={()=>scheduleStudentToday(selS)} disabled={busy}
                                className="py-3 rounded-xl text-sm font-bold bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 min-h-[50px] inline-flex items-center justify-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>{isStudentScheduledOn(selS.id,todayISO())?'查看今日排课':'加入今日排课'}</button>}
                        {canWriteStudents && <button onClick={()=>{setEditP(true);setEditPhoto(selS.photo||'');}}
                            className="py-3 rounded-xl text-sm font-bold bg-white border-2 border-indigo-100 active:bg-indigo-50 text-indigo-700 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="pencil" className="w-4 h-4"/>编辑</span></button>}
                    </div>
                    {canWriteCredits && !selS.archived && (
                        <button onClick={()=>{setTuStu(selS.id);setSelS(null);setEditP(false);setTab('topup');}}
                            className="w-full py-3 rounded-xl text-sm font-bold bg-white border border-gray-200 active:bg-gray-50 text-gray-700 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="money" className="w-4 h-4"/>快速充值</span></button>
                    )}
                </div>
            )}
        </div>
    </div>
    );
}
