export const translations = {
  en: {
    recognized: "Recognized",
    birthday_label: "🎂 Birthday!",
    birthday_banner: "🎉 Today is their Birthday! 🎉",
    welcome: (name) => `Welcome, ${name}!`,
    happy_birthday: (name) => `🎂 Happy Birthday, ${name}!`,
    todays_schedule: "Today's Schedule",
    announcements: "Announcements",
    in_progress: "In progress",
  },
  uz: {
    recognized: "Aniqlandi",
    birthday_label: "🎂 Tug'ilgan kun!",
    birthday_banner: "🎉 Bugun uning tug'ilgan kuni! 🎉",
    welcome: (name) => `Xush kelibsiz, ${name}!`,
    happy_birthday: (name) => `🎂 Tug'ilgan kuningiz bilan, ${name}!`,
    todays_schedule: "Bugungi jadval",
    announcements: "E'lonlar",
    in_progress: "Davom etmoqda",
  },
  ru: {
    recognized: "Распознан",
    birthday_label: "🎂 День рождения!",
    birthday_banner: "🎉 Сегодня день рождения! 🎉",
    welcome: (name) => `Добро пожаловать, ${name}!`,
    happy_birthday: (name) => `🎂 С днём рождения, ${name}!`,
    todays_schedule: "Расписание на сегодня",
    announcements: "Объявления",
    in_progress: "В процессе",
  },
};

export function t(lang, key, arg) {
  const dict = translations[lang] || translations.en;
  const val = dict[key] ?? translations.en[key];
  return typeof val === "function" ? val(arg) : val;
}