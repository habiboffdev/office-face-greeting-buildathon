import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Cloud, TrendingUp, Newspaper, Clock } from "lucide-react";

export function SmartInfoCard() {
  const [now, setNow] = useState(new Date());
  
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Mock data - in a real app these would be fetched from APIs
  const weather = { temp: 28, city: "Toshkent", cond: "Ochiq osmon" };
  const rates = [
    { code: "USD", val: "12,850", up: true },
    { code: "EUR", val: "13,920", up: false },
  ];
  const news = [
    "UzCombinator startap inkubatori yangi mavsumni boshlamoqda",
    "IT Park rezidentlari soni 2000 tadan oshdi",
    "O'zbekistonda yangi AI laboratoriyasi ochildi",
  ];

  return (
    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-[#0a0a0b] via-[#111113] to-[#1a1a1d] p-8 md:p-16">
      <div className="grid h-full w-full max-w-7xl grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
        
        {/* Time & Weather */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="glass-strong flex flex-col justify-between rounded-[2.5rem] p-10 border border-white/5"
        >
          <div>
            <div className="flex items-center gap-3 text-primary mb-6">
              <Clock className="h-6 w-6" />
              <span className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold">Mahalliy Vaqt</span>
            </div>
            <div className="text-7xl font-display font-bold tracking-tighter tabular-nums">
              {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
            </div>
            <div className="text-lg text-muted-foreground mt-2 font-medium">
              {now.toLocaleDateString('uz-UZ', { weekday: 'long', day: 'numeric', month: 'long' })}
            </div>
          </div>
          
          <div className="mt-12 pt-10 border-t border-white/5">
            <div className="flex items-center gap-6">
              <div className="h-20 w-20 rounded-3xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-glow">
                <Cloud className="h-10 w-10 text-primary" />
              </div>
              <div>
                <div className="text-4xl font-bold">{weather.temp}°C</div>
                <div className="text-sm text-muted-foreground uppercase tracking-widest font-mono mt-1">{weather.city} // {weather.cond}</div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Exchange Rates */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="glass-strong rounded-[2.5rem] p-10 border border-white/5 flex flex-col"
        >
          <div className="flex items-center gap-3 text-primary mb-10">
            <TrendingUp className="h-6 w-6" />
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold">Valyuta Kurslari</span>
          </div>
          <div className="space-y-6 flex-1 flex flex-col justify-center">
            {rates.map(r => (
              <div key={r.code} className="flex items-center justify-between p-6 rounded-3xl bg-white/[0.02] border border-white/5">
                <div className="flex items-center gap-4">
                  <div className="h-12 w-12 rounded-2xl bg-white/5 flex items-center justify-center font-bold text-sm">{r.code}</div>
                  <div className="text-2xl font-bold">{r.val}</div>
                </div>
                <div className={`text-[10px] font-bold ${r.up ? 'text-emerald-500' : 'text-destructive'}`}>
                  {r.up ? '▲ 0.2%' : '▼ 0.1%'}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* News Feed */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="glass-strong lg:col-span-1 md:col-span-2 rounded-[2.5rem] p-10 border border-white/5 overflow-hidden relative"
        >
          <div className="flex items-center gap-3 text-primary mb-10">
            <Newspaper className="h-6 w-6" />
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold">So'nggi Yangiliklar</span>
          </div>
          <div className="space-y-6">
            {news.map((n, i) => (
              <motion.div 
                key={i} 
                initial={{ x: 20, opacity: 0 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.1 }}
                className="relative pl-6 border-l-2 border-primary/20"
              >
                <div className="text-lg font-medium leading-snug hover:text-primary transition-colors cursor-default">{n}</div>
                <div className="text-[9px] font-mono text-muted-foreground uppercase mt-2">Darakchi.uz // 14:30</div>
              </motion.div>
            ))}
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#111113] to-transparent pointer-events-none" />
        </motion.div>

      </div>
    </div>
  );
}
