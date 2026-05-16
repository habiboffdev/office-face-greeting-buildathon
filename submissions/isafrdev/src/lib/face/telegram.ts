export async function sendTelegram(message: string, photo?: string | null) {
  try {
    const token = localStorage.getItem("visiongate:tg_token") || import.meta.env.VITE_TELEGRAM_TOKEN;
    const chatId = localStorage.getItem("visiongate:tg_chatid") || import.meta.env.VITE_TELEGRAM_CHATID;
    
    if (!token || !chatId) return;

    if (photo && photo.startsWith("data:")) {
      // Send photo with caption
      try {
        const blob = await fetch(photo).then(r => r.blob());
        const form = new FormData();
        form.append("chat_id", chatId);
        form.append("caption", message.replace(/<[^>]*>/g, "")); // strip HTML for caption
        form.append("parse_mode", "HTML");
        form.append("photo", blob, "snapshot.jpg");
        await fetch(`https://api.telegram.org/bot${token.trim()}/sendPhoto`, {
          method: "POST",
          body: form,
        });
        return;
      } catch {
        // fallback to text-only
      }
    }

    const url = `https://api.telegram.org/bot${token.trim()}/sendMessage`;
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId.trim(),
        text: message,
        parse_mode: "HTML"
      }),
    });
  } catch (e) {
    console.error("Telegram error:", e);
  }
}
