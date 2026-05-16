import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

const TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN');

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const { event, data } = await req.json();

    if (event.type !== 'create') return Response.json({ success: true });
    if (!data?.employee_name) return Response.json({ success: true });

    const companyId = data.company_id;

    // Get company settings to find telegram_chat_id
    const settingsList = companyId
      ? await base44.asServiceRole.entities.CompanySettings.filter({ company_id: companyId })
      : await base44.asServiceRole.entities.CompanySettings.list();

    const settings = settingsList[0];

    if (!settings?.telegram_chat_id) {
      return Response.json({ skipped: 'No telegram_chat_id configured' });
    }

    const name = data.employee_name;
    const dept = data.department || '';
    const isBirthday = data.is_birthday;

    let message = isBirthday
      ? `🎂 Birthday! ${name} arrived today!\n${dept ? `Department: ${dept}` : ''}`
      : `👤 ${name} recognized\n${dept ? `Department: ${dept}` : ''}`;

    const apiUrl = `https://api.telegram.org/bot${TOKEN}/sendMessage`;
    const res = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: settings.telegram_chat_id,
        text: message.trim(),
        parse_mode: 'HTML'
      })
    });

    if (!res.ok) {
      const body = await res.text();
      return Response.json({ error: `Telegram error: ${body}` }, { status: 500 });
    }

    return Response.json({ success: true });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});