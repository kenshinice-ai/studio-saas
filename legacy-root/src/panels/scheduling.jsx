/* 课程与排课 — 课程目录、每日点名表。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { BalBadge, EmptyState, Icon, PhotoAvatar, StudentPicker, Tabs, TabPanel, TENANT_SLUG } from "../components.jsx";
import { fmtDate, shiftDate, todayISO, v1Api } from "../components.jsx";
import { PrivateLessonsPanel } from "./private_lessons.jsx";

export function CoursesSection(props) {
    const {
        archiveCourse, busy, canManageOperations, courseEdit, courses, saveCourse,
        setCourseEdit, setTab,
    } = props;
    return (
<div className="anim space-y-5 max-w-6xl mx-auto">
    <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
            <h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800"><Icon name="calendar" className="w-5 h-5"/>课程目录</h2>
            <p className="text-sm text-gray-500 mt-1">维护可被固定课表引用的课程条目；公开课表是否展示详情仍由 Studio Admin 控制。</p>
        </div>
        {/* 从课程目录过来的人要建的是固定班次，不是给今天的人签到 —— 这个入口
            显式带上分区。 */}
        <button type="button" onClick={()=>setTab('roster', {section:'plan'})} className="min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold">查看课程安排 →</button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-[1.618fr_1fr] gap-5 items-start">
        <section id="courseManager" className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-3 scroll-mt-24" aria-labelledby="course-list-title">
            <div className="flex items-center justify-between gap-3"><div><h3 id="course-list-title" className="font-bold text-gray-900">已启用课程</h3><p className="text-xs text-gray-400 mt-0.5">{courses.length} 门课程</p></div>{canManageOperations && <button type="button" onClick={()=>setCourseEdit({name:'',description:'',ageRange:'',durationMinutes:60,priceAud:''})} className="min-h-[44px] px-3 rounded-xl bg-indigo-600 text-white text-xs font-bold"><Icon name="plus" className="w-4 h-4 inline mr-1"/>添加课程</button>}</div>
            {courses.length === 0 && <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="还没有课程" sub="先添加一门课程，再回到课程安排关联固定班次。" action={canManageOperations ? '添加第一门课程' : ''} onAction={canManageOperations ? ()=>setCourseEdit({name:'',description:'',ageRange:'',durationMinutes:60,priceAud:''}) : undefined}/>}
            <div className="space-y-2">
                {courses.map(course => <article key={course.id} className="rounded-2xl border border-gray-200 bg-gray-50 p-4 flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 inline-flex items-center justify-center flex-shrink-0"><Icon name="calendar" className="w-5 h-5"/></div>
                    <div className="min-w-0 flex-1"><h4 className="font-bold text-gray-900 truncate">{course.name}</h4><p className="text-xs text-gray-500 mt-1">{[course.age_range && `适龄 ${course.age_range}`,course.duration_minutes && `${course.duration_minutes} 分钟`,course.price_aud_cents ? `AUD ${(course.price_aud_cents/100).toFixed(2)}` : '未标价'].filter(Boolean).join(' · ')}</p>{course.description && <p className="text-sm text-gray-600 mt-2 leading-relaxed">{course.description}</p>}</div>
                    {canManageOperations && <div className="flex items-center gap-1 flex-shrink-0"><button type="button" onClick={()=>setCourseEdit({id:course.id,name:course.name,description:course.description||'',ageRange:course.age_range||'',durationMinutes:course.duration_minutes||60,priceAud:course.price_aud_cents ? String(course.price_aud_cents/100) : ''})} className="min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-100">编辑</button><button type="button" onClick={()=>archiveCourse(course)} aria-label={`归档课程 ${course.name}`} className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50"><Icon name="archiveBox" className="w-4 h-4"/></button></div>}
                </article>)}
            </div>
        </section>
        <aside className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5" aria-labelledby="course-help-title">
            <h3 id="course-help-title" className="font-bold text-gray-900">这组信息会影响什么？</h3>
            <div className="mt-3 space-y-3 text-sm text-gray-600 leading-relaxed"><p><strong className="text-gray-800">课程名称和简介</strong>：供固定课表关联，是否对外显示取决于 Studio Admin 的公开课表开关。</p><p><strong className="text-gray-800">适龄段、时长和价格</strong>：用于公开课程详情和内部排课参考，不会改动已经保存的排课。</p><p className="rounded-xl bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-800">归档不是删除。历史排课仍保留原课程名称，新排课不会再出现已归档课程。</p></div>
        </aside>
    </div>
    {courseEdit && canManageOperations && <div className="fixed inset-0 z-[70] bg-black/40 flex items-end md:items-center justify-center p-0 md:p-4" role="dialog" aria-modal="true" aria-labelledby="course-editor-title" onClick={()=>setCourseEdit(null)}>
        <div className="bg-white w-full md:max-w-xl rounded-t-2xl md:rounded-2xl p-5 md:p-6 space-y-4" onClick={e=>e.stopPropagation()}>
            <div><h3 id="course-editor-title" className="text-lg font-bold text-gray-900">{courseEdit.id ? '编辑课程' : '添加课程'}</h3><p className="text-xs text-gray-500 mt-1">带 * 为必填；保存后可在课程安排中关联。</p></div>
            <label className="block text-sm font-bold text-gray-700">课程名称 *<input id="course-name" type="text" required value={courseEdit.name} onChange={e=>setCourseEdit(p=>({...p,name:e.target.value}))} placeholder="例如：儿童油画基础" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/><span className="block text-xs font-normal text-gray-400 mt-1">用于内部排课和公开课表标题。</span></label>
            <label className="block text-sm font-bold text-gray-700">课程简介 <span className="font-normal text-gray-400">选填</span><textarea rows="3" value={courseEdit.description} onChange={e=>setCourseEdit(p=>({...p,description:e.target.value}))} placeholder="介绍课程内容、适合的学习目标" className="mt-1 w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/><span className="block text-xs font-normal text-gray-400 mt-1">会随公开课表配置显示给访客。</span></label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><label className="block text-sm font-bold text-gray-700">适龄段 <span className="font-normal text-gray-400">选填</span><input type="text" value={courseEdit.ageRange} onChange={e=>setCourseEdit(p=>({...p,ageRange:e.target.value}))} placeholder="6–9 岁" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label><label className="block text-sm font-bold text-gray-700">时长（分钟） *<input type="number" min="1" required value={courseEdit.durationMinutes} onChange={e=>setCourseEdit(p=>({...p,durationMinutes:e.target.value}))} className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label><label className="block text-sm font-bold text-gray-700">价格（AUD） <span className="font-normal text-gray-400">选填</span><input type="number" min="0" step="0.01" value={courseEdit.priceAud} onChange={e=>setCourseEdit(p=>({...p,priceAud:e.target.value}))} placeholder="0.00" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label></div>
            <div className="flex gap-2 pt-1"><button type="button" onClick={()=>setCourseEdit(null)} className="flex-1 min-h-[48px] rounded-xl border border-gray-300 text-sm font-bold text-gray-600">取消</button><button type="button" onClick={saveCourse} disabled={busy} className="flex-1 min-h-[48px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">{busy?'保存中…':'保存课程'}</button></div>
        </div>
    </div>}
</div>
    );
}


/* 排课 #7: a <details> popover is not a menu — the browser leaves it open
   after an item is chosen, so it kept covering the row it had just changed.
   Closing on the container catches every item, including the `sms:` link that
   the five hand-written closers below it never covered. */
const closeMenu = (e) => { const menu = e.currentTarget.closest('details'); if (menu) menu.open = false; };

export function RosterSection(props) {
    const {
        WEEKDAYS, addToRoster, applyGroup, availRoster, batchCheckIn, busy,
        canExportData, canManageOperations, canWriteAttendance, canWriteScheduling, checkIn, checkInWindow, copyRosterDaily, copyRosterReminders,
        copyText, courses, dayIds, db, defaultClassTime, deleteGroup,
        deleteSchedule, groupToSchedule, grpSel, icsBusy, loadSchedules, nextOccurrence,
        openIcsPreview, rDate, rOneToOne, rPick, rTime, removeFromRoster,
        renderMessage, renewTh, restoreCancellation, rosterDone, rosterMetaFor, rosterSlotFor,
        saveCancellation, saveGroup, saveSchedule, schedCancel, schedEdit, schedOverlap,
        rosterSection, schedPick, scheduleLoadError, scheduledForDate, schedules,
        setGrpSel, setRDate, setRosterSection,
        setROneToOne, setRPick, setRTime, setSchedCancel, setSchedEdit, setSchedPick,
        setTab, showToast, sortedAZ, teachableMembers, tenantDisplayName, undoCheckIn,
        updateRosterEntry,
    } = props;
    /* 阶段二 · 乙：这一页分成「今日签到」和「排课设置」两个标签。

       版面收益是边际的（实测净 −83px，方案预测 60–110px）。做它的理由是
       角色：固定课表的增删改在 `@tenant_admin_required` 后面，一对一面板的
       canWrite 是 canWriteScheduling。对 teacher 和助教，整个「排课设置」
       半边都是按不动的东西 —— 放在页尾是「不挡路」，放进另一个标签才是
       「与我无关」。实测按钮数 55 → 26。

       日期导航、迷你周视图、当日概览条留在标签条**之上**：它们是两个职能
       共用的上下文，切标签时不该动。它们也整块留在 `.cms-roster-planner`
       里没有被拆散 —— 那张卡声明了 `container: roster-planner / inline-size`
       (index.html:619)，窄屏日期栏的栅格由 `@container` 规则给；把日期导航
       挪出这张卡，那条规则会静默失效，而卡的白底正是它的视觉。 */
    const rosterTabs = Boolean(TENANT_SLUG);
    /* 单店模式（根目录，TENANT_SLUG 为空）下固定课表与一对一都不渲染，
       「排课设置」会是一个空面板 —— 那时不出标签条，签到内容直接渲染。
       没有 tab 指向它的时候也不该留下一个 role="tabpanel"。 */
    const RosterPanel = ({name, active, children}) => rosterTabs
        ? <TabPanel idBase="roster" name={name} active={active}>{children}</TabPanel>
        : <div className="space-y-4">{children}</div>;
    return (
<div className="anim space-y-4">
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="calendar" className="w-4 h-4"/>课程安排</h2>
    {scheduleLoadError && <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <span className="flex-1">{scheduleLoadError}</span>
        <button onClick={loadSchedules} className="rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]">重试</button>
    </div>}

    <div className="cms-roster-planner bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
            <div className="w-full">
                <label className="cms-roster-date-label text-xs font-bold text-gray-500 mb-1 block">课程日期</label>
                <div className="cms-roster-date-nav">
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,-1))}
                        aria-label="前一天" className="cms-roster-date-button"><Icon name="chevronLeft" className="w-4 h-4"/></button>
                    <button type="button" onClick={()=>setRDate(todayISO())}
                        aria-current={rDate===todayISO()?'date':undefined} className="cms-roster-today">今天</button>
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,1))}
                        aria-label="后一天" className="cms-roster-date-button"><Icon name="chevronRight" className="w-4 h-4"/></button>
                    <input type="date" value={rDate} onChange={e=>setRDate(e.target.value)}
                        aria-label="选择课程日期"
                        className="w-full px-3 py-3 min-h-[50px] border border-gray-300 rounded-xl font-bold text-gray-900 focus:ring-2 focus:ring-indigo-500 outline-none"/>
                </div>
            </div>

    {/* B1: 迷你周视图 — 本周七天一键切换，含每日应到人数 */}
    <div className="cms-roster-week" role="group" aria-label="本周课程日期">
        {(() => {
            const anchor = new Date(`${rDate}T12:00:00`);
            const monday = new Date(anchor); monday.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
            return [0,1,2,3,4,5,6].map(i => {
                const d = new Date(monday); d.setDate(monday.getDate() + i);
                const iso = d.toLocaleDateString('en-CA');
                const manual = db.rosters[iso] || [];
                const sched = schedules.filter(sc => sc.weekday === d.getDay()).flatMap(sc => sc.students.map(st => st.id));
                const n = new Set([...sched, ...manual]).size;
                const isSel = iso === rDate, isToday = iso === todayISO();
                return (
                    <button key={iso} type="button" onClick={()=>setRDate(iso)}
                        aria-current={isSel?'date':undefined}
                        aria-label={`${WEEKDAYS[d.getDay()]} ${fmtDate(iso)}，${n} 人`}
                        className={`cms-roster-week-day ${isSel?'is-selected':''} ${isToday?'is-today':''}`}>
                        <p className="text-[10px] opacity-70">{WEEKDAYS[d.getDay()]}{isToday?'·今':''}</p>
                        <p className="text-sm font-bold">{d.getDate()}</p>
                        <p className="text-[10px] font-bold opacity-80">{n>0?n:'—'}</p>
                    </button>
                );
            });
        })()}
    </div>

    {/* B1: 当日概览条 — 应到/已签/未签/低余额 */}
    {(() => {
        const valid = dayIds.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived;});
        const done = valid.filter(id=>rosterDone.has(id)).length;
        const low = valid.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&(parseInt(s.balance,10)||0)<=renewTh;}).length;
        if (!valid.length) return null;
        return (
            <div className="cms-roster-summary" aria-live="polite">
                <strong>{rDate===todayISO()?'今日':fmtDate(rDate)} · {valid.length} 人</strong>
                <span className="is-success">已签到 {done}</span>
                <span>待上课 {valid.length-done}</span>
                {low>0 && <span className="is-warning"><Icon name="warning" className="inline-block w-3.5 h-3.5 mr-1"/>低余额 {low}</span>}
                {/* 按钮灰掉了要说得出为什么。概览条是这一天唯一的说明位置。 */}
                {checkInWindow.reason && <span className="is-warning"><Icon name="warning" className="inline-block w-3.5 h-3.5 mr-1"/>{checkInWindow.reason}</span>}
            </div>
        );
    })()}
    </div>

    {rosterTabs && <Tabs idBase="roster" label="课程安排分区" value={rosterSection} onChange={setRosterSection}
        items={[{value:'checkin', label:'今日签到', icon:'check'},
                {value:'plan', label:'排课设置', icon:'settings'}]}/>}

    <RosterPanel name="checkin" active={rosterSection === 'checkin'}>

        {/* 0022: slots. Several people at the same time may be one class, or may be
            a one-to-one that was booked into an occupied hour — which the flat
            list could not show, so it surfaced when both families arrived. */}
        {(()=>{
            const ids = dayIds.filter(id=>{const st=db.students.find(x=>x.id===id);return st&&!st.archived;});
            if (!ids.length) return null;
            const slots = {};
            ids.forEach(id=>{
                const t = (rosterSlotFor(rDate,id) || '').trim() || '__unset';
                (slots[t] = slots[t] || []).push(id);
            });
            const groups = Object.entries(slots).sort(([a],[b]) =>
                a==='__unset' ? 1 : b==='__unset' ? -1 : a.localeCompare(b));
            const nameOf = id => db.students.find(x=>x.id===id)?.name || '';
            /* This panel grows with the day: it prints every name again, above the
               list those names are in. On a ten-student Saturday that is ~400px on
               a phone, which put the first student row's bottom at 845 against an
               844px viewport — the reorder's whole point, undone by a summary of
               the thing it was meant to reveal. So it folds. The one thing it says
               that the list below cannot is the 1-on-1 collision, and that opens
               itself. */
            const conflicted = groups.some(([, arr]) =>
                arr.filter(id=>!!rosterMetaFor(rDate,id).oneToOne).length>0 && arr.length>1);
            return (
                <details className="cms-roster-slot-panel" open={conflicted}>
                    <summary className="list-none cursor-pointer min-h-[44px] flex items-center justify-between gap-3">
                        <span className="font-bold text-sm text-gray-800 inline-flex items-center gap-2">
                            <Icon name="clock" className="w-4 h-4"/>时段安排
                            <span className="text-xs font-normal text-gray-400">
                                {conflicted ? '有 1 对 1 时间冲突' : `${groups.length} 个时段`}
                            </span>
                        </span>
                        <span className="text-indigo-600" aria-hidden="true">⌄</span>
                    </summary>
                    <div className="space-y-1.5 pt-2">
                    {groups.map(([t,arr])=>{
                        const soloIds = arr.filter(id=>!!rosterMetaFor(rDate,id).oneToOne);
                        const clash = soloIds.length>0 && arr.length>1;
                        return (
                            <div key={t} className={`cms-roster-slot-row ${clash?'has-conflict':''}`}>
                                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                                    <span className="font-bold text-gray-800 min-w-[56px]">{t==='__unset'?'时间未设置':t}</span>
                                    <span className="px-2 py-0.5 rounded-full bg-white border border-gray-200 font-bold">{arr.length} 人</span>
                                    <span className="text-gray-500">{arr.map(nameOf).filter(Boolean).join('、')}</span>
                                </div>
                                {soloIds.length>0 && (
                                    <p className={`mt-1 text-xs font-bold ${clash?'text-red-700':'text-indigo-600'}`}>
                                        {clash
                                            ? `1 对 1 时间冲突：${soloIds.map(nameOf).join('、')} 与同时段其他排课重叠`
                                            : `1 对 1：${soloIds.map(nameOf).join('、')}`}
                                    </p>
                                )}
                            </div>
                        );
                    })}
                    </div>
                </details>
            );
        })()}

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
            <div className="bg-gray-50 border-b px-4 py-3 flex justify-between items-center gap-2 flex-wrap">
                <p className="font-bold text-sm text-gray-800">{fmtDate(rDate)} · {dayIds.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived;}).length} 人{scheduledForDate.length>0 && <span className="text-xs font-normal text-indigo-500 ml-1">{`（课表 ${scheduledForDate.length} 班）`}</span>}</p>
                {dayIds.length>0 && <details className="cms-day-actions-mobile">
                    <summary><Icon name="ellipsis" className="w-4 h-4"/>当日操作</summary>
                    <div className="cms-roster-menu" onClick={closeMenu}>
                        {canExportData && <button onClick={()=>openIcsPreview('roster')} disabled={icsBusy}><Icon name="calendar" className="w-4 h-4"/>导出当日 ICS</button>}
                        <button onClick={copyRosterDaily}><Icon name="clipboard" className="w-4 h-4"/>复制日报</button>
                        {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile;}) && <button onClick={copyRosterReminders}><Icon name="chat" className="w-4 h-4"/>批量提醒</button>}
                        {canWriteAttendance && dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.balance>0;}) && <button onClick={batchCheckIn} disabled={busy||!checkInWindow.ok} title={checkInWindow.ok ? undefined : checkInWindow.reason}><Icon name="check" className="w-4 h-4"/>批量签到并扣课时</button>}
                    </div>
                </details>}
                <div className="cms-day-actions-desktop flex gap-2 flex-wrap">
                    {dayIds.length>0 && canExportData && (
                        <button onClick={()=>openIcsPreview('roster')} disabled={icsBusy}
                            className="border border-gray-200 bg-white text-gray-700 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px] inline-flex items-center gap-1.5 disabled:opacity-50">
                            <Icon name="calendar" className="w-4 h-4"/>导出当日 ICS
                        </button>
                    )}
                    {dayIds.length>0 && (
                        <button onClick={copyRosterDaily} className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>日报</span></button>
                    )}
                    {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile;}) && (
                        <button onClick={copyRosterReminders} className="bg-white border border-green-300 active:bg-green-50 text-green-700 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="chat" className="w-4 h-4"/>批量提醒</span></button>
                    )}
                    {canWriteAttendance && dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.balance>0;}) && (
                        <button onClick={batchCheckIn} disabled={busy||!checkInWindow.ok}
                            title={checkInWindow.ok ? undefined : checkInWindow.reason}
                            className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 disabled:opacity-40 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="bolt" className="w-4 h-4"/>批量签到并扣课时</button>
                    )}
                </div>
            </div>
            <div className="cms-roster-list divide-y divide-gray-100">
                {!dayIds.length && <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="今天还没有排课"
                    sub={TENANT_SLUG?'在下方「调整这一天的名单」加人；要让每周都自动排入，用页尾的「固定课表」建一个班次。':'在下方「调整这一天的名单」添加学员即可开始今天的排课。'}
                    action={canWriteAttendance ? '添加学员' : ''} onAction={canWriteAttendance ? ()=>{const el=document.getElementById('rosterAddStudent'); if(el) el.scrollIntoView({behavior:'smooth',block:'center'});} : undefined}/>}
                {/* Fix #3: skip archived students in roster */}
                {dayIds.map(sid => {
                    const s = db.students.find(x=>x.id===sid);
                    if (!s || s.archived) return null;
                    const entry = rosterMetaFor(rDate,sid);
                    const isDone = rosterDone.has(s.id);
                    const lowBal = (parseInt(s.balance,10)||0) <= renewTh && !isDone;   /* A5: 课前低余额预警（v4.5） */
                    const slot = rosterSlotFor(rDate,sid);
                    const rosterStatus = isDone ? '已签到' : entry.status==='makeup' ? '补课' : '待上课';
                    return (
                        <div key={sid} className={`cms-roster-row hover-row ${lowBal?'is-low':''}`}>
                            <div className="cms-roster-info">
                                <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 min-w-0 flex-wrap">
                                        <p className="font-bold text-gray-900 truncate">{s.name}</p>
                                        {entry.oneToOne && <span className="text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2 py-0.5">1 对 1</span>}
                                        <span className={`text-[11px] font-bold rounded-full px-2 py-0.5 border ${isDone?'bg-green-50 border-green-200 text-green-700':entry.status==='makeup'?'bg-blue-50 border-blue-200 text-blue-700':'bg-gray-50 border-gray-200 text-gray-600'}`}>{rosterStatus}</span>
                                    </div>
                                    <p className="text-xs text-gray-400 truncate">{[s.mobile||'未填写手机', slot, entry.note].filter(Boolean).join(' · ')}</p>
                                </div>
                                <BalBadge n={s.balance}/>
                            </div>
                            {/* Correcting the slot in place: re-adding the student would
                                reset their source and status. Only in tenant mode —
                                the legacy JSON store has no entry id to patch. */}
                            <div className={`cms-roster-actions ${lowBal?'has-reminder':''}`}>
                            {TENANT_SLUG && entry.id && canWriteAttendance && (
                                <input type="time" defaultValue={entry.classTime||''}
                                    aria-label={`${s.name} 的上课时间`}
                                    onChange={e=>{
                                        const entryId = entry.id;
                                        updateRosterEntry(entryId, {classTime: e.target.value || ''})
                                            .then(()=>showToast(e.target.value?`${s.name} 上课时间改为 ${e.target.value}`:`${s.name} 已清除上课时间`))
                                            .catch(err=>showToast(err.message||'时间未能保存', 'error'));
                                    }}
                                    className="cms-roster-time px-2 py-2 border border-gray-300 rounded-xl bg-white text-xs font-bold min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500"/>
                            )}
                            {TENANT_SLUG && (!entry.id || !canWriteAttendance) && (
                                <span className="cms-roster-time px-3 py-2 border border-gray-200 rounded-xl bg-gray-50 text-xs font-bold text-gray-700 min-h-[44px] inline-flex items-center">
                                    {slot || '未设时间'}
                                </span>
                            )}
                            {lowBal && (
                                <button onClick={()=>{
                                    const msg = renderMessage('renewal',
                                        '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
                                        {student:s.name, balance:s.balance, note:(parseInt(s.balance,10)||0)===0?'（已用完）':''});
                                    copyText(msg, `已复制给 ${s.name} 的催费提醒`);
                                }} className="cms-roster-reminder"><Icon name="chat" className="w-4 h-4"/>续费提醒</button>
                            )}
                            {(isDone || !canWriteAttendance)
                                ? <button disabled className="cms-roster-primary is-done"><Icon name="check" className="w-4 h-4"/>{isDone?'已签到':'待上课'}</button>
                                : <button onClick={()=>checkIn(s.id,s.name)} disabled={busy||s.balance<=0||!checkInWindow.ok}
                                    title={checkInWindow.ok ? undefined : checkInWindow.reason}
                                    aria-label={`为 ${s.name} 签到并扣 1 课时`} className="cms-roster-primary"><Icon name="check" className="w-4 h-4"/>{!checkInWindow.ok?'不可签到':(s.balance>0?'签到并扣 1 课时':'余额不足')}</button>}
                            <details className="cms-roster-more" name="roster-student-actions">
                                <summary aria-label={`${s.name} 更多操作`}><Icon name="ellipsis" className="w-5 h-5"/></summary>
                                <div className="cms-roster-menu" onClick={closeMenu}>
                                    <div className="cms-roster-menu__context">
                                        <strong>{s.name}</strong>
                                        <span>{fmtDate(rDate)} · {slot || '时间未设置'} · 余额 {s.balance}</span>
                                    </div>
                                    {entry.id && canWriteAttendance && <>
                                        <p className="cms-roster-menu__label">课程状态</p>
                                        <button onClick={()=>{updateRosterEntry(entry.id,{status:'scheduled'}).then(()=>showToast(`${s.name} 已标记为待上课`)).catch(err=>showToast(err.message||'课程状态未能保存','error'));}} disabled={busy||entry.status!=='makeup'} aria-current={entry.status!=='makeup'?'true':undefined}><Icon name="check" className="w-4 h-4"/>待上课</button>
                                        <button onClick={()=>{updateRosterEntry(entry.id,{status:'makeup'}).then(()=>showToast(`${s.name} 已标记为补课`)).catch(err=>showToast(err.message||'课程状态未能保存','error'));}} disabled={busy||entry.status==='makeup'} aria-current={entry.status==='makeup'?'true':undefined}><Icon name="refresh" className="w-4 h-4"/>补课</button>
                                        <div className="cms-roster-menu__separator"/>
                                    </>}
                                    {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent(`提醒：您的上课时间是 ${fmtDate(rDate)}${slot?` ${slot}`:''}，请准时到课。${tenantDisplayName} 期待见到您！`)}`}><Icon name="chat" className="w-4 h-4"/>发短信提醒</a>}
                                    {entry.id && canWriteAttendance && <button onClick={()=>{updateRosterEntry(entry.id,{oneToOne:!entry.oneToOne}).then(()=>showToast(entry.oneToOne?'已改为普通班课':'已标记为 1 对 1')).catch(err=>showToast(err.message||'排课类型未能保存','error'));}} disabled={busy}><Icon name="users" className="w-4 h-4"/>{entry.oneToOne?'改为普通班课':'标记为 1 对 1'}</button>}
                                    {isDone && canWriteAttendance && <button onClick={()=>{undoCheckIn(s.id,s.name);}} disabled={busy}><Icon name="refresh" className="w-4 h-4"/>撤销本日签到</button>}
                                    {entry.id && canWriteAttendance
                                        ? <button onClick={()=>{removeFromRoster(s.id);}} disabled={busy} className="is-danger"><Icon name="trash" className="w-4 h-4"/>移出本日课程安排</button>
                                        : <p className="cms-roster-menu__source"><Icon name="calendar" className="w-4 h-4"/>{entry.id?'当前角色只读':'来自固定课表，需在页尾的固定课表中调整'}</p>}
                                </div>
                            </details>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>

        {/* 「加人」和「套模板」是当天的收尾动作，不是开场动作：走进教室先看的是
            名单，改名单是发现少了谁之后才做的事。放在名单之后，两个工作室都
            少滚一屏 —— 小工作室的 owner 一天改几次，成熟机构的老师一周不改一次。
            `.cms-roster-tools` 复用 planner 的容器名，否则 `.cms-roster-add-fields`
            的窄屏栅格会跟着它一起搬出 `@container roster-planner` 的作用域。 */}
        {(canWriteAttendance || canManageOperations) && (
        <div className="cms-roster-tools bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
            <p className="inline-flex items-center gap-1.5 font-bold text-sm text-gray-800"><Icon name="plus" className="w-4 h-4"/>调整这一天的名单</p>
        {/* 这一段以下每一个控件打的都是要 `attendance:write` 的接口（/daily-roster
            的增删改、签到、撤销签到）。在此之前它们只由 `busy` 把关 —— 能看到这一页
            的角色恰好都有那把钥匙，所以没出过事，但那是导航表在保护钱路径，不是权限
            在保护。加一个角色进 roleTabs 就会翻车。 */}
        {canWriteAttendance && <div className="cms-roster-add" id="rosterAddStudent">
            <div className="cms-roster-add-fields">
                <div className="min-w-0">
                    <label className="text-xs font-bold text-gray-500 mb-1 block">添加学员</label>
                    <StudentPicker students={availRoster} value={rPick} onChange={setRPick} placeholder="搜索并选择学员..."/>
                </div>
                <div>
                    <label className="text-xs font-bold text-gray-500 mb-1 block">上课时间</label>
                    <input type="time" value={rTime} onChange={e=>setRTime(e.target.value)}
                        aria-label="上课时间"
                        className="w-full px-3 py-3 border border-gray-300 rounded-xl bg-white text-sm font-bold min-h-[50px] outline-none focus:ring-2 focus:ring-indigo-500"/>
                </div>
                <button onClick={addToRoster} disabled={!rPick||busy}
                    className="cms-roster-add-button bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-bold text-sm min-h-[50px]">
                    <Icon name="plus" className="w-4 h-4"/>{rPick?'加入课程安排':'请先选择学员'}
                </button>
            </div>
            <label className="inline-flex items-center gap-2 mt-2 text-xs font-bold text-gray-500 min-h-[44px]">
                <input type="checkbox" checked={rOneToOne} onChange={e=>setROneToOne(e.target.checked)} className="w-4 h-4"/>
                1 对 1（同时段还有其他人时会提示冲突）
            </label>
        </div>}

        {/* F4b: Advanced batch tools stay available without permanently
            pushing the actual day roster below the fold. */}
        <details className={`group ${canWriteAttendance?'pt-3 border-t border-gray-100':''}`}>
            <summary className="list-none cursor-pointer min-h-[44px] flex items-center justify-between gap-3 text-xs font-bold text-gray-600">
                <span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>班组模板与批量工具</span>
                <span className="text-indigo-600 group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
            </summary>
            <div className="pt-2 flex gap-2 items-center flex-wrap">
            <select value={grpSel} onChange={e=>setGrpSel(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded-xl bg-white text-sm font-medium min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="">-- 选择模板 --</option>
                {Object.keys(db.groups||{}).sort().map(g => <option key={g} value={g}>{`${g}（${(db.groups[g]||[]).length} 人）`}</option>)}
            </select>
            {canWriteAttendance && <button onClick={applyGroup} disabled={!grpSel||busy}
                className="bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">套用到当前日期</button>}
            {/* B: template management stays owner/manager; applying a template to a day is a per-day attendance action */}
            {canManageOperations && <button onClick={saveGroup} disabled={busy}
                className="bg-white text-gray-600 border border-gray-300 active:bg-gray-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">保存当前为模板</button>}
            {canManageOperations && grpSel && <button onClick={deleteGroup} disabled={busy}
                className="bg-white text-red-500 border border-red-200 active:bg-red-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">删除</button>}
            {canManageOperations && TENANT_SLUG && grpSel && <button onClick={groupToSchedule} disabled={busy}
                className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="calendar" className="w-4 h-4"/>转为每周班次</button>}
            </div>
        </details>
        </div>
        )}
    </RosterPanel>

    {rosterTabs && <RosterPanel name="plan" active={rosterSection === 'plan'}>

        {/* 一对一循环课收在一个可折叠区块里，而不是新开一个导航项：它和班课
            回答的是同一个问题（这周谁什么时候上课），只是重复方式不同。默认
            折叠，因为只教班课的工作室不该被一块空面板挡住每天要看的课表。 */}
        {TENANT_SLUG && (
            <details className="border border-indigo-100 rounded-2xl overflow-hidden group">
                <summary className="list-none cursor-pointer min-h-[44px] px-4 py-3 flex items-center justify-between gap-3 bg-indigo-50 text-sm font-bold text-indigo-800">
                    <span className="inline-flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>一对一循环课与补课额度</span>
                    <span className="group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
                </summary>
                <div className="p-3 bg-white">
                    <PrivateLessonsPanel api={v1Api} showToast={showToast}
                        canWrite={canWriteScheduling} canWritePolicy={canManageOperations}
                        students={db.students.filter(s=>!s.archived)} />
                </div>
            </details>
        )}

        {/* A1: 每周课表 — 固定班次自动生成当日课程安排 */}
        {TENANT_SLUG && (
        <details id="rosterSchedules" className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden group">
            <summary className="list-none cursor-pointer min-h-[52px] px-4 py-3 flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2 min-w-0">
                    <Icon name="calendar" className="w-4 h-4 text-gray-500"/>
                    <span><span className="block text-sm font-bold text-gray-800">固定课表</span><span className="block text-xs font-normal text-gray-400">{schedules.length ? `${schedules.length} 个每周班次` : '创建每周自动排课班次'}</span></span>
                </span>
                <span className="text-indigo-600 group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
            </summary>
            <div className="p-4 space-y-3 border-t border-gray-100">
            <div className="flex justify-between items-center gap-2 flex-wrap">
                <p className="inline-flex items-center gap-1.5 font-bold text-sm text-gray-800"><Icon name="calendar" className="w-4 h-4"/>每周课表 <span className="text-xs font-normal text-gray-400">固定班次按周几自动排入当日名单</span></p>
                <div className="flex items-center gap-2 flex-wrap">
                    <button onClick={()=>openIcsPreview('schedule')} disabled={icsBusy || schedules.length===0}
                        title={schedules.length ? '导出所有固定班次，不包含学员姓名' : '请先新增固定班次'}
                        className="inline-flex items-center gap-1.5 border border-indigo-200 bg-indigo-50 text-indigo-700 px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px] active:bg-indigo-100 disabled:opacity-50">
                        <Icon name="download" className="w-3.5 h-3.5"/>固定课表 ICS
                    </button>
                    {/* B: schedule templates hit owner/manager-only endpoints — hide from teacher/staff */}
                    {canManageOperations && <button onClick={()=>setSchedEdit({label:'', weekday:new Date().getDay(), startTime:defaultClassTime, durationMinutes:60, capacity:10, studentIds:[], courseId:'', teacherUserId:'', isPublic:false, room:''})}
                        className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="plus" className="w-3.5 h-3.5"/>新增班次</button>}
                </div>
            </div>
            {schedules.length===0 && !schedEdit && (
                <p className="text-xs text-gray-400">还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排课里。</p>
            )}
            {schedules.length>0 && (
                <div className="flex flex-wrap gap-2">
                    {schedules.map(sc => (
                        <div key={sc.id} className={`border rounded-xl px-3 py-2 ${sc.weekday===new Date(`${rDate}T12:00:00`).getDay()?'border-indigo-300 bg-indigo-50':'border-gray-200 bg-gray-50'}`}>
                            <p className="text-sm font-bold text-gray-800">{WEEKDAYS[sc.weekday]} {sc.startTime} · {sc.label||'未命名班次'}</p>
                            <p className="text-[11px] text-gray-500 mt-0.5">
                                {sc.students.length}/{sc.capacity} 人 · {sc.durationMinutes} 分钟
                                {sc.teacherName && <> · {sc.teacherName} 老师</>}
                                {sc.room && <> · {sc.room}</>}
                            </p>
                            {/* v8.8.0: 公开状态是一句话，不是一个只有开发者看得懂的图标。
                                没有这一行，Owner 只能靠打开编辑器逐个班次确认哪些已经
                                对外可见 —— 而这正是最不该靠回忆的一件事。 */}
                            <p className="text-[11px] mt-0.5">
                                {sc.isPublic
                                    ? <span className="text-green-700">● 已公开{sc.teacherUserId && !sc.teacherIsPublic ? '（不显示老师姓名）' : ''}</span>
                                    : <span className="text-gray-400">○ 仅内部可见</span>}
                            </p>
                            {(sc.cancellations||[]).length>0 && (
                                <div className="mt-1 space-y-0.5">
                                    {sc.cancellations.map(c=>(
                                        <p key={c.date} className="text-[11px] text-amber-700">
                                            {c.date} 停课{c.note?` · ${c.note}`:''}
                                            {canManageOperations && <button onClick={()=>restoreCancellation(sc, c.date)} disabled={busy}
                                                className="ml-1.5 font-bold text-indigo-600 active:text-indigo-800">恢复</button>}
                                        </p>
                                    ))}
                                </div>
                            )}
                            <div className="flex items-center gap-2 mt-1">
                                {canManageOperations && <>
                                <button onClick={()=>setSchedEdit({id:sc.id, label:sc.label, weekday:sc.weekday, startTime:sc.startTime, durationMinutes:sc.durationMinutes, capacity:sc.capacity, studentIds:sc.students.map(st=>st.id), courseId:sc.courseId||'', teacherUserId:sc.teacherUserId||'', isPublic:!!sc.isPublic, room:sc.room||''})}
                                    className="text-[11px] font-bold text-indigo-600 active:text-indigo-800">编辑</button>
                                <button onClick={()=>setSchedCancel({id:sc.id, label:sc.label||'未命名班次', date:nextOccurrence(sc.weekday), note:''})}
                                    className="text-[11px] font-bold text-amber-600 active:text-amber-800">停课</button>
                                <button onClick={()=>deleteSchedule(sc)} className="text-[11px] font-bold text-red-500 active:text-red-700">删除</button>
                                </>}
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {schedEdit && (
                <div className="border-t border-gray-100 pt-3 space-y-3">
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
                        <div className="col-span-2">
                            <label className="text-xs font-bold text-gray-500 mb-1 block">班次名称</label>
                            <input value={schedEdit.label} onChange={e=>setSchedEdit(p=>({...p,label:e.target.value}))} placeholder="如：周三素描班"
                                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">周几</label>
                            <select value={schedEdit.weekday} onChange={e=>setSchedEdit(p=>({...p,weekday:Number(e.target.value)}))}
                                className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                                {WEEKDAYS.map((w,i)=><option key={i} value={i}>{w}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">开始时间</label>
                            <input type="time" value={schedEdit.startTime} onChange={e=>setSchedEdit(p=>({...p,startTime:e.target.value}))}
                                className="w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">容量</label>
                            <input type="number" min="1" value={schedEdit.capacity} onChange={e=>setSchedEdit(p=>({...p,capacity:e.target.value}))}
                                className="w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                        </div>
                    </div>
                    {/* v8.8.0: 关联课程、授课老师、地点。前两项都是选填 ——
                        一个只在内部用的班次不需要这些，逼着填只会让人乱填。 */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">关联课程<span className="font-normal text-gray-400">（选填）</span></label>
                            <select value={schedEdit.courseId||''} onChange={e=>setSchedEdit(p=>({...p,courseId:e.target.value}))}
                                className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                                <option value="">不关联课程</option>
                                {courses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
                            </select>
                            {/* 从「需要它的地方」通向「管理它的地方」。没有这一行，
                                一个空的下拉只会让人以为功能坏了，而不是还没建课程。 */}
                            <p className="text-[11px] text-gray-400 mt-1">
                                {courses.length
                                    ? '关联后，课程简介和适龄段可用于公开课表；未关联时只用班次名称。'
                                    : '还没有课程。'}
                                <button type="button" onClick={()=>{setTab('courses');setTimeout(()=>document.getElementById('courseManager')?.scrollIntoView({block:'center'}),80);}}
                                    className="ml-1 font-bold text-indigo-600 active:text-indigo-800 underline">
                                    {courses.length ? '管理课程' : '去添加课程 →'}
                                </button>
                            </p>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">授课老师<span className="font-normal text-gray-400">（选填）</span></label>
                            <select value={schedEdit.teacherUserId||''} onChange={e=>setSchedEdit(p=>({...p,teacherUserId:e.target.value}))}
                                className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                                <option value="">未指定</option>
                                {teachableMembers.map(m=><option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
                            </select>
                            <p className="text-[11px] text-gray-400 mt-1">指定后，同一位老师同时段被排两处会提示冲突。</p>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">地点 / 教室<span className="font-normal text-gray-400">（选填）</span></label>
                            <input value={schedEdit.room||''} onChange={e=>setSchedEdit(p=>({...p,room:e.target.value}))} placeholder="如：A 教室"
                                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                        </div>
                    </div>
                    {/* 默认不公开。「已排的课」和「对外招生的课」不是同一批：
                        一对一时段、内部补课、给某个家庭留的试听位都在前者里。 */}
                    <label className="flex items-start gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 min-h-[44px] cursor-pointer">
                        <input type="checkbox" checked={!!schedEdit.isPublic}
                            onChange={e=>setSchedEdit(p=>({...p,isPublic:e.target.checked}))}
                            className="mt-0.5 w-4 h-4 accent-indigo-600"/>
                        <span className="flex-1">
                            <span className="text-sm font-bold text-gray-700">在公开课表上展示这个班次</span>
                            <span className="block text-[11px] text-gray-400 mt-0.5">
                                默认不展示。一对一时段、内部补课、留给特定家庭的试听位不应该出现在公网上。
                                {schedEdit.teacherUserId && (() => {
                                    const m = teachableMembers.find(x=>x.user_id===schedEdit.teacherUserId);
                                    return m && !m.show_on_public_timetable
                                        ? <span className="block text-amber-600 mt-0.5">{m.full_name} 尚未同意在公开课表显示姓名，课表会照常展示但不带老师。可在「设置 · 团队与权限」里逐人开启。</span>
                                        : null;
                                })()}
                            </span>
                        </span>
                    </label>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">{`班次学员（${schedEdit.studentIds.length} 人）`}</label>
                        <div className="flex flex-wrap gap-1.5 mb-2">
                            {schedEdit.studentIds.map(id => {
                                const s = db.students.find(x=>x.id===id);
                                return s ? (
                                    <span key={id} className="inline-flex items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full px-2.5 py-1 text-xs font-bold">
                                        {s.name}
                                        <button onClick={()=>setSchedEdit(p=>({...p,studentIds:p.studentIds.filter(x=>x!==id)}))} aria-label="移出" className="text-indigo-400 active:text-red-500 p-1 -m-1 inline-flex items-center justify-center"><Icon name="close" className="w-3 h-3"/></button>
                                    </span>
                                ) : null;
                            })}
                        </div>
                        <div className="flex gap-2">
                            <div className="flex-1">
                                <StudentPicker students={sortedAZ.filter(s=>!schedEdit.studentIds.includes(s.id))} value={schedPick} onChange={setSchedPick} placeholder="搜索并添加学员..."/>
                            </div>
                            <button onClick={()=>{ if(!schedPick) return;
                                if (schedEdit.studentIds.includes(schedPick)) { showToast('该学员已在本班次中', 'warn'); setSchedPick(null); return; }
                                const other = schedules.find(sc => sc.id !== schedEdit.id && schedOverlap(sc, schedEdit) && sc.students.some(st=>st.id===schedPick));
                                if (other) showToast(`注意：该学员同时段已在「${other.label}」，已加入但请确认不冲突`, 'warn');
                                setSchedEdit(p=>({...p,studentIds:[...p.studentIds,schedPick]})); setSchedPick(null); }} disabled={!schedPick}
                                className="bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-4 py-2.5 rounded-xl text-xs font-bold">加入班次</button>
                        </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                        <button onClick={()=>setSchedEdit(null)} className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50">取消</button>
                        <button onClick={saveSchedule} disabled={busy}
                            className="bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold">{schedEdit.id?'保存修改':'创建班次'}</button>
                    </div>
                </div>
            )}
            {/* v8.8.0 停课：固定课表说的是「每周三」，没有办法说「这个周三不上」。
                少了它，公开课表就是一个收不回的承诺 —— 某周停课，网站照旧写着
                16:00，家长白跑一趟。停课那天是划掉并注明原因，不是让它消失：
                消失看起来像网站坏了，标注停课看起来像有人在管。 */}
            {schedCancel && (
                <div className="border-t border-gray-100 pt-3 space-y-3">
                    <p className="text-sm font-bold text-gray-800">标记停课 · {schedCancel.label}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">停课日期</label>
                            <input type="date" value={schedCancel.date} onChange={e=>setSchedCancel(p=>({...p,date:e.target.value}))}
                                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                            <p className="text-[11px] text-gray-400 mt-1">必须落在这个班次上课的那一天，默认已填好下一次。</p>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-gray-500 mb-1 block">原因<span className="font-normal text-gray-400">（选填，会显示给家长）</span></label>
                            <input value={schedCancel.note} onChange={e=>setSchedCancel(p=>({...p,note:e.target.value}))} placeholder="如：公众假期 / 老师培训"
                                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                        </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                        <button onClick={()=>setSchedCancel(null)} className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50">取消</button>
                        <button onClick={saveCancellation} disabled={busy}
                            className="bg-amber-600 active:bg-amber-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold">标记停课</button>
                    </div>
                </div>
            )}
            </div>
        </details>
        )}
    </RosterPanel>}
</div>
    );
}
