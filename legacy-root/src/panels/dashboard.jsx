/* 工作台 — 今日概览、待办入口与经营速览。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { EmptyState, Icon, TENANT_SLUG, daysSince, fmtDate, todayISO } from "../components.jsx";

export function DashboardSection(props) {
    const {
        activityMap, actorRole, actorRoleLabel, allowedTabs, analytics, arSummary,
        bizStats, canViewFinancialAnalytics, canWriteAttendance, canWriteCredits, canWriteStudents, copyText,
        db, inactiveDays, loadSchedules, pendingCount, scheduleLoadError, setFilterBy,
        setGOpen, setGQ, setRDate, setSortBy, setSrch, setTab,
        setTuStu, showToast, todayCheckedCount, todayEffectiveCount,
        renderMessage,
    } = props;
    /* 生日祝福必须走租户自己的文案模板。这里以前把「愿新的一年里画艺大进」
       写死了四处（两处复制、两处 sms: 的 body），于是钢琴、舞蹈、游戏租户的
       家长会收到一句祝他画技进步的短信 —— 而 cms-app.jsx 的注释里，同一类
       坑（写死 "Studio" 一词、结尾调色板 emoji）已经修过一次，这四处是漏网。
       `birthday` 是服务端模板白名单里的键（_shared.py 的 MESSAGE_TEMPLATE_KEYS），
       自带默认文案，不需要新增任何管道。 */
    const birthdayWish = (name) => renderMessage(
        'birthday',
        '{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～',
        {student: name},
    );
    return (
<div className="cms-dashboard-root anim space-y-5">
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="dashboard" className="w-4 h-4"/>工作台</h2>
    {(()=>{
        const actionsByRole = {
            owner:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            platform_super_admin:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            super_admin:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            manager:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['topup','充值与退款',null,'money'],['stats','查看经营统计',null,'trend']],
            teacher:[['roster','今日课程名单',todayEffectiveCount,'calendar'],['students','查找学员',analytics.totalStudents,'users'],['works','上传作品',null,'image'],['logs','查看操作记录',null,'scroll']],
            front_desk:[['pending','处理报名与约课',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['new_student','新建学员',null,'plus'],['topup','充值与退款',null,'money']],
            staff:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','查找学员',analytics.totalStudents,'users'],['works','管理作品',null,'image']],
        };
        const actions = (actionsByRole[actorRole] || actionsByRole.staff).filter(([key])=>allowedTabs.includes(key));
        return <section className="rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm" aria-labelledby="role-workbench-title">
            <div className="flex items-center justify-between gap-3 mb-3"><div><h3 id="role-workbench-title" className="text-sm font-bold text-gray-900">今日重点</h3><p className="text-xs text-gray-400 mt-0.5">按你的角色排列最常用的工作入口</p></div><span className="text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-full px-2.5 py-1">{actorRoleLabel}</span></div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">{actions.slice(0,4).map(([key,label,count,icon])=><button key={key} type="button" onClick={()=>setTab(key)} className="min-h-[62px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:border-indigo-300 hover:bg-indigo-50"><span className="flex items-center gap-1.5 text-xs font-bold text-gray-700"><Icon name={icon} className="w-4 h-4 text-indigo-600"/>{label}</span>{count !== null && <span className="block text-lg font-bold text-indigo-700 mt-1 tabular-nums">{count}</span>}</button>)}</div>
        </section>;
    })()}
    {actorRole==='teacher' && <div className="md:hidden rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
        <p className="text-xs font-bold text-emerald-900 mb-2">教师手机快捷流程 · 3 步完成今日工作</p>
        <div className="grid grid-cols-3 gap-2">
            <button onClick={()=>{setRDate(todayISO());setTab('roster');}}
                className="min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900">1 · 今日名单</button>
            <button onClick={()=>{setGOpen(true);setGQ('');}}
                className="min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900">2 · 找到学员</button>
            <button onClick={()=>{setTab('students');showToast('选择学员后，在作品区上传今日作品。');}}
                className="min-h-[56px] rounded-xl bg-emerald-700 px-2 py-2 text-[11px] font-bold text-white">3 · 上传作品</button>
        </div>
    </div>}
    {scheduleLoadError && <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <span className="flex-1">{scheduleLoadError}</span>
        <button onClick={loadSchedules} className="rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]">重试</button>
    </div>}
    <div className={TENANT_SLUG ? 'cms-dashboard-lead' : ''}>
    {TENANT_SLUG && (
        <div className="cms-command-card bg-gradient-to-br from-indigo-900 to-indigo-700 text-white rounded-2xl p-4 shadow-lg">
            <div className="flex items-center justify-between gap-3 mb-3">
                <div><p className="text-xs text-indigo-200 tracking-wider">TODAY · 今日指挥台</p><p className="font-bold mt-0.5">先处理最需要行动的事项</p></div>
                <span className="text-xs bg-white/10 border border-white/20 px-2.5 py-1 rounded-full">{fmtDate(todayISO())}</span>
            </div>
            {/* E4: every command-strip number opens the exact list it counts —
                低课时 lands on the pre-filtered student list whose cards carry
                the one-tap 快速充值 button (student preselected). */}
            <div className="grid grid-cols-3 gap-2 mb-3">
                {[
                    ['应到',todayEffectiveCount,'人',()=>{setRDate(todayISO());setTab('roster');}],
                    ['已签到',todayCheckedCount,'人',()=>{setRDate(todayISO());setTab('roster');}],
                    ['低课时',analytics.lowBalance.length,'人',()=>{setSortBy('bal-asc');setFilterBy('low');setTab('students');}],
                ].map(([label,value,unit,go])=><button key={label} type="button" onClick={go||undefined} disabled={!go}
                    className={`rounded-xl bg-white/10 border border-white/10 p-2.5 text-left ${go?'active:bg-white/20':''}`}>
                    <p className="text-[11px] text-indigo-200">{label}{go && <span className="ml-1">→</span>}</p>
                    <p className="text-xl font-bold">{value}<span className="text-xs font-normal ml-1">{unit}</span></p></button>)}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {canWriteAttendance && <button onClick={()=>{setRDate(todayISO());setTab('roster');}} className="bg-white text-indigo-800 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>今日排课</span></button>}
                {canWriteStudents && <button onClick={()=>setTab('new_student')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="plus" className="w-4 h-4"/>新建学员</span></button>}
                {allowedTabs.includes('pending') && <button onClick={()=>setTab('pending')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>审核报名</span></button>}
                {canWriteCredits && <button onClick={()=>setTab('topup')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="money" className="w-4 h-4"/>充值结算</span></button>}
            </div>
        </div>
    )}
    <div className="cms-kpi-grid">
        {[{l:'学员总数',      v:`${analytics.totalStudents} 人`,             c:'text-gray-800',    action:()=>{setSortBy('date-desc');setFilterBy('all');setTab('students');}},
          {l:'全部剩余课时',  v:`${analytics.totalBalance} 课时`,             c:'text-indigo-600',  action:()=>{setSortBy('bal-desc');setFilterBy('active');setTab('students');}},
          {l:'今日排课',      v:`${TENANT_SLUG ? todayEffectiveCount : analytics.todayRoster.length} 人`,         c:'text-gray-700',    action:()=>setTab('roster')},
          canViewFinancialAnalytics
            ? {l:'历史总营收', v:`$${analytics.totalRevenue.toFixed(0)}`, c:'text-emerald-600', action:()=>setTab('stats')}
            : {l:'本月出勤', v:`${bizStats?.attended_month || 0} 人次`, c:'text-emerald-600', action:()=>setTab('roster')},
        ].map(({l,v,c,action})=>(
            <button key={l} onClick={action}
                className="bg-white p-4 rounded-2xl shadow-sm border border-indigo-100 text-left w-full active:bg-indigo-50 transition">
                <p className="text-gray-400 text-xs mb-1">{l} <span className="text-indigo-400">→</span></p>
                <p className={`text-2xl font-bold ${c}`}>{v}</p>
            </button>
        ))}
    </div>
    </div>

    {/* ⏰ 今日待办 */}
    {(()=>{
        const todoClear   = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) === 0 && s.lastActive);
        const todoLast    = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) === 1);
        const todoRisk    = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.id]||0) === 0);
        const now = new Date(); now.setHours(0,0,0,0); // normalise to midnight so today's birthdays are included
        /* 逐日向前扫，不要把生日拼成「今年的那一天」再比大小：12 月 29 号看
           1 月 3 号的生日，new Date(今年,0,3) 落在过去，`bd>=now` 为假，这个人
           在跨年那一周整周消失。课程安排页删掉的那块横幅用的就是这个扫法，
           它是两份实现里算得对的那一份。 */
        const bdayWithin = (s, span) => {
            if (!s.birthday || s.archived) return false;
            const mm = parseInt(s.birthday.slice(5,7),10), dd = parseInt(s.birthday.slice(8,10),10);
            if (!mm || !dd) return false;
            for (let i=0;i<span;i++) {
                const d = new Date(now.getFullYear(), now.getMonth(), now.getDate()+i);
                if (d.getMonth()+1===mm && d.getDate()===dd) return true;
                /* 2 月 29 日出生的人，平年没有那一天。旧写法靠 JS 日期溢出
                   （new Date(y,1,29) 自动变成 3 月 1 日）误打误撞接住了他们，
                   精确比对月日就接不住了 —— 平年会整整三年收不到提醒。
                   平年按 3 月 1 日过，这是澳洲常见的处理，也和旧行为一致。 */
                if (mm===2 && dd===29 && d.getMonth()===2 && d.getDate()===1
                    && new Date(d.getFullYear(), 1, 29).getDate() !== 29) return true;
            }
            return false;
        };
        const todoBdayWeek  = db.students.filter(s => bdayWithin(s, 8));
        const todoBdayMonth = db.students.filter(s => { if(!s.birthday||s.archived) return false; return s.birthday.slice(5,7)===String(now.getMonth()+1).padStart(2,'0') && !todoBdayWeek.includes(s); });
        const todoFollowUp = (db.pending||[]).filter(item=>item.nextFollowUpAt && String(item.nextFollowUpAt).slice(0,10)<=todayISO());
        const total = todoClear.length + todoLast.length + todoRisk.length + todoBdayWeek.length + todoBdayMonth.length + todoFollowUp.length;
        if (!total) return null;
        const names = (arr, max=4) => arr.slice(0,max).map(s=>s.name).join('、') + (arr.length>max?` 等${arr.length}人`:'');
        return (
            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
                    <p className="inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm"><Icon name="clock" className="w-4 h-4"/>今日待办</p>
                    <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">{total} 项</span>
                </div>
                <div className="divide-y divide-gray-50">
                    {todoFollowUp.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-700"><Icon name="phone" className="w-4 h-4"/>报名跟进到期 · {todoFollowUp.length} 项</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{todoFollowUp.slice(0,4).map(item=>`${item.firstName||''} ${item.lastName||''}`.trim()).join('、')}</p>
                            </div>
                            <button onClick={()=>setTab('pending')}
                                className="flex-shrink-0 text-xs text-indigo-600 font-bold bg-indigo-50 active:bg-indigo-100 border border-indigo-200 px-3 py-1.5 rounded-xl min-h-[44px]">处理 →</button>
                        </div>
                    )}
                    {todoClear.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-red-700"><Icon name="warning" className="w-4 h-4"/>课时已清零 · {todoClear.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoClear)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('zero');setTab('students');}}
                                className="flex-shrink-0 text-xs text-red-600 font-bold bg-red-50 active:bg-red-100 border border-red-200 px-3 py-1.5 rounded-xl min-h-[44px]">查看 →</button>
                        </div>
                    )}
                    {todoLast.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-orange-700"><Icon name="bolt" className="w-4 h-4"/>最后 1 课时 · {todoLast.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoLast)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('low');setTab('students');}}
                                className="flex-shrink-0 text-xs text-orange-600 font-bold bg-orange-50 active:bg-orange-100 border border-orange-200 px-3 py-1.5 rounded-xl min-h-[44px]">查看 →</button>
                        </div>
                    )}
                    {todoRisk.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-amber-700"><Icon name="warning" className="w-4 h-4"/>流失风险 · {todoRisk.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoRisk)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('tag-risk');setTab('students');}}
                                className="flex-shrink-0 text-xs text-amber-600 font-bold bg-amber-50 active:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-xl min-h-[44px]">查看 →</button>
                        </div>
                    )}
                    {todoBdayWeek.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-pink-600"><Icon name="cake" className="w-4 h-4"/>本周生日 · {todoBdayWeek.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayWeek.map(s=>birthdayWish(s.name)).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-600 font-bold bg-pink-50 active:bg-pink-100 border border-pink-200 px-3 py-1.5 rounded-xl min-h-[44px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayWeek.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent(birthdayWish(s.name))}`} aria-label="发送祝福短信" className="text-pink-400 ml-0.5 active:text-pink-600 inline-flex"><Icon name="chat" className="w-3.5 h-3.5"/></a>}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    {todoBdayMonth.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-pink-400"><Icon name="cake" className="w-4 h-4"/>本月生日 · {todoBdayMonth.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayMonth.map(s=>birthdayWish(s.name)).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-400 font-bold bg-pink-50 active:bg-pink-100 border border-pink-100 px-3 py-1.5 rounded-xl min-h-[44px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayMonth.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent(birthdayWish(s.name))}`} aria-label="发送祝福短信" className="text-pink-400 ml-0.5 active:text-pink-600 inline-flex"><Icon name="chat" className="w-3.5 h-3.5"/></a>}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    })()}

    {/* 需要注意 — 这四条曾经是四个独立区块，被别的内容隔开：待审核 72px、
       长期未到访 210px（手机 698px，学员胶囊换行）、应收 78px、课时预警 106px，
       桌面合计 466px、手机 986px。它们是 v5.3 到 v10.7 逐版本累加的，每一条
       单看都合理，摞在一起就成了一条提醒的走廊，而工作台是落地页。

       它们说的其实是同一件事——「有 N 个东西需要你看一眼」——所以合成一个区、
       每类一行，名单默认折叠。合并的是块，不是信息：每一行仍然带着自己的
       数据源、权限判定和去处，四行跳向四个不同的页面。

       「长期未到访」没有跳转按钮，因为学员列表里没有与之对应的筛选值
       （合法值见 students.jsx:65，最接近的 tag-risk 是另一套口径）。
       对这一行，展开名单本身就是操作。 */}
    {(()=>{
        const rows = [];
        if ((db.pending||[]).length > 0 && allowedTabs.includes('pending')) rows.push({
            key: 'pending', icon: 'clipboard',
            text: `${(db.pending||[]).length} 位学员等待审核`,
            cta: '去审核', go: ()=>setTab('pending'),
        });
        if (analytics.inactive.length > 0) rows.push({
            key: 'inactive', icon: 'calendar',
            text: `${analytics.inactive.length} 名学员有余额但超过 ${inactiveDays} 天未上课`,
            chips: analytics.inactive.slice(0,12).map(s => (
                <button key={s.id} type="button" onClick={()=>{setTab('students');setSrch(s.name);}}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200 active:bg-amber-200 min-h-[44px]">
                    {/* daysSince returns the 9999 sentinel for "no class on
                        record"; printing it raw read as "9999天前". */}
                    {s.name} ({s.balance}课 · {daysSince(s.lastActive)<9999?`${daysSince(s.lastActive)}天前`:'从未上课'})
                </button>
            )),
        });
        if (arSummary && arSummary.unpaidCount > 0) rows.push({
            key: 'ar', icon: 'invoice',
            text: `未付清 ${arSummary.unpaidCount} 张${arSummary.overdueCount > 0 ? `，其中逾期 ${arSummary.overdueCount} 张` : ''} · 应收 ${`$${(arSummary.unpaidCents/100).toFixed(2)}`}`,
            cta: '进账单中心', go: ()=>setTab('billing'),
        });
        if (analytics.lowBalance.length > 0) rows.push({
            key: 'low', icon: 'bolt',
            text: `${analytics.lowBalance.length} 名学员余额 ≤ 2 课时`,
            cta: '看名单', go: ()=>{setSortBy('bal-asc');setFilterBy('low');setTab('students');},
            chips: analytics.lowBalance.map(s => (
                <span key={s.id} className="inline-flex items-stretch">
                <button type="button" onClick={()=>{setTab('students');setSrch(s.name);}}
                    className={`px-3 py-1.5 rounded-l-lg text-xs font-bold border min-h-[44px] ${parseInt(s.balance,10)===0?'bg-red-100 text-red-700 border-red-200':'bg-amber-100 text-amber-800 border-amber-200'}`}>
                    {s.name} ({s.balance})
                </button>
                {/* E4: renewal is the point of this row — one tap lands on the
                    top-up form with this student preselected. */}
                {canWriteCredits && <button type="button" onClick={()=>{setTuStu(s.id);setTab('topup');}}
                    title="去充值" aria-label={`为 ${s.name} 充值`}
                    className="px-2.5 rounded-r-lg text-xs font-bold border border-l-0 min-h-[44px] bg-emerald-50 text-emerald-700 border-emerald-200 active:bg-emerald-100">
                    <Icon name="money" className="w-4 h-4"/>
                </button>}
                </span>
            )),
        });
        if (!rows.length) return null;
        const goButton = (row) => row.go ? (
            <button type="button" onClick={e=>{e.preventDefault();e.stopPropagation();row.go();}}
                className="shrink-0 px-2 min-h-[44px] text-xs font-bold text-indigo-600 active:text-indigo-800 whitespace-nowrap">
                {row.cta} →
            </button>
        ) : null;
        return <section className="bg-white rounded-2xl shadow-sm border border-amber-200 overflow-hidden" aria-labelledby="needs-attention-title">
            <div className="flex items-center gap-2 bg-amber-50 border-b border-amber-200 px-4 py-3">
                <Icon name="warning" className="w-4 h-4 text-amber-700"/>
                <h3 id="needs-attention-title" className="text-sm font-bold text-amber-900">需要注意</h3>
                <span className="ml-auto rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800 tabular-nums">{rows.length}</span>
            </div>
            <div className="divide-y divide-gray-100">
                {rows.map(row => row.chips ? (
                    <details key={row.key} className="group">
                        <summary className="flex cursor-pointer select-none items-center gap-3 px-4 py-2 min-h-[44px] active:bg-amber-50">
                            <Icon name={row.icon} className="w-4 h-4 shrink-0 text-amber-600"/>
                            <span className="flex-1 text-sm text-gray-700">{row.text}</span>
                            {goButton(row)}
                            <span className="shrink-0 text-indigo-600 group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
                        </summary>
                        <div className="flex flex-wrap gap-2 px-4 pb-3">{row.chips}</div>
                    </details>
                ) : (
                    <button key={row.key} type="button" onClick={row.go}
                        className="flex w-full items-center gap-3 px-4 py-2 min-h-[44px] text-left active:bg-amber-50">
                        <Icon name={row.icon} className="w-4 h-4 shrink-0 text-amber-600"/>
                        <span className="flex-1 text-sm text-gray-700">{row.text}</span>
                        <span className="shrink-0 px-2 text-xs font-bold text-indigo-600 whitespace-nowrap">{row.cta} →</span>
                    </button>
                ))}
            </div>
        </section>;
    })()}

    {/* A3: 经营真账（估算）— 现金 vs 已赚 vs 预收负债（v5.3） */}
    {TENANT_SLUG && bizStats && (
        <details className="bg-white rounded-2xl shadow-sm border border-emerald-100">
            {/* D: roles without analytics:read only receive attended_total/attended_month —
               the financial fields are absent, so render those cards only when present. */}
            <summary className="inline-flex items-center gap-1.5 cursor-pointer px-4 py-3 font-bold text-sm text-gray-800 select-none"><Icon name="trend" className="w-4 h-4"/>{canViewFinancialAnalytics ? '经营真账（估算）' : '教学出勤'} <span className="text-xs font-normal text-gray-400">已上课 {bizStats.attended_total} 人次{bizStats.avg_price !== undefined ? ` · 加权均价 $${bizStats.avg_price}/课时` : ''}</span></summary>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-4 pb-4">
                {[
                    ['已上课人次', `${bizStats.attended_total} 次`, `本月 ${bizStats.attended_month} 次`, 'text-gray-800'],
                    ...(bizStats.earned_revenue !== undefined ? [['已赚收入(估)', `$${bizStats.earned_revenue}`, '人次 × 加权均价', 'text-emerald-600']] : []),
                    ...(bizStats.prepaid_liability !== undefined ? [['预收未耗(负债)', `$${bizStats.prepaid_liability}`, '剩余课时 × 均价', 'text-amber-600']] : []),
                    ...(bizStats.cash_net !== undefined ? [['净现金收入', `$${bizStats.cash_net}`, '充值 − 退款', 'text-indigo-600']] : []),
                ].map(([l,v,sub,c]) => (
                    <div key={l} className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                        <p className="text-[11px] text-gray-400">{l}</p>
                        <p className={`text-xl font-bold ${c}`}>{v}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>
                    </div>
                ))}
            </div>
        </details>
    )}

    {/* v9.1: readiness is operational only when every number opens the exact
        students that need work. The same filter values are available in the
        student list, so this is not a decorative dashboard dead-end. */}
    {TENANT_SLUG && (()=>{
        const students = db.students.filter(student=>!student.archived);
        const metrics = [
            ['专区已就绪', students.filter(s=>s.mobile&&s.hasAccessCode).length, 'portal-ready', 'lock'],
            ['缺少手机号', students.filter(s=>!s.mobile).length, 'portal-missing-mobile', 'phone'],
            ['专区未启用', students.filter(s=>s.mobile&&!s.hasAccessCode).length, 'portal-disabled', 'warning'],
            ['私人内容受阻', students.filter(s=>(s.portfolio||[]).length>0&&(!s.mobile||!s.hasAccessCode)).length, 'portal-content-blocked', 'image'],
            ['作品已公开', students.filter(s=>(s.portfolio||[]).some(item=>item.public||item.visibility==='shared')).length, 'publication-live', 'image'],
            ['公开授权有效', students.filter(s=>s.publicationConsent?.status==='confirmed').length, 'publication-ready', 'shield'],
            ['有作品但缺授权', students.filter(s=>(s.portfolio||[]).length>0&&s.publicationConsent?.status!=='confirmed').length, 'publication-missing-consent', 'warning'],
        ];
        return <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-start justify-between gap-3 mb-3">
                <div><p className="font-bold text-sm text-gray-800">学员专区与作品发布</p><p className="text-xs text-gray-400 mt-0.5">点击数字直接处理对应学员</p></div>
                <Icon name="shield" className="w-5 h-5 text-indigo-500"/>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
                {metrics.map(([label,value,filter,icon])=><button key={filter} type="button" onClick={()=>{setFilterBy(filter);setTab('students');}}
                    className="min-h-[68px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left active:border-indigo-300 active:bg-indigo-50">
                    <span className="flex items-center gap-1.5 text-xs text-gray-500"><Icon name={icon} className="w-3.5 h-3.5"/>{label}</span>
                    <span className="mt-1 block text-xl font-bold text-gray-900 tabular-nums">{value}</span>
                </button>)}
            </div>
        </div>;
    })()}

    {/* 「最近操作」在工作台上曾经是 722px —— 落地页最高的单块，位置在
       桌面 y=1413 / 手机 y=2630，没有人会滚到那里去读它。而「操作日志」
       本来就是独立导航项（实测 29 行、桌面 3098px），干的是同一件事。
       落地页只留一个入口，完整流水在它自己的页面里看。 */}
    {allowedTabs.includes('logs') && (
        <button type="button" onClick={()=>setTab('logs')}
            className="flex w-full items-center gap-3 rounded-2xl border border-gray-100 bg-white px-4 py-3 min-h-[44px] text-left shadow-sm active:bg-gray-50">
            <Icon name="scroll" className="w-4 h-4 shrink-0 text-gray-400"/>
            <span className="flex-1 text-sm text-gray-700">最近操作</span>
            <span className="shrink-0 text-xs font-bold text-indigo-600">全部 →</span>
        </button>
    )}
</div>
    );
}
