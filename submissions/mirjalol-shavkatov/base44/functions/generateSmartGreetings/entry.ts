import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

const UZBEK_HOLIDAYS = [
  { date: '01-01', name: 'New Year' },
  { date: '03-08', name: 'International Women\'s Day' },
  { date: '05-09', name: 'Memory and Honor Day' },
  { date: '09-01', name: 'Independence Day' },
  { date: '12-08', name: 'Constitution Day' }
];

const GREETINGS = {
  en: {
    welcome: (name) => `Welcome, ${name}!`,
    long_time_no_see: (name, days) => `Welcome back, ${name}! We haven't seen you in ${days} days.`,
    frequent_visitor: (name, times) => `Great to see you again, ${name}! That's ${times} times this week.`,
    morning: (name) => `Good morning, ${name}!`,
    afternoon: (name) => `Good afternoon, ${name}!`,
    evening: (name) => `Good evening, ${name}!`,
    holiday: (name, holidayName) => `Happy ${holidayName}, ${name}!`
  },
  uz: {
    welcome: (name) => `Xush kelibsiz, ${name}!`,
    long_time_no_see: (name, days) => `Qaytib kelganingizdan xursand, ${name}! ${days} kun ko'rmadik.`,
    frequent_visitor: (name, times) => `Shunga ko'ra, ${name}! Bu hafta ${times} marta kelibsiz.`,
    morning: (name) => `Xush kelibsiz ertalab, ${name}!`,
    afternoon: (name) => `Xush kelibsiz kunduzi, ${name}!`,
    evening: (name) => `Xush kelibsiz kechasi, ${name}!`,
    holiday: (name, holidayName) => `${holidayName} bilan tabriklaymiz, ${name}!`
  },
  ru: {
    welcome: (name) => `Добро пожаловать, ${name}!`,
    long_time_no_see: (name, days) => `С возвращением, ${name}! Мы не видели вас ${days} дней.`,
    frequent_visitor: (name, times) => `Хорошо снова вас видеть, ${name}! Это ${times} раз на этой неделе.`,
    morning: (name) => `Доброе утро, ${name}!`,
    afternoon: (name) => `Добрый день, ${name}!`,
    evening: (name) => `Добрый вечер, ${name}!`,
    holiday: (name, holidayName) => `С праздником ${holidayName}, ${name}!`
  }
};

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);

    // Get all active employees
    const employees = await base44.entities.Employee.filter({ is_active: true });
    const logs = await base44.entities.RecognitionLog.list("-created_date", 10000);
    
    const settings = await base44.entities.CompanySettings.list().then(s => s[0]);
    const lang = settings?.language || 'en';

    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    // Delete old greetings
    const oldGreetings = await base44.entities.SmartGreeting.list("-generated_date", 1000);
    for (const g of oldGreetings) {
      if (g.generated_date !== todayStr) {
        await base44.asServiceRole.entities.SmartGreeting.delete(g.id);
      }
    }

    // Check if today is a holiday
    const monthDay = `${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const todayHoliday = UZBEK_HOLIDAYS.find(h => h.date === monthDay);

    // Generate new greetings
    for (const emp of employees) {
      const empLogs = logs.filter(l => l.employee_id === emp.id);
      const thisWeekLogs = empLogs.filter(l => new Date(l.created_date) >= new Date(weekAgo));
      const lastGreeting = empLogs[0];
      const daysSinceLast = lastGreeting ? Math.floor((today - new Date(lastGreeting.created_date)) / (24 * 60 * 60 * 1000)) : 999;

      let greetingType = 'welcome';
      let greetingText = GREETINGS[lang].welcome(emp.name);

      // Holiday greeting (highest priority)
      if (todayHoliday) {
        greetingType = 'holiday';
        greetingText = GREETINGS[lang].holiday(emp.name, todayHoliday.name);
      }
      // Long time no see (>7 days)
      else if (daysSinceLast > 7 && lastGreeting) {
        greetingType = 'long_time_no_see';
        greetingText = GREETINGS[lang].long_time_no_see(emp.name, daysSinceLast);
      }
      // Frequent visitor (10+ times this week)
      else if (thisWeekLogs.length >= 10) {
        greetingType = 'frequent_visitor';
        greetingText = GREETINGS[lang].frequent_visitor(emp.name, thisWeekLogs.length);
      }
      // Time-based greeting (only if not long time no see)
      else if (daysSinceLast <= 7) {
        const hour = today.getHours();
        if (hour < 12) {
          greetingType = 'morning';
          greetingText = GREETINGS[lang].morning(emp.name);
        } else if (hour < 17) {
          greetingType = 'afternoon';
          greetingText = GREETINGS[lang].afternoon(emp.name);
        } else {
          greetingType = 'evening';
          greetingText = GREETINGS[lang].evening(emp.name);
        }
      }

      // Save the greeting
      await base44.asServiceRole.entities.SmartGreeting.create({
        employee_id: emp.id,
        greeting_text: greetingText,
        greeting_type: greetingType,
        generated_date: todayStr,
        valid_until: new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString()
      });
    }

    return Response.json({ success: true, count: employees.length });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});