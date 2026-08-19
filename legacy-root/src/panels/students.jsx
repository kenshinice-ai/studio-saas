/* 学员 — 档案列表、新建学员、报名审核。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { BalBadge, EmptyState, Icon, PhotoAvatar, PhotoUploader, REG_STATUS_ZH } from "../components.jsx";
import { daysSince, fmtDT, fmtDate, mediaSrc, todayISO, v1Api } from "../components.jsx";
import { FilterBar } from "./filter_bar.jsx";
import { OverdueReports } from "./progress_reports.jsx";

export function StudentsSection(props) {
    const {
        archiveSelected, busy, canManageOperations, canWriteAttendance, canWriteCredits, canWriteStudents,
        copySelectedReminders, copyText, exportStudentsCSV, filterBy, getTag, isStudentScheduledOn,
        pageStudents, preferenceRows, renderMessage, renewTh, scheduleStudentToday, selectedStudentIds,
        selectedStudents, setEditP, setFilterBy, setSelS, setSelectedStudentIds, setSortBy,
        setSrch, setStudentPage, setTab, setTuStu, sortBy, sortedFiltered,
        srch, studentPage, studentPageCount, toggleSelectPage, toggleSelectStudent,
    } = props;
    return (
<div className="anim space-y-4">
    <div className="flex justify-between items-center gap-3 flex-wrap">
        <h2 className="md:hidden text-xl font-bold text-gray-800">{`学员档案 (${sortedFiltered.length})`}</h2>
        <p className="hidden md:block text-sm font-bold text-gray-500">{`共 ${sortedFiltered.length} 人`}</p>
        <div className="flex gap-2">
            {canManageOperations && <button onClick={exportStudentsCSV}
                className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
            }
            {canWriteStudents && <button onClick={()=>setTab('new_student')}
                className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md min-h-[44px]"><Icon name="plus" className="w-4 h-4"/>新建</button>
            }
        </div>
    </div>

    {/* 学员档案接上共享筛选栏。这里刻意 NOT 把 15 个分类片塞进 FilterBar 的
        `buckets`：那是一维数组，15 个平铺会换行成三行，而且这一排本来就带
        横向滚动、够用。它们和排序下拉一起走 extra 插槽 —— 页面保留自己需要
        的控件，共享的是「常驻结果计数」和「一键清除全部」，那两样正是六页
        各写各的、每次都写漏一点的东西。
        搜索框回车打开唯一匹配是这一页特有的加速器，所以它也留在插槽里。 */}
    <FilterBar
        total={sortedFiltered.length} totalNoun="人"
        extraDirty={Boolean(filterBy !== 'all' || srch)}
        onClearExtra={()=>{ setFilterBy('all'); setSrch(''); }}
        extra={<div className="space-y-3">
        <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"><Icon name="search"/></span>
            <input type="text" placeholder="搜索姓名 / 电话 / 微信 / 邮箱…（回车打开唯一匹配）" value={srch} onChange={e=>setSrch(e.target.value)}
                onKeyDown={e=>{ if (e.key==='Enter' && sortedFiltered.length===1) { setSelS(sortedFiltered[0]); setEditP(false); } }}
                aria-label="搜索学员"
                className="w-full pl-10 pr-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
        </div>
        <div className="overflow-x-auto -mx-1 px-1 pb-1"><div className="flex gap-2 items-center" style={{minWidth:'max-content'}}>
            <select value={sortBy} onChange={e=>setSortBy(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-sm min-h-[44px] flex-shrink-0">
                <option value="name-az">名 A→Z</option>
                <option value="name-za">名 Z→A</option>
                <option value="last-az">姓 A→Z</option>
                <option value="last-za">姓 Z→A</option>
                <option value="bal-desc">课时 高→低</option>
                <option value="bal-asc">课时 低→高</option>
                <option value="date-desc">最近活跃</option>
            </select>
            {[['all','全部'],['active','有余额'],['low',`低余额≤${renewTh}`],['zero','已清零'],['archived','归档库'],['tag-hot','活跃'],['tag-low','低频'],['tag-risk','流失风险'],['portal-ready','专区已就绪'],['portal-missing-mobile','缺手机号'],['portal-disabled','专区未启用'],['portal-content-blocked','私人内容受阻'],['publication-live','作品已公开'],['publication-ready','公开授权有效'],['publication-missing-consent','缺公开授权']].map(([v,l]) => (
                <button key={v} onClick={()=>setFilterBy(v)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border min-h-[44px] transition flex-shrink-0 ${filterBy===v?'bg-indigo-600 text-white border-indigo-600':'bg-white text-gray-600 border-gray-300 active:border-indigo-300'}`}>{l}{filterBy===v?` · ${sortedFiltered.length}`:''}</button>
            ))}
        </div></div>
        </div>} />

    {/* P2-14: multi-select toolbar. Bulk archive and bulk reminders used to be
        reachable only through the low-balance filter's single "copy all" button. */}
    {selectedStudents.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm font-bold text-indigo-700">{`已选择 ${selectedStudents.length} 人`}</p>
            <div className="flex gap-2 flex-wrap">
                <button onClick={()=>setSelectedStudentIds([])}
                    className="bg-white border border-indigo-200 text-indigo-700 px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]">清除选择</button>
                <button onClick={copySelectedReminders}
                    className="bg-indigo-600 active:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]">复制续课提醒</button>
                {canManageOperations && (
                    <button onClick={archiveSelected} disabled={busy}
                        className="bg-gray-700 active:bg-gray-800 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px] disabled:bg-gray-300">批量归档</button>
                )}
            </div>
        </div>
    )}
    {/* F5: 待续课看板 — 低余额筛选下提供一键复制提醒话术 */}
    {canWriteCredits && filterBy==='low' && sortedFiltered.length>0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="inline-flex items-center gap-1.5 text-sm font-bold text-orange-700"><Icon name="bolt" className="w-4 h-4"/>待续课学员 {sortedFiltered.length} 人（余额 ≤{renewTh} 节）</p>
            <button onClick={()=>{
                const lines = sortedFiltered.map(s => renderMessage('renewal',
                    '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
                    {student:s.name, balance:s.balance, note:''}));
                copyText(lines.join('\n\n'), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
            }} className="bg-orange-600 active:bg-orange-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>复制全部提醒话术</span></button>
        </div>
    )}
    {!sortedFiltered.length && <EmptyState icon={<Icon name="search" className="w-8 h-8"/>} main="没有符合条件的学员"
            sub={srch ? `没有姓名、电话、微信或邮箱包含「${srch}」的学员。换个关键词，或清空搜索看全部。` : '当前筛选条件下没有学员。点下方按钮回到全部名单。'}
            action={srch ? '清空搜索' : '查看全部学员'} onAction={()=>{setSrch('');setFilterBy('all');}}/>}
    {sortedFiltered.length > 0 && (
        <label className="flex items-center gap-2 text-xs font-bold text-gray-500 px-1">
            <input type="checkbox" className="w-4 h-4"
                checked={pageStudents.length>0 && pageStudents.every(item=>selectedStudentIds.includes(item.id))}
                onChange={e=>toggleSelectPage(e.target.checked)}/>
            {`选择本页 ${pageStudents.length} 人`}
        </label>
    )}
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {pageStudents.map(s => (
            <div key={s.id} className={`bg-white rounded-2xl p-4 shadow-sm border hover-row transition flex flex-col justify-between print-card ${selectedStudentIds.includes(s.id)?'ring-2 ring-indigo-400 border-indigo-200':s.archived?'border-gray-200 opacity-70':parseInt(s.balance,10)===0?'border-red-100':parseInt(s.balance,10)<=2?'border-orange-100':'border-gray-100'}`}>
                <div>
                    <div className="flex justify-between items-start mb-2 gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                            <input type="checkbox" className="w-4 h-4 flex-shrink-0" aria-label={`选择 ${s.name}`}
                                checked={selectedStudentIds.includes(s.id)}
                                onChange={()=>toggleSelectStudent(s.id)}/>
                            <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                            <div className="min-w-0">
                                <h3 className="font-bold text-gray-800 break-words leading-snug">{s.name}</h3>
                                {s.archived && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 rounded mt-0.5 inline-block">归档</span>}
                            </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                            <BalBadge n={s.balance}/>
                            {(()=>{const t=getTag(s); return t?<span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-bold ${t.cls}`}><Icon name={t.icon} className="w-3 h-3"/>{t.label}</span>:null;})()}
                        </div>
                    </div>
                    <p className="text-gray-400 text-sm flex items-center gap-1.5"><Icon name="phone" className="w-4 h-4"/> {s.mobile||'—'}</p>
                    {s.email && <p className="text-gray-400 text-sm flex items-center gap-1.5"><Icon name="mail" className="w-4 h-4"/> {s.email}</p>}
                    {preferenceRows(s).slice(0, 1).map(row => (
                        <p key={row.key} className="text-gray-400 text-sm">{row.label}：{row.value}</p>
                    ))}
                    <p className="text-gray-400 text-sm mt-0.5 flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/> {fmtDate(s.lastActive)}{daysSince(s.lastActive)<9999?` · ${daysSince(s.lastActive)}天前`:''}</p>
                </div>
                <div className="flex gap-2 mt-3">
                    <button onClick={()=>{setSelS(s);setEditP(false);}}
                        className="flex-1 bg-gray-50 active:bg-gray-100 border border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-bold min-h-[44px]">详情</button>
                    {!s.archived && (<>
                        {canWriteCredits && <button onClick={()=>{setTuStu(s.id);setTab('topup');}}
                            title="快速充值" aria-label="快速充值" className="px-3.5 py-3 rounded-xl font-bold bg-emerald-50 active:bg-emerald-100 text-emerald-700 border border-emerald-200 min-h-[44px] flex items-center justify-center"><Icon name="money"/></button>
                        }
                        {canWriteAttendance && <button onClick={()=>scheduleStudentToday(s)} disabled={busy}
                            className="flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[44px] bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 inline-flex items-center justify-center gap-1.5">{/* Same wording as the profile sheet's primary action: the label says
    what the tap does, not where it goes. It used to read 去排课 when the
    student was ALREADY on today's roster and 排课 when they were not,
    which is the opposite of how both read. */}
<Icon name="calendar" className="w-4 h-4"/>{isStudentScheduledOn(s.id,todayISO())?'查看排课':'加入排课'}</button>
                        }
                    </>)}
                </div>
            </div>
        ))}
    </div>
    {studentPageCount > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
            <button onClick={()=>setStudentPage(p=>Math.max(1,p-1))} disabled={studentPage<=1}
                className="px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]">上一页</button>
            <span className="text-sm text-gray-500 font-bold">{`第 ${studentPage} / ${studentPageCount} 页`}</span>
            <button onClick={()=>setStudentPage(p=>Math.min(studentPageCount,p+1))} disabled={studentPage>=studentPageCount}
                className="px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]">下一页</button>
        </div>
    )}
    {/* U7: Back-to-top button when list > 15 */}
    {sortedFiltered.length > 15 && (
        <button onClick={()=>{ const m=document.querySelector('main'); if(m) m.scrollTo({top:0,behavior:'smooth'}); else window.scrollTo({top:0,behavior:'smooth'}); }}
            className="fixed bottom-24 right-4 md:bottom-8 z-40 w-11 h-11 bg-indigo-600 active:bg-indigo-700 text-white rounded-full shadow-lg flex items-center justify-center text-lg"
            title="回到顶部" aria-label="回到顶部">↑</button>
    )}
</div>
    );
}


export function NewStudentSection(props) {
    const {
        busy, formPhoto, handleAddStudent, notify, preferenceProfile, setFormPhoto,
        setTab,
    } = props;
    return (
<div className="anim bg-white rounded-2xl p-6 max-w-xl mx-auto shadow-sm border border-gray-100">
    <h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold mb-5 text-gray-800"><Icon name="plus" className="w-5 h-5"/>新建学员档案</h2>
    <form onSubmit={handleAddStudent} className="space-y-4">
        {/* Photo */}
        <div>
            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
            <PhotoUploader value={formPhoto} onChange={setFormPhoto} notify={notify}/>
        </div>
        {/* Name */}
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">First Name (名) *</label>
                <input required name="firstName" placeholder="如 Holly"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">Last Name (姓) <span className="font-normal text-gray-400">选填</span></label>
                <input name="lastName" placeholder="如 Chen"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
        {/* Contact + Balance */}
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">电话</label>
                <input name="mobile" placeholder="04xx xxx xxx"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">初始课时</label>
                <input name="balance" type="number" min="0" defaultValue="0"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">微信号 <span className="font-normal text-gray-400">选填</span></label>
                <input name="wechat" placeholder="如 wechat_id"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">邮箱 <span className="font-normal text-gray-400">选填</span></label>
                <input name="email" type="email" placeholder="example@email.com"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
	        {/* Tenant-configured student preferences */}
	        <details className="border border-gray-200 rounded-xl overflow-hidden">
	            <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100">
	                {preferenceProfile().title} <span className="font-normal text-gray-400">选填 / Optional</span>
	            </summary>
	            <div className="p-4 space-y-3">
	                {preferenceProfile().fields.map(field => (
	                    <div key={field.key}>
	                        <label className="text-sm font-bold text-gray-500 mb-1 block">{field.label}</label>
	                        <input name={`pref_${field.key}`} placeholder={field.placeholder}
	                            className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
	                    </div>
	                ))}
	            </div>
	        </details>
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">生日 <span className="font-normal text-gray-400">选填</span></label>
                <input type="date" name="birthday" min="1920-01-01" max="2099-12-31"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">入学日期</label>
                <input type="date" name="enrollmentDate" defaultValue={todayISO()} min="1900-01-01" max={todayISO()}
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1 block">备注</label>
            <textarea name="remark" rows="3" placeholder="备注信息..."
                className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"></textarea>
        </div>
        <div className="flex gap-3 pt-2">
            <button type="submit" disabled={busy}
                className="flex-1 bg-indigo-600 active:bg-indigo-700 text-white py-3.5 rounded-xl font-bold text-sm shadow-md min-h-[52px]">确认建档</button>
            <button type="button" onClick={()=>{setTab('students');setFormPhoto('');}}
                className="px-6 py-3.5 bg-gray-100 active:bg-gray-200 text-gray-700 rounded-xl font-bold text-sm min-h-[52px]">取消</button>
        </div>
    </form>
</div>
    );
}


export function PendingSection(props) {
    const {
        advanceRegistration, approveCredits, approveStudent, approveTenant, bookings, busy,
        canReviewBookings, db, dupPick, followUpDates, pendingCount, pendingTab,
        preferenceRows, rejectStudent, reviewBooking, setApproveCredits, setDupPick, setFollowUpDates,
        setPendingTab, setTab, showToast,
    } = props;
    return (
<div className="anim space-y-4">
    <div className="flex items-start justify-between gap-3 flex-wrap"><div><h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="clipboard" className="w-4 h-4"/>待处理</h2><p className="text-sm text-gray-500 mt-1">新报名和约课申请共用一个收件箱，按业务类型分开处理。</p></div><span className="rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-bold text-amber-700">{pendingCount} 项等待处理</span></div>
    {/* v8.10.0: 一个收件箱，两个标签。计数分开写，是因为两者含义不同 ——
        「新报名」批准后建学员，「约课」批准后占座位，把后者算进前者会让
        「本月新报名」永远虚高，而那正是工作室用来判断投放效果的数字。
        但前台不该有两个地方要看，所以它们在同一页。 */}
    <div className="flex gap-2 flex-wrap">
        {[['registrations','新报名',(db.pending||[]).length],
          ['bookings','约课',bookings.length],
          ['reports','成长报告','']].map(([key,label,count])=>(
            <button key={key} onClick={()=>setPendingTab(key)}
                className={`px-4 py-2 rounded-xl text-sm font-bold min-h-[44px] border ${pendingTab===key?'bg-indigo-600 text-white border-indigo-600':'bg-white text-gray-600 border-gray-200 active:bg-gray-50'}`}>
                {label} {count}
            </button>
        ))}
    </div>
    {pendingTab==='reports' && (
        <OverdueReports api={v1Api} showToast={showToast}
            onOpenStudent={(id)=>setTab('students', {recordId: id})} />
    )}

    {pendingTab==='bookings' && (
    <div className="space-y-3">
        {!bookings.length && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
                <p className="font-bold text-gray-600">没有待处理的约课申请</p>
                <p className="text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed">
                    在 Studio Admin 的「Timetable」里打开公开课表并允许约课后，家长可以在课表页留下姓名和手机号申请上课，申请会出现在这里。
                </p>
            </div>
        )}
        {bookings.map(bk => (
            <div key={bk.id} className="bg-white rounded-2xl shadow-sm border border-amber-200 p-4 space-y-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0">
                        <p className="text-base font-bold text-gray-800">{bk.contactName}
                            {/* 是否命中老学员只在这里显示。公开表单的回应无论
                                命中与否都完全一致 —— 否则那个表单就成了「这个
                                号码是不是你们的学员」的查询接口。 */}
                            {bk.isExistingStudent
                                ? <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-green-100 text-green-700 border border-green-300 rounded-full px-2 py-0.5">已是学员{bk.matchedStudent?` · ${bk.matchedStudent}`:''}</span>
                                : <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-gray-100 text-gray-600 border border-gray-300 rounded-full px-2 py-0.5">新访客</span>}
                        </p>
                        <p className="inline-flex items-center gap-1.5 text-sm text-gray-500"><Icon name="phone" className="w-4 h-4"/>{bk.contactPhone}</p>
                        <p className="text-sm text-gray-600 mt-1">{bk.date} {bk.startTime} · {bk.title||'未命名班次'}</p>
                        {bk.message && <p className="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{bk.message}</p>}
                    </div>
                    <div className="text-right flex-shrink-0">
                        {/* 容量在「批准」那一刻才是真的，所以这里显示的是现在
                            的余位，而不是提交时的。 */}
                        <p className={`text-xs font-bold ${bk.seatsLeft===0?'text-gray-500':'text-green-700'}`}>
                            {bk.seatsLeft===0?'已满':`还有 ${bk.seatsLeft} 位`}
                        </p>
                        <p className="text-[11px] text-gray-400">容量 {bk.capacity}</p>
                    </div>
                </div>
                {bk.seatsLeft===0 && (
                    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                        这节课已经满了。批准会被拒绝——先提高班次容量，或婉拒并联系家长改约。
                    </p>
                )}
{canReviewBookings && <div className="flex gap-2 justify-end">
                    <button onClick={()=>reviewBooking(bk,'declined')} disabled={busy}
                        className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50 min-h-[44px]">婉拒</button>
                    <button onClick={()=>reviewBooking(bk,'approved')} disabled={busy}
                        className="bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold min-h-[44px]">
                        {bk.isExistingStudent?'批准并排课':'批准并转报名'}
                    </button>
                </div>}
            </div>
        ))}
    </div>
    )}
    {pendingTab==='registrations' && <>
    {!(db.pending||[]).length && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
            <p className="inline-flex items-center gap-1.5 text-4xl mb-3"><Icon name="check" className="w-4 h-4"/></p>
            <p className="font-bold text-gray-600">没有待审核的报名</p>
            <p className="text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed">家长在官网或报名页提交后，申请会出现在这里等你批准。把报名页链接发出去就能开始收。</p>
        </div>
    )}
    {(db.pending||[]).map(pen => {
        const fullName = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
        const normP = p => (p||'').replace(/[\s\-\(\)]+/g,'');
        /* 走查发现：同一手机号的重复待审申请（如同一家长提交两次）在列表里
           看不出来。纯前端提示——两张卡都挂琥珀色「疑似重复」角标。 */
        const penMobile = normP(pen.mobile);
        const isDupPending = !!penMobile && (db.pending||[]).some(o => o.id!==pen.id && normP(o.mobile)===penMobile);
        return (
            <div key={pen.id} className="bg-white rounded-2xl shadow-sm border border-amber-200 p-5 space-y-4">
                <div className="flex items-start gap-4">
                    {pen.photo
                        ? <img src={mediaSrc(pen.photo)} className="w-16 h-16 rounded-full object-cover flex-shrink-0 border-2 border-indigo-100" alt={fullName}/>
                        : <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-2xl font-bold text-indigo-600 flex-shrink-0">{(pen.firstName||'?')[0].toUpperCase()}</div>
                    }
                    <div className="flex-1 min-w-0">
                        <p className="text-lg font-bold text-gray-800">{fullName}
                            {isDupPending && <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300 rounded-full px-2 py-0.5" title="另有一条待审核申请使用相同手机号">疑似重复</span>}
                        </p>
                        <p className="inline-flex items-center gap-1.5 text-sm text-gray-500"><Icon name="phone" className="w-4 h-4"/>{pen.mobile||'—'}{pen.wechat ? ` · ${pen.wechat}` : ''}{pen.email ? ` · ${pen.email}` : ''}</p>
                        {pen.birthday && <p className="inline-flex items-center gap-1.5 text-xs text-pink-500 mt-0.5"><Icon name="cake" className="w-4 h-4"/>{fmtDate(pen.birthday)}</p>}
                        {pen.mobile && (() => {
                            const match = db.students.filter(s=>!s.archived && normP(s.mobile)===normP(pen.mobile));
                            return match.length > 0 ? <p className="inline-flex items-center gap-1.5 text-xs text-blue-500 mt-0.5"><Icon name="device" className="w-4 h-4"/>此电话已有学员：{match.map(s=>s.firstName&&s.lastName?`${s.firstName} ${s.lastName}`:s.name||'').join('、')}</p> : null;
                        })()}
                        <p className="text-xs text-gray-400 mt-0.5">提交时间: <span title={pen.submittedAt||''}>{fmtDT(pen.submittedAt)}</span> · 来源: {pen.source==='portal'?'门户网站':'快速报名'} · 状态: {REG_STATUS_ZH[pen.status||'pending']||pen.status}</p>
                    </div>
                </div>
	                {preferenceRows(pen).length > 0 && (
	                    <div className="grid grid-cols-2 gap-2 text-sm">
	                        {preferenceRows(pen).map(row => (
	                            <div key={row.key} className="bg-gray-50 rounded-2xl p-4 border border-gray-100">
	                                <p className="text-xs text-gray-400 mb-1">{row.label}</p>
	                                <p className="font-bold text-gray-700 text-sm">{row.value}</p>
	                            </div>
	                        ))}
	                    </div>
	                )}
                {pen.message && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-gray-700">
                        <p className="inline-flex items-center gap-1.5 text-xs text-amber-500 font-bold mb-1"><Icon name="chat" className="w-4 h-4"/>留言</p>
                        <p>{pen.message}</p>
                    </div>
                )}
                <div className="bg-blue-50 border border-blue-100 rounded-2xl p-3 flex flex-wrap items-end gap-2">
                    <div>
                        <label className="text-xs font-bold text-blue-700 mb-1 block">下次跟进</label>
                        <input type="date" value={followUpDates[pen.id]||''}
                            onChange={e=>setFollowUpDates(p=>({...p,[pen.id]:e.target.value}))}
                            className="px-3 py-2 border border-blue-200 rounded-xl text-sm"/>
                    </div>
                    <button onClick={()=>advanceRegistration(pen.id,'contacted')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">已联系</button>
                    <button onClick={()=>advanceRegistration(pen.id,'trial_booked')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">已约试听</button>
                    <button onClick={()=>advanceRegistration(pen.id,'waiting')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">继续跟进</button>
                </div>
                <div className="flex items-end gap-3 pt-2 border-t border-gray-100">
                    <div className="flex-1">
                        <label className="text-xs font-bold text-gray-500 mb-1 block">初始课时数</label>
                        <input type="number" min="0" placeholder="0"
                            value={approveCredits[pen.id]??''}
                            onChange={e=>setApproveCredits(p=>({...p,[pen.id]:e.target.value}))}
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl font-bold text-xl focus:ring-2 focus:ring-indigo-500 outline-none text-indigo-700"/>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                        <button onClick={()=>rejectStudent(pen.id)} disabled={busy}
                            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-red-50 active:bg-red-100 text-red-700 border border-red-200 font-bold rounded-xl text-sm min-h-[44px]">拒绝</button>
                        <button onClick={()=>approveStudent(pen.id)} disabled={busy}
                            className="px-5 py-2.5 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="check" className="w-4 h-4"/>批准建档</span></button>
                    </div>
                </div>
            </div>
        );
    })}
    </>}
    {/* E5: explicit duplicate decision — merge or create, never automatic. */}
    {dupPick && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal="true">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-5 space-y-3">
                <p className="font-bold text-sm">疑似已有档案 — {dupPick.fullName}</p>
                <p className="text-xs text-gray-500">发现下列可能是同一名学员的既有档案。并入会把这次报名归到既有学员名下（初始课时也入其账本）；确认是新学员则继续新建。不会自动合并。</p>
                <div className="space-y-2">
                    {dupPick.candidates.map(c => (
                        <button key={c.studentId} disabled={busy}
                            onClick={()=>approveTenant(dupPick.pid, dupPick.fullName, dupPick.credits, c.studentId)}
                            className="w-full text-left px-3 py-2.5 rounded-xl border border-indigo-200 bg-indigo-50 active:bg-indigo-100 min-h-[44px]">
                            <span className="text-sm font-bold text-indigo-800">{c.name}</span>
                            <span className="block text-xs text-gray-500">{[c.phone, c.email].filter(Boolean).join(' · ')}{c.matchedOn?.length ? ` · 命中：${c.matchedOn.join('/')}` : ''}</span>
                            <span className="block text-xs font-bold text-indigo-600 mt-0.5">并入这个档案 →</span>
                        </button>
                    ))}
                </div>
                <div className="flex gap-2 pt-1">
                    <button onClick={()=>setDupPick(null)} disabled={busy}
                        className="flex-1 min-h-[44px] rounded-xl border border-gray-200 text-xs font-bold">取消</button>
                    <button onClick={()=>approveTenant(dupPick.pid, dupPick.fullName, dupPick.credits, null)} disabled={busy}
                        className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold">确认是新学员，新建档案</button>
                </div>
            </div>
        </div>
    )}
</div>
    );
}
