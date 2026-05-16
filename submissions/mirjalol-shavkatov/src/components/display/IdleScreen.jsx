import { useEffect, useState } from 'react';
import { useCompanySettings } from '@/lib/useCompanySettings';

export default function IdleScreen({ isIdle, companyId }) {
  const { company_name, logo_url, brand_color } = useCompanySettings(companyId);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  if (!isIdle) return null;

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center z-15 bg-gradient-to-b from-black via-gray-900 to-black pointer-events-none">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full opacity-5 animate-pulse"
            style={{
              width: Math.random() * 400 + 100 + 'px',
              height: Math.random() * 400 + 100 + 'px',
              background: brand_color,
              left: Math.random() * 100 + '%',
              top: Math.random() * 100 + '%',
              animation: `float ${10 + Math.random() * 10}s infinite linear`
            }}
          />
        ))}
      </div>

      {/* Content */}
      <div className="relative z-10 text-center">
        {logo_url && (
          <img 
            src={logo_url} 
            alt="logo" 
            className="w-24 h-24 mx-auto mb-8 object-contain animate-pulse"
          />
        )}
        
        <h1 className="text-5xl font-display font-semibold text-white mb-6">
          {company_name}
        </h1>

        <div className="text-6xl font-display font-light text-white tracking-wider mb-4 font-mono">
          {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>

        <p className="text-xl text-white/50 font-light">
          {time.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </p>

        <div 
          className="mt-12 h-1 w-32 mx-auto rounded-full opacity-40 animate-pulse"
          style={{ background: brand_color }}
        />
      </div>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(30px); }
        }
      `}</style>
    </div>
  );
}