# Welcome pack — the handover email

The message a new studio gets when their tenant is created. Copy the block for
their language, replace every `{{PLACEHOLDER}}`, send.

**It is deliberately two messages.** The welcome email carries links and
instructions and no secrets; the temporary password goes separately, by a
channel the studio already trusts. That is not ceremony — an email thread gets
forwarded, quoted and left in a mailbox for years, and a password in it
outlives every reason it existed.

Checklist step: `Onboarding_Checklist.md` Phase 2.

---

## Before you send

- [ ] Tenant created, owner account added, plan assigned.
- [ ] Website published at least once — an unpublished portal shows an empty
      shell, and a first link that looks broken is expensive to undo.
- [ ] Every `{{PLACEHOLDER}}` below replaced. Search the draft for `{{` before
      sending.
- [ ] Temporary password ready to send **separately**.

---

## English

> **Subject:** Your PWE Studio account is ready — {{STUDIO_NAME}}

Hi {{OWNER_NAME}},

{{STUDIO_NAME}} is set up and ready for you. Here is everything in one place.

**Your four addresses**

| | |
|---|---|
| Your public website | https://pwestudio.online/{{SLUG}} |
| Quick registration page | https://pwestudio.online/{{SLUG}}/register |
| Daily operations (CMS) | https://pwestudio.online/{{SLUG}}/cms |
| Brand & website settings | https://pwestudio.online/{{SLUG}}/studio-admin |

The last two are for your team. The first two are for families — the
registration page is the one to put behind a QR code.

**First, change your password**

Sign in at https://pwestudio.online/{{SLUG}}/studio-admin with
`{{OWNER_EMAIL}}` and the temporary password I am sending you separately. Then
change it straight away: **Change Password** in the top bar, minimum eight
characters. Do the same in the CMS for any account you create for your team —
each person gets their own; nobody shares one.

**The manual**

https://pwestudio.online/manual/

Worth reading first, in this order:

- What credits are and why families see a credit balance, not a class count —
  https://pwestudio.online/manual/#start
- Getting your website live — https://pwestudio.online/manual/#launch
- Who on your team can do what, and what the system will refuse them —
  https://pwestudio.online/manual/#team
- How families check their own records — https://pwestudio.online/manual/#families

**Bringing your existing students across**

Start from the import template — [CSV](https://pwestudio.online/customer-resources/PWE_Studio_Data_Import_Template.csv)
or [Excel](https://pwestudio.online/customer-resources/PWE_Studio_Data_Import_Template.xlsx).
Send it back and we will review it with you before anything is loaded.

**What we do and do not do**

We run the platform. We cannot open your CMS without starting a logged support
session with a written reason, and you can see every one of those yourself
under Studio Admin → Analytics → Audit Trail. The details are in
https://pwestudio.online/manual/#platform

Our commitments and their limits are written down rather than implied:
[support policy](https://pwestudio.online/customer-resources/Support_Policy.html) ·
[privacy policy](https://pwestudio.online/customer-resources/Privacy_Policy.html) ·
[terms of service](https://pwestudio.online/customer-resources/Terms_of_Service.html) ·
[service FAQ](https://pwestudio.online/customer-resources/FAQ.html)

Reply to this email with anything at all.

{{SENDER_NAME}}
PWE Studio

---

## 中文

> **主题：**{{STUDIO_NAME}} 的 PWE Studio 已经开通

{{OWNER_NAME}} 你好，

{{STUDIO_NAME}} 已经开通，需要的东西都在这封信里。

**四个地址**

| | |
|---|---|
| 你的公开官网 | https://pwestudio.online/{{SLUG}} |
| 快速报名页 | https://pwestudio.online/{{SLUG}}/register |
| 日常运营（CMS） | https://pwestudio.online/{{SLUG}}/cms |
| 品牌与官网设置 | https://pwestudio.online/{{SLUG}}/studio-admin |

后两个给你的团队用，前两个给家长用——报名页就是放在二维码后面的那一个。

**第一件事：改密码**

用 `{{OWNER_EMAIL}}` 和我另外发给你的临时密码登录
https://pwestudio.online/{{SLUG}}/studio-admin ，然后**立刻改掉**：顶部
「修改密码」，至少 8 位。之后你在 CMS 里给团队开的每个账号也一样——**一人
一号，不要共用**。

**用户手册**

https://pwestudio.online/zh/manual/

建议按这个顺序先看四段：

- 课时是什么、为什么给家长显示的是「剩余课时」而不是「还能上几节课」——
  https://pwestudio.online/zh/manual/#start
- 让官网上线 —— https://pwestudio.online/zh/manual/#launch
- 团队里谁能做什么、系统会拒绝谁 —— https://pwestudio.online/zh/manual/#team
- 家长怎么自助查询 —— https://pwestudio.online/zh/manual/#families

**把现有学员迁进来**

从导入模版开始——[CSV](https://pwestudio.online/customer-resources/PWE_Studio_Data_Import_Template.csv)
或 [Excel](https://pwestudio.online/customer-resources/PWE_Studio_Data_Import_Template.xlsx)。
填好发回来，我们会先和你一起核对，再导入任何数据。

**我们做什么、不做什么**

我们负责平台。在没有开启一次留痕的支持会话（并写明原因）之前，我们**打不开
你的 CMS**；每一次这样的进入你都能自己在「品牌工作台 → 数据分析 → 操作审计」
里看到。说明见 https://pwestudio.online/zh/manual/#platform

我们的承诺和它的边界都是写下来的，不靠默契：
[支持政策](https://pwestudio.online/customer-resources/Support_Policy.html) ·
[隐私政策](https://pwestudio.online/customer-resources/Privacy_Policy.html) ·
[服务条款](https://pwestudio.online/customer-resources/Terms_of_Service.html) ·
[服务 FAQ](https://pwestudio.online/customer-resources/FAQ.html)

有任何问题直接回这封邮件。

{{SENDER_NAME}}
PWE Studio

---

## The separate message

Send by SMS, WeChat, or whatever channel the studio already uses with you —
not as a reply on the email thread above.

> {{STUDIO_NAME}} 的临时密码：`{{TEMPORARY_PASSWORD}}`
> 登录后请立刻修改。这条消息看完可以删掉。
>
> Temporary password for {{STUDIO_NAME}}: `{{TEMPORARY_PASSWORD}}`
> Change it as soon as you sign in. You can delete this message afterwards.

**Never put the password in the welcome email.** Not as a postscript, not in
an attachment. The two-message split is the only part of this pack that is a
rule rather than a suggestion.

---

## Notes for whoever is sending it

* **The manual is public and stays public.** Sending the link is a courtesy
  and an onboarding step, not an access control — do not describe it to a
  customer as though it were one. What protects it is the rights notice at the
  foot of the page, not obscurity.
* **Deep-link, do not summarise.** `#team` and `#families` answer the two
  questions every new studio asks in the first week; pasting the answers into
  the email creates a second copy that will be wrong after the next release.
* Every link above is asserted by `backend/tests/test_welcome_pack.py`, so a
  route renamed in the app fails a test rather than a customer's first click.
