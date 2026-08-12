/* The pricing calculator.
 *
 * It answers one question — "which plan is mine and what does the first year
 * cost" — from the plan rows the server already rendered into the page. There
 * is no fetch and no second copy of the numbers: `data-plans` is written from
 * `public_plan_rows()`, the same call that renders the cards below it, so the
 * figure the slider produces cannot disagree with the figure in the card.
 *
 * Everything degrades: with no script the sliders are still inputs and the
 * cards below still carry every number. Nothing here is required to read the
 * page.
 */
(function () {
  'use strict';

  const root = document.getElementById('calc');
  if (!root) return;

  let plans = [];
  try {
    plans = JSON.parse(root.dataset.plans || '[]');
  } catch (error) {
    return; // The cards below are the fallback, and they are already correct.
  }
  if (!plans.length) return;

  const zh = String(document.documentElement.lang || '').toLowerCase().startsWith('zh');
  const T = (en, cn) => (zh ? cn : en);

  const students = document.getElementById('calcStudents');
  const team = document.getElementById('calcTeam');
  const studentsOut = document.getElementById('calcStudentsOut');
  const teamOut = document.getElementById('calcTeamOut');
  const planOut = document.getElementById('calcPlan');
  const monthlyOut = document.getElementById('calcMonthly');
  const yearOut = document.getElementById('calcYear');
  const noteOut = document.getElementById('calcNote');

  const money = (value) => `AUD ${Number(value).toLocaleString('en-AU')}`;
  const bySize = plans.slice().sort((a, b) => a.monthly_price_aud - b.monthly_price_aud);

  function choose(studentCount, teamCount) {
    // The smallest plan that holds both numbers. Not the cheapest that holds
    // students — a five-person team on a one-login plan is the same "no".
    return bySize.find((plan) => plan.student_limit >= studentCount && plan.user_limit >= teamCount) || null;
  }

  function render() {
    const studentCount = Number(students.value);
    const teamCount = Number(team.value);
    studentsOut.textContent = studentCount;
    teamOut.textContent = teamCount;

    const plan = choose(studentCount, teamCount);
    if (!plan) {
      // Above the largest published plan. Say so plainly rather than showing
      // the biggest one and quietly hoping.
      const largest = bySize[bySize.length - 1];
      planOut.textContent = T('Let us talk', '需要单独谈');
      monthlyOut.textContent = T('Beyond the published plans', '超出已发布的套餐');
      yearOut.textContent = '—';
      noteOut.textContent = T(
        `The largest published plan holds ${largest.student_limit} students and ${largest.user_limit} logins. Above that we quote.`,
        `已发布的最大套餐是 ${largest.student_limit} 名学员、${largest.user_limit} 个登录名额。超过这个规模我们单独报价。`
      );
      return;
    }

    planOut.textContent = plan.name;
    monthlyOut.textContent = `${money(plan.monthly_price_aud)}${T(' / month', ' / 月')}`;
    yearOut.textContent = money(plan.monthly_price_aud * 12);

    // Why this plan and not the one below it — the honest half of a
    // recommendation is the constraint that decided it.
    const smaller = bySize[bySize.indexOf(plan) - 1];
    if (!smaller) {
      const logins = `${plan.user_limit} login${plan.user_limit === 1 ? '' : 's'}`;
      noteOut.textContent = T(
        `Room for ${plan.student_limit} students and ${logins}.`,
        `可容纳 ${plan.student_limit} 名学员、${plan.user_limit} 个登录名额。`
      );
    } else if (smaller.student_limit < studentCount) {
      noteOut.textContent = T(
        `${smaller.name} stops at ${smaller.student_limit} students.`,
        `${smaller.name} 的学员上限是 ${smaller.student_limit} 名。`
      );
    } else {
      noteOut.textContent = T(
        `${smaller.name} allows ${smaller.user_limit} login${smaller.user_limit === 1 ? '' : 's'}.`,
        `${smaller.name} 只有 ${smaller.user_limit} 个登录名额。`
      );
    }
  }

  students.addEventListener('input', render);
  team.addEventListener('input', render);
  render();
})();
