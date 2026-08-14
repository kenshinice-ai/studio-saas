/* 待写的成长报告 —— 收件箱里的第三种事。
 *
 * 「写一份报告」和「知道有哪些该写」是两个问题，学员详情只能回答前者：
 * 要在两百个学员里找出逾期未写的七份，那个页面无能为力。
 *
 * 产品里已经有这个模式 —— 学员是档案，待处理是工作清单，报名和约课
 * 就是这么分的。所以报告不开独立入口，写在学员详情，找在这里。
 */

import { fmtApiDate } from "./_shared.jsx";

const { useState, useEffect, useCallback } = React;

export function OverdueReports({ api, showToast, onOpenStudent }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api('/progress-reports/overdue');
      setRows(d.overdue || []);
      setError('');
    } catch (e) {
      setError(e.status === 403 ? '这个套餐未包含成长报告。' : `加载失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-gray-500 p-4">正在加载…</p>;
  if (error) return <p className="text-sm text-red-600 p-4">{error}</p>;

  if (!rows.length) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
        <p className="font-bold text-gray-600">没有逾期未写的报告</p>
        <p className="text-xs text-gray-500 mt-1">
          到期的草稿会自动出现在这里，并提醒对应的老师 —— 官网上那句「每 4–8 节课一份进度报告」由系统兜底。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map(r => {
        const days = Number(r.days_overdue || 0);
        return (
          <div key={r.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-3 flex items-center gap-3">
            <div className="min-w-0">
              <p className="font-bold text-sm truncate">{r.display_name}</p>
              <p className="text-xs text-gray-500">
                周期至 {fmtApiDate(r.period_end)} · 由 {r.teacher_name || '未指派老师'} 撰写
              </p>
            </div>
            <span className={`ml-auto text-xs font-bold px-2 py-1 rounded whitespace-nowrap border
              ${days > 14 ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
              逾期 {days} 天
            </span>
            <button type="button" onClick={() => onOpenStudent && onOpenStudent(r.student_id)}
                    className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold whitespace-nowrap">
              去写
            </button>
          </div>
        );
      })}
    </div>
  );
}
