import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

const TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN');
const API_URL = `https://api.telegram.org/bot${TOKEN}/sendMessage`;

Deno.serve(async (req) => {
  try {
    const { employees, isDailyOnly } = await req.json();
    const base44 = createClientFromRequest(req);

    const settings = await base44.entities.CompanySettings.list().then(s => s[0]);
    if (!settings?.telegram_chat_id) {
      return Response.json({ error: 'Telegram chat ID not configured' }, { status: 400 });
    }

    let message = '';

    if (isDailyOnly) {
      // Daily summary
      const today = new Date().toISOString().split('T')[0];
      const todayLogs = await base44.entities.RecognitionLog.filter({});
      const uniqueToday = new Set(todayLogs.map(l => l.employee_id)).size;
      const birthdaysToday = todayLogs.filter(l => l.is_birthday).length;

      message = `📊 Daily Summary\n\nTotal visitors: ${uniqueToday}\nBirthdays today: ${birthdaysToday}`;
    } else {
      // Real-time alert
      if (employees.length === 1) {
        const emp = employees[0];
        message = `👤 ${emp.name}\n${emp.department ? `Department: ${emp.department}` : ''}`;
      } else if (employees.length > 1 && employees.length <= 10) {
        message = `🚪 ${employees.length} people arrived:\n${employees.map(e => `• ${e.name}`).join('\n')}`;
      } else if (employees.length > 10) {
        message = `🚪 Conference detected: ${employees.length} people`;
      }
    }

    await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: settings.telegram_chat_id,
        text: message,
        parse_mode: 'HTML'
      })
    });

    return Response.json({ success: true });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});