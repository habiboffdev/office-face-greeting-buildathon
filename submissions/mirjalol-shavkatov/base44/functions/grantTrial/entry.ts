import { createClientFromRequest } from 'npm:@base44/sdk@0.8.25';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Only grant trial if not already set
    if (user.trial_expires_at) {
      return Response.json({ already_set: true });
    }

    const trialExpiry = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();

    // Use service role to set role + trial_expires_at
    await base44.asServiceRole.entities.User.update(user.id, {
      role: 'admin',
      trial_expires_at: trialExpiry,
    });

    return Response.json({ granted: true, trial_expires_at: trialExpiry });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});