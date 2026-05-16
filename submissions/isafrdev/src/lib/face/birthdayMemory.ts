
export function hasBeenCelebratedToday(personId: string): boolean {
  try {
    const raw = localStorage.getItem("visiongate:birthday_celebrations");
    if (!raw) return false;
    const map = JSON.parse(raw) as Record<string, string>;
    const today = new Date().toISOString().split("T")[0];
    return map[personId] === today;
  } catch {
    return false;
  }
}

export function markCelebratedToday(personId: string) {
  try {
    const raw = localStorage.getItem("visiongate:birthday_celebrations");
    const map = raw ? (JSON.parse(raw) as Record<string, string>) : {};
    const today = new Date().toISOString().split("T")[0];
    map[personId] = today;
    localStorage.setItem("visiongate:birthday_celebrations", JSON.stringify(map));
  } catch {
    // ignore
  }
}
