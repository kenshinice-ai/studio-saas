/* 一条筛选栏，六个页面共用。
 *
 * 课酬、发票、学员档案、作品、操作日志、待处理要的是同一组东西：一段时间、
 * 一个名字、一个分类。分六次手写就是六份会各自漂的实现 —— 这个仓库已经在
 * 「侧栏名 vs 页面标题」和「归档清单 vs 导入顺序」上各栽过一次，两次都是
 * 两份写死的清单悄悄分了家。
 *
 * 四种格子都是可选的：课酬不需要分类，学员档案不需要时间。没传的那格不渲染，
 * 而不是渲染一个空壳 —— 一个永远筛不出东西的空控件，比没有这个控件更让人
 * 怀疑功能坏了。
 *
 * 不 import Icon：--bundle 之后主文件的标识符在这里不存在，
 * tests/test_cms_panels.py 会拦这件事。
 */
const { useMemo } = React;

/** 发工资和对账时真正会用到的几段，不是一整套日期算术。 */
export const RANGE_PRESETS = [
    { key: 'this_month', label: '本月' },
    { key: 'last_month', label: '上月' },
    { key: 'last_30', label: '近 30 天' },
];

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** 把快捷档换算成具体的起止日，本地时区。 */
export function presetRange(key, today = new Date()) {
    const y = today.getFullYear(), m = today.getMonth();
    if (key === 'this_month') return { start: iso(new Date(y, m, 1)), end: iso(new Date(y, m + 1, 0)) };
    if (key === 'last_month') return { start: iso(new Date(y, m - 1, 1)), end: iso(new Date(y, m, 0)) };
    if (key === 'last_30') {
        const from = new Date(today); from.setDate(from.getDate() - 29);
        return { start: iso(from), end: iso(today) };
    }
    return { start: '', end: '' };
}

/**
 * @param range     {start,end} 或 null（不显示时间格）
 * @param onRange   (next) => void
 * @param query     字符串或 null（不显示搜索格）
 * @param onQuery   (text) => void
 * @param buckets   [{key,label,count}] 或 null（不显示分类格）
 * @param bucket    当前分类 key
 * @param onBucket  (key) => void
 * @param total     筛选后剩多少条 —— 一直显示，不是只在有筛选时显示
 */
/*
 * `extra` exists because the operations log needs a student picker and an action
 * select, and neither is a date, a search box or a bucket. Without a slot the
 * choice was: rewrite the log's filter as four generic boxes and LOSE the picker,
 * or leave the page out of the shared bar and keep the drift. A slot is the third
 * answer — the page contributes the control only it needs, and still inherits the
 * one thing every page was getting wrong on its own: a visible result count and a
 * clear-filters button that actually clears everything.
 *
 * `extraDirty` / `onClearExtra` let those page-specific controls take part in
 * "清除筛选" instead of quietly surviving it, which would be worse than not
 * sharing at all.
 */
export function FilterBar({
    range, onRange, searchPlaceholder = '搜索…', query, onQuery,
    buckets, bucket, onBucket, total, totalNoun = '条',
    extra = null, extraDirty = false, onClearExtra = null,
}) {
    const dirty = useMemo(() => Boolean(
        (query && query.trim()) ||
        (buckets && bucket && bucket !== buckets[0]?.key) ||
        (range && (range.start || range.end)) ||
        extraDirty
    ), [query, bucket, buckets, range, extraDirty]);

    function clearAll() {
        if (onQuery) onQuery('');
        if (onBucket && buckets?.length) onBucket(buckets[0].key);
        if (onRange) onRange(presetRange('this_month'));
        if (onClearExtra) onClearExtra();
    }

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-3 space-y-2">
            {range && (
                <div className="flex flex-wrap items-end gap-2">
                    <label className="text-[11px] text-gray-500">
                        起
                        <input type="date" value={range.start || ''}
                               onChange={e => onRange({ ...range, start: e.target.value })}
                               className="block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                    <label className="text-[11px] text-gray-500">
                        止
                        <input type="date" value={range.end || ''}
                               onChange={e => onRange({ ...range, end: e.target.value })}
                               className="block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                        {RANGE_PRESETS.map(preset => (
                            <button key={preset.key} type="button"
                                    onClick={() => onRange(presetRange(preset.key))}
                                    className="min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-700">
                                {preset.label}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {extra}

            {query !== null && query !== undefined && (
                <input value={query} onChange={e => onQuery(e.target.value)}
                       placeholder={searchPlaceholder}
                       className="w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
            )}

            {buckets && buckets.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {buckets.map(item => (
                        <button key={item.key} type="button" onClick={() => onBucket(item.key)}
                                className={`min-h-[44px] px-3 rounded-xl text-xs font-bold border ${
                                    bucket === item.key
                                        ? 'bg-indigo-600 text-white border-indigo-600'
                                        : 'bg-white text-gray-700 border-gray-200'}`}>
                            {/* 计数跟着标签走：「逾期 2」不点开就知道要不要点，
                                「逾期」得点一下才知道是不是空的。 */}
                            {item.label}{typeof item.count === 'number' ? ` ${item.count}` : ''}
                        </button>
                    ))}
                </div>
            )}

            {/* 结果计数常驻。一个看不见的筛选条件，就是那通「为什么只剩三条」的
                电话 —— v10.1.0 给账户深链加过一条横幅，同一个道理。 */}
            <div className="flex items-center gap-2 text-[11px] text-gray-500">
                {/* One node, not three: the count sits between two Chinese
                    fragments, and a measure word translated on its own cannot
                    tell 张-invoices from 张-works. cms-i18n.js matches the
                    whole phrase per noun instead. */}
                <span>{`共 ${total} ${totalNoun}`}</span>
                {dirty && (
                    <button type="button" onClick={clearAll}
                            className="min-h-[44px] px-2 font-bold text-indigo-600">
                        清除筛选
                    </button>
                )}
            </div>
        </div>
    );
}
