/** Returns true if audio playback completed; false means no key / error (caller falls back). */
export async function speakElevenLabs(
  text: string,
  voiceId = "TX3LPaxmHKxFfWicjF17",
  apiKey?: string,
): Promise<boolean> {
  if (!text) return true;

  if (!apiKey?.trim()) return false;

  try {
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "xi-api-key": apiKey.trim(),
      },
      body: JSON.stringify({
        text,
        model_id: "eleven_multilingual_v2",
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
        },
      }),
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      console.error("[ElevenLabs] API Error body:", JSON.stringify(errorBody));
      throw new Error(`ElevenLabs API error: ${response.status}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await new Promise<void>((resolve, reject) => {
      const done = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onended = done;
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("audio playback error"));
      };
      void audio.play().catch((err) => {
        URL.revokeObjectURL(url);
        reject(err);
      });
    });
    return true;
  } catch (error) {
    console.error("ElevenLabs speak error, falling back to Web Speech API:", error);
    return false;
  }
}
