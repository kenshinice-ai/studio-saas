-- v10.3.0 — 租户隔离从「靠纪律」变成「靠构造」。
--
-- 在此之前隔离完全由「每条查询都记得写 WHERE tenant_id」保证。核查过：213 段
-- SQL 里 180 段写了，剩下 33 段查的是 users / tenants / plans 这类本来就不是
-- 租户级的表。纪律守住了，今天没有已知泄漏 —— 这条迁移不是在补漏，是在把
-- 「不能忘」从约定变成事实。
--
-- 为什么是现在：生产此刻 6 个内测租户、57 名学员、17 MB，多半还是演示数据。
-- 这是这套系统一生中做这件事最便宜的时刻。每多一个真实工作室都会更贵。
--
-- 为什么是 73 张而不是只给钱那几张：RLS 的成本不在策略条数（这些是生成的），
-- 在四件固定开销 —— 请求路径的会话变量、角色切换、登录特例、平台控制台。
-- 这四项无论 9 张表还是 73 张表都一样要付。只保护一部分表，等于付全部成本
-- 拿部分覆盖。
--
-- ── 三件必须同时成立的事 ───────────────────────────────────────────
--
-- 1. 应用不能以超级用户连库。超级用户**无条件绕过 RLS**。本地实测过：以超级
--    用户身份开了 RLS 并加了 FORCE，两个租户的数据照样全能读到 —— 策略在库里、
--    隔离为零。只加策略不换角色，等于什么都没做。
-- 2. FORCE ROW LEVEL SECURITY。默认表属主不受自己表上的策略约束。
-- 3. current_setting(..., true) 的第二个参数：变量没设时返回 NULL 而不是报错，
--    策略变成 tenant_id = NULL → 假 → 一行都读不到。
--    **忘记设租户的后果是什么都看不见，不是什么都看得见。**

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'studiosaas_app') THEN
        -- NOLOGIN：角色建出来但连不上，直到运维显式设一次密码。密码不进 git。
        CREATE ROLE studiosaas_app NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO studiosaas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO studiosaas_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO studiosaas_app;
-- 明确不给 CREATE / DROP / TRUNCATE / ALTER。TRUNCATE 尤其要紧：它绕过 RLS，
-- 而租户彻底删除走的是 DELETE FROM tenants 级联，不受影响。
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO studiosaas_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO studiosaas_app;

ALTER TABLE attendance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_sessions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON attendance_sessions;
CREATE POLICY tenant_isolation ON attendance_sessions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON audit_logs;
CREATE POLICY tenant_isolation ON audit_logs
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE bank_statement_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_statement_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON bank_statement_lines;
CREATE POLICY tenant_isolation ON bank_statement_lines
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE billing_account_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_account_members FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing_account_members;
CREATE POLICY tenant_isolation ON billing_account_members
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE billing_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing_accounts;
CREATE POLICY tenant_isolation ON billing_accounts
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE billing_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing_schedules;
CREATE POLICY tenant_isolation ON billing_schedules
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE calendar_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_subscriptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON calendar_subscriptions;
CREATE POLICY tenant_isolation ON calendar_subscriptions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE class_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_bookings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON class_bookings;
CREATE POLICY tenant_isolation ON class_bookings
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE class_schedule_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_schedule_exceptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON class_schedule_exceptions;
CREATE POLICY tenant_isolation ON class_schedule_exceptions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE class_schedule_students ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_schedule_students FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON class_schedule_students;
CREATE POLICY tenant_isolation ON class_schedule_students
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE class_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON class_schedules;
CREATE POLICY tenant_isolation ON class_schedules
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE cms_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE cms_notifications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON cms_notifications;
CREATE POLICY tenant_isolation ON cms_notifications
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON courses;
CREATE POLICY tenant_isolation ON courses
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE credit_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credit_accounts;
CREATE POLICY tenant_isolation ON credit_accounts
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE credit_note_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_note_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credit_note_lines;
CREATE POLICY tenant_isolation ON credit_note_lines
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE credit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credit_notes;
CREATE POLICY tenant_isolation ON credit_notes
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON credit_transactions;
CREATE POLICY tenant_isolation ON credit_transactions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE daily_roster_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_roster_entries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON daily_roster_entries;
CREATE POLICY tenant_isolation ON daily_roster_entries
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE document_number_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_number_sequences FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON document_number_sequences;
CREATE POLICY tenant_isolation ON document_number_sequences
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE email_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_templates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON email_templates;
CREATE POLICY tenant_isolation ON email_templates
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE integration_sync_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_sync_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON integration_sync_jobs;
CREATE POLICY tenant_isolation ON integration_sync_jobs
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE invoice_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON invoice_events;
CREATE POLICY tenant_isolation ON invoice_events
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE invoice_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON invoice_lines;
CREATE POLICY tenant_isolation ON invoice_lines
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON invoices;
CREATE POLICY tenant_isolation ON invoices
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE lesson_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_exceptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON lesson_exceptions;
CREATE POLICY tenant_isolation ON lesson_exceptions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE lesson_series ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_series FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON lesson_series;
CREATE POLICY tenant_isolation ON lesson_series
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE makeup_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE makeup_credits FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON makeup_credits;
CREATE POLICY tenant_isolation ON makeup_credits
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON media_assets;
CREATE POLICY tenant_isolation ON media_assets
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE media_variants ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_variants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON media_variants;
CREATE POLICY tenant_isolation ON media_variants
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE notification_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_channels FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON notification_channels;
CREATE POLICY tenant_isolation ON notification_channels
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE notification_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON notification_logs;
CREATE POLICY tenant_isolation ON notification_logs
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE notification_optouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_optouts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON notification_optouts;
CREATE POLICY tenant_isolation ON notification_optouts
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE notification_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_routes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON notification_routes;
CREATE POLICY tenant_isolation ON notification_routes
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE packages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON packages;
CREATE POLICY tenant_isolation ON packages
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE payment_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_allocations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON payment_allocations;
CREATE POLICY tenant_isolation ON payment_allocations
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE payment_provider_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_provider_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON payment_provider_events;
CREATE POLICY tenant_isolation ON payment_provider_events
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE payment_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_providers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON payment_providers;
CREATE POLICY tenant_isolation ON payment_providers
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON payments;
CREATE POLICY tenant_isolation ON payments
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE portfolio_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON portfolio_items;
CREATE POLICY tenant_isolation ON portfolio_items
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE progress_report_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE progress_report_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON progress_report_settings;
CREATE POLICY tenant_isolation ON progress_report_settings
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE progress_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE progress_reports FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON progress_reports;
CREATE POLICY tenant_isolation ON progress_reports
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE public_analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_analytics_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public_analytics_events;
CREATE POLICY tenant_isolation ON public_analytics_events
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON refunds;
CREATE POLICY tenant_isolation ON refunds
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE registrations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON registrations;
CREATE POLICY tenant_isolation ON registrations
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE scheduling_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduling_policies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON scheduling_policies;
CREATE POLICY tenant_isolation ON scheduling_policies
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE student_access_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_access_attempts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON student_access_attempts;
CREATE POLICY tenant_isolation ON student_access_attempts
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE student_access_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_access_sessions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON student_access_sessions;
CREATE POLICY tenant_isolation ON student_access_sessions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE student_publication_consent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_publication_consent_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON student_publication_consent_events;
CREATE POLICY tenant_isolation ON student_publication_consent_events
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE students FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON students;
CREATE POLICY tenant_isolation ON students
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON subscriptions;
CREATE POLICY tenant_isolation ON subscriptions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tax_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_codes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tax_codes;
CREATE POLICY tenant_isolation ON tax_codes
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teacher_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_availability FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teacher_availability;
CREATE POLICY tenant_isolation ON teacher_availability
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teacher_engagements ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_engagements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teacher_engagements;
CREATE POLICY tenant_isolation ON teacher_engagements
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teacher_pay_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_pay_adjustments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teacher_pay_adjustments;
CREATE POLICY tenant_isolation ON teacher_pay_adjustments
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teacher_pay_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_pay_periods FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teacher_pay_periods;
CREATE POLICY tenant_isolation ON teacher_pay_periods
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teacher_pay_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_pay_rates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teacher_pay_rates;
CREATE POLICY tenant_isolation ON teacher_pay_rates
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE teaching_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE teaching_sessions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON teaching_sessions;
CREATE POLICY tenant_isolation ON teaching_sessions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_addons ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_addons FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_addons;
CREATE POLICY tenant_isolation ON tenant_addons
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_archives ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_archives FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_archives;
CREATE POLICY tenant_isolation ON tenant_archives
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_billing_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_billing_identity FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_billing_identity;
CREATE POLICY tenant_isolation ON tenant_billing_identity
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_brand_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_brand_drafts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_brand_drafts;
CREATE POLICY tenant_isolation ON tenant_brand_drafts
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_brand_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_brand_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_brand_versions;
CREATE POLICY tenant_isolation ON tenant_brand_versions
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_slug_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_slug_aliases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_slug_aliases;
CREATE POLICY tenant_isolation ON tenant_slug_aliases
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE tenant_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_usage FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_usage;
CREATE POLICY tenant_isolation ON tenant_usage
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE term_closures ENABLE ROW LEVEL SECURITY;
ALTER TABLE term_closures FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON term_closures;
CREATE POLICY tenant_isolation ON term_closures
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE terms FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON terms;
CREATE POLICY tenant_isolation ON terms
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE xero_account_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_account_mappings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON xero_account_mappings;
CREATE POLICY tenant_isolation ON xero_account_mappings
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE xero_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_connections FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON xero_connections;
CREATE POLICY tenant_isolation ON xero_connections
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE xero_object_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_object_links FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON xero_object_links;
CREATE POLICY tenant_isolation ON xero_object_links
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');
ALTER TABLE xero_sync_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_sync_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON xero_sync_settings;
CREATE POLICY tenant_isolation ON xero_sync_settings
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');

-- ── memberships：唯一的例外，而且非要不可 ──────────────────────────
--
-- 登录时还不知道租户 —— auth_login 读 memberships 正是为了查出这个用户属于
-- 哪些租户。套用上面那条策略，登录返回零行，谁也进不来。
--
-- 多一条自查子句解决：你永远看得见自己的 membership。这在语义上是准确的 ——
-- 「我属于哪些工作室」是自查，不是跨租户查询。别人的 membership 仍然只在
-- 当前租户上下文里可见。WITH CHECK 不放宽：能看见不等于能写。

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON memberships;
CREATE POLICY tenant_isolation ON memberships
    USING (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR user_id = current_setting('studiosaas.user_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on')
    WITH CHECK (tenant_id = current_setting('studiosaas.tenant_id', true)::uuid
           OR current_setting('studiosaas.platform', true) = 'on');

-- ── 不加 RLS 的 5 张表 ─────────────────────────────────────────────
--
--   plans / schema_migrations  平台级，本来就该共享
--   tenants                    租户注册表本身，给它加租户策略是循环定义
--   users                      刻意全局：一个老师在两家工作室教课是同一个人、
--                              同一个密码。租户归属在 memberships 里，那张受控
--   cms_notification_reads     (notification_id, user_id)，租户范围由通知本身
--                              决定；读它必须先读到通知，那一步已经受控
--   password_setup_tokens      按不可猜的令牌查，**查到之前不可能知道租户**。
--   share_tokens               令牌本身就是授权（这是它们的安全模型）。把它们
--                              放进隔离集，等于把唯一的读法堵死。
--
-- ── 平台标记 ──────────────────────────────────────────────────────
--
-- 超管控制台本来就跨租户（列全部租户的订阅、聚合用量、读全量审计）。
-- @super_admin_required 里设 studiosaas.platform = 'on'，随连接销毁。
-- 它不是「绕过」而是「把已有的权限说出来」—— 超管本来就看得见这些。
-- support mode 不需要这个：它限定单租户，正好落在主策略里。
--
-- ── 超管不需要旁路 ────────────────────────────────────────────────
--
-- support mode 已经把超管限定在**一个**租户（原因必填、写审计），那正好就是
-- 策略要求的范围。真正跨租户的只有平台看板，它继续用属主连接串。
