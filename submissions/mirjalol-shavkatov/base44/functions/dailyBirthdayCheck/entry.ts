import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

Deno.serve(async (req) => {
  // This function is intended for scheduled/automated use only.
  // Verify via a shared secret to prevent unauthorized public calls.
  const secret = Deno.env.get("SCHEDULER_SECRET");
  if (secret) {
    const provided = req.headers.get("x-scheduler-secret") || new URL(req.url).searchParams.get("secret");
    if (provided !== secret) {
      return Response.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  const base44 = createClientFromRequest(req);

  const today = new Date();
  const todayMonth = today.getMonth() + 1;
  const todayDay = today.getDate();

  const employees = await base44.asServiceRole.entities.Employee.filter({ is_active: true });

  const birthdayPeople = employees.filter((emp) => {
    if (!emp.birth_date) return false;
    const parts = emp.birth_date.split("-");
    return parseInt(parts[1]) === todayMonth && parseInt(parts[2]) === todayDay;
  });

  if (birthdayPeople.length === 0) {
    return Response.json({ message: "No birthdays today", count: 0 });
  }

  const admins = await base44.asServiceRole.entities.User.filter({ role: "admin" });

  const names = birthdayPeople.map((e) => `• ${e.name}${e.position ? ` (${e.position})` : ""}`).join("\n");

  const subject = birthdayPeople.length === 1
    ? `🎂 Birthday today: ${birthdayPeople[0].name}`
    : `🎂 ${birthdayPeople.length} birthdays today!`;

  const body = `Hello,

Today's birthdays in the office:

${names}

When these employees arrive and are recognized by the display screen, a special birthday celebration will be shown automatically — confetti, a festive banner, and a personalized birthday greeting.

Have a great day!
— FaceGreet System`;

  await Promise.all(
    admins.map((admin) =>
      base44.asServiceRole.integrations.Core.SendEmail({
        to: admin.email,
        subject,
        body,
      })
    )
  );

  return Response.json({
    message: `Birthday notifications sent for ${birthdayPeople.length} employee(s)`,
    birthdays: birthdayPeople.map((e) => e.name),
    notified: admins.length,
  });
});