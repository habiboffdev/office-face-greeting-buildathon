import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);

    // Only callable by admins or scheduled automations (service role)
    const isScheduled = req.headers.get('x-base44-automation') === 'true';
    if (!isScheduled) {
      const user = await base44.auth.me();
      if (!user || user.role !== 'admin') {
        return Response.json({ error: 'Forbidden' }, { status: 403 });
      }
    }
    const now = new Date();

    const allUsers = await base44.asServiceRole.entities.User.list();
    const expired = allUsers.filter(u =>
      u.role === 'admin' &&
      u.trial_expires_at &&
      new Date(u.trial_expires_at) < now
    );

    let downgraded = 0;
    for (const u of expired) {
      await base44.asServiceRole.entities.User.update(u.id, { role: 'user' });
      downgraded++;
    }

    return Response.json({ success: true, downgraded });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});