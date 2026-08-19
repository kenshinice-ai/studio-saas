/* 作品集 — 全馆作品流。
 *
 * v10.11.0 从 cms-app.jsx 的 App() 机械抽出：JSX 原文未动，App 状态与
 * 处理函数经 props 显式传入（与 billing.jsx 同一约定，避免循环依赖）。
 */

import { EmptyState, Icon, fmtDate, portfolioThumbSrc } from "../components.jsx";
import { FilterBar } from "./filter_bar.jsx";

export function WorksSection(props) {
    const {
        canWritePortfolio, portfolioEntries, setEditP, setPortUpload, setSelS, setStudentProfileTab,
        setTab, setWorksBucket, setWorksQuery, worksBucket, worksBuckets, worksQuery,
        worksVisible,
    } = props;
    return (
<div className="anim space-y-5 max-w-6xl mx-auto">
    <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800"><Icon name="image" className="w-5 h-5"/>作品管理</h2><p className="text-sm text-gray-500 mt-1">从这里按学员浏览作品；具体上传、编辑和公开授权仍在学员档案中完成。</p></div>
        <button type="button" onClick={()=>setTab('students')} className="min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold">进入学员档案 →</button>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[['作品总数',portfolioEntries.length,'text-gray-900'],['已公开',portfolioEntries.filter(({item})=>item.public||item.visibility==='shared').length,'text-emerald-700'],['待授权',portfolioEntries.filter(({student})=>student.publicationConsent?.status!=='confirmed').length,'text-amber-700'],['有作品学员',new Set(portfolioEntries.map(({student})=>student.id)).size,'text-indigo-700']].map(([label,value,color])=><div key={label} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4"><p className="text-xs text-gray-400">{label}</p><p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p></div>)}
    </div>
    <FilterBar
        query={worksQuery} onQuery={setWorksQuery}
        searchPlaceholder="搜学员姓名或作品说明"
        buckets={worksBuckets} bucket={worksBucket} onBucket={setWorksBucket}
        total={worksVisible.length} totalNoun="件" />
    <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5" aria-labelledby="works-list-title">
        <div className="flex items-center justify-between gap-3 mb-3"><div><h3 id="works-list-title" className="font-bold text-gray-900">最近作品</h3><p className="text-xs text-gray-400 mt-0.5">按作品日期倒序 · 最多显示最近 50 件</p></div><span className="text-xs font-bold text-gray-500">{worksVisible.length} 件</span></div>
        {!portfolioEntries.length ? <EmptyState icon={<Icon name="image" className="w-8 h-8"/>} main="还没有作品" sub="打开学员档案后，在作品区上传第一件作品。" action="查看学员" onAction={()=>setTab('students')}/>
         : !worksVisible.length ? <EmptyState icon={<Icon name="image" className="w-8 h-8"/>} main="没有符合筛选的作品" sub="换一个分类，或清空搜索词。"/>
         : <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{worksVisible.slice(0,50).map(({student,item})=>{
            const shared = item.public || item.visibility === 'shared';
            return <article key={`${student.id}-${item.id||item.filename||item.date}`} className="overflow-hidden rounded-2xl border border-gray-200 bg-gray-50">
                <button type="button" onClick={()=>{setTab('students',{recordId:student.id});setSelS(student);setEditP(false);setTimeout(()=>setStudentProfileTab('portfolio'),0);}} className="block w-full text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500">
                    <div className="aspect-[4/3] bg-gray-100 overflow-hidden">{item.filename ? <img src={portfolioThumbSrc(student.id,item)} loading="lazy" alt={`${student.name} 的作品`} className="w-full h-full object-cover"/> : <div className="w-full h-full inline-flex items-center justify-center text-gray-300"><Icon name="image" className="w-10 h-10"/></div>}</div>
                    <div className="p-3"><div className="flex items-center justify-between gap-2"><p className="font-bold text-gray-900 truncate">{item.title||item.note||'未命名作品'}</p><span className={`flex-shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-full border ${shared?'bg-emerald-50 border-emerald-200 text-emerald-700':'bg-gray-100 border-gray-200 text-gray-500'}`}>{shared?'已公开':'未公开'}</span></div><p className="text-xs text-gray-500 mt-1 truncate">{student.name} · {fmtDate(item.date)}</p>{item.note && item.title && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{item.note}</p>}</div>
                </button>
                {canWritePortfolio && <div className="px-3 pb-3"><button type="button" onClick={()=>{setTab('students',{recordId:student.id});setSelS(student);setEditP(false);setTimeout(()=>{setStudentProfileTab('portfolio');setPortUpload(true);},0);}} className="w-full min-h-[44px] rounded-xl border border-indigo-200 bg-white text-xs font-bold text-indigo-700 hover:bg-indigo-50">在该学员下继续上传</button></div>}
            </article>;
        })}</div>}
    </section>
</div>
    );
}
