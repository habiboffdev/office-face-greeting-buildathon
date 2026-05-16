/** Optional GPT polish / memory line for hourly follow-up (~1 sentence). */
export async function polishHourlyFollowUp(context: string, langHint: string): Promise<string | null> {
  const key = import.meta.env.VITE_OPENAI_API_KEY;
  if (!key || !context.trim()) return null;

  const body = {
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: `Rewrite as one short polite follow-up (${langHint}) for a kiosk: reference their last words briefly.`,
      },
      { role: "user", content: context.slice(0, 400) },
    ],
    temperature: 0.5,
    max_tokens: 80,
  };

  try {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const text = data?.choices?.[0]?.message?.content?.trim();
    return text?.length ? text : null;
  } catch {
    return null;
  }
}
