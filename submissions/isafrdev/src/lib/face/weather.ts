export async function getWeather(lang: "uz" | "en" | "ru" = "uz") {
  try {
    const res = await fetch("https://api.open-meteo.com/v1/forecast?latitude=41.2646&longitude=69.2163&current_weather=true");
    const data = await res.json();
    const temp = Math.round(data.current_weather.temperature);
    const code = data.current_weather.weathercode;
    
    if (lang === "en") {
      let desc = "the weather is great";
      if (code > 50) desc = "it might rain today, don't forget an umbrella";
      if (temp > 30) desc = "it's going to be quite hot today";
      return `The temperature is ${temp} degrees, ${desc}.`;
    }
    
    if (lang === "ru") {
      let desc = "погода отличная";
      if (code > 50) desc = "сегодня возможен дождь, не забудьте зонт";
      if (temp > 30) desc = "сегодня будет довольно жарко";
      return `Сейчас ${temp} градусов, ${desc}.`;
    }

    let desc = "havo yaxshi";
    if (code > 50) desc = "bugun yomg'ir yog'ishi mumkin, soyabon olishni unutmang";
    if (temp > 30) desc = "bugun havo ancha issiq bo'ladi";
    
    return `Hozir harorat ${temp} daraja, ${desc}.`;
  } catch {
    return lang === "en" ? "Unable to fetch weather." : lang === "ru" ? "Не удалось загрузить погоду." : "Ob-havo ma'lumotlarini yuklab bo'lmadi.";
  }
}

export function getTopNews() {
  const news = [
    "O'zbekistonda yangi IT texnoparklar ochilmoqda.",
    "Sun'iy intellekt sohasida katta yutuqlarga erishildi.",
    "Bugun yurtimizda bayramona kayfiyat hukmron.",
    "Texnologiya olamida yangi gadjetlar taqdim etildi."
  ];
  return news[Math.floor(Math.random() * news.length)];
}
