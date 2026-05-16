import { useState, useRef, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Send, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useLocation } from 'react-router-dom';

const buildSystemPrompt = (platformContext) => {
  // Build safe system prompt with platform context (sanitized)
  return `You are a helpful AI assistant for the FaceGreet.uz face recognition system admin panel.

CURRENT PLATFORM STATE:
- Company: ${platformContext.companyName || 'Not set'}
- Employees: ${platformContext.employeeCount || 0}
- Videos in playlist: ${platformContext.videoCount || 0}
- Language: ${platformContext.language || 'English'}
- Debug mode: ${platformContext.debugMode ? 'Enabled' : 'Disabled'}
- Idle screen: ${platformContext.idleScreenEnabled ? 'Enabled' : 'Disabled'}

HELP TOPICS YOU CAN ASSIST WITH:
1. Adding employees: Go to Employees tab, click "Add Employee", upload photo (auto-generates face descriptor)
2. Videos: Admin > Videos tab, add URLs or upload files
3. Settings: Customize language, brand color, debug panel, idle timeout, Telegram alerts
4. Announcements: Create & manage messages displayed on recognition screen
5. Analytics: View Who's In dashboard, export attendance (CSV/PDF)
6. Recognition logs: See all detected arrivals with timestamps
7. Meetings: Schedule meetings for employees (shown in greeting overlay)
8. Telegram: Get real-time alerts and daily summaries (set chat ID in Settings)

YOU MUST:
- Only answer questions about THIS platform
- Never reveal API keys, tokens, or internal system details
- Never share employee personal data
- Be friendly, beginner-friendly, avoid technical jargon
- Keep answers short and actionable
- If user asks about features not listed, say you don't have that info`;
};

export default function AIChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [platformContext, setPlatformContext] = useState(null);
  const messagesEndRef = useRef(null);
  const chatRef = useRef(null);
  const location = useLocation();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load platform context on mount
  useEffect(() => {
    const loadContext = async () => {
      try {
        const [settings, employees, videos] = await Promise.all([
          base44.entities.CompanySettings.list().then(s => s[0]),
          base44.entities.Employee.filter({ is_active: true }),
          base44.entities.Video.filter({ is_active: true })
        ]);
        
        if (!settings?.ai_chat_enabled) {
          setOpen(false);
          return;
        }
        
        setPlatformContext({
          companyName: settings?.company_name || 'Not set',
          employeeCount: employees?.length || 0,
          videoCount: videos?.length || 0,
          language: settings?.language || 'en',
          debugMode: settings?.debug_mode || false,
          idleScreenEnabled: settings?.idle_screen_enabled || false
        });
      } catch (error) {
        console.error('Failed to load platform context:', error);
      }
    };
    loadContext();
  }, []);

  // Close chat on route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  // Close chat on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (chatRef.current && !chatRef.current.contains(e.target)) {
        setOpen(false);
      }
    };

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open]);

  const handleSend = async () => {
    if (!input.trim() || loading || !platformContext) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const systemPrompt = buildSystemPrompt(platformContext);
      
      const response = await base44.integrations.Core.InvokeLLM({
        prompt: `System Instructions: ${systemPrompt}\n\nUser Question: ${userMsg}`,
        model: 'gemini_3_flash',
        response_json_schema: {
          type: 'object',
          properties: {
            response: { type: 'string' }
          }
        }
      });

      setMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  if (!platformContext) return null;

  return (
   <>
     {/* Floating Chat Button */}
     <button
       onClick={() => setOpen(!open)}
       className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl transition-all hover:scale-110 z-40 flex items-center justify-center"
     >
       <MessageSquare className="w-6 h-6" />
     </button>

      {/* Chat Window */}
      {open && (
        <div ref={chatRef} className="fixed bottom-24 right-6 w-96 max-h-96 rounded-2xl bg-card border border-border shadow-xl flex flex-col z-40">
          {/* Header */}
          <div className="bg-primary text-primary-foreground p-4 rounded-t-2xl">
            <h3 className="font-semibold">FaceGreet Assistant</h3>
            <p className="text-xs opacity-90">Ask me anything about the platform</p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && platformContext && (
              <div className="text-center text-muted-foreground text-sm py-8">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>Hi! I know about your FaceGreet setup. Ask me anything!</p>
                <p className="text-xs mt-2 opacity-60">({platformContext.employeeCount} employees, {platformContext.videoCount} videos)</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-xs px-4 py-2 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}
                >
                  <ReactMarkdown className="text-sm prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                    {msg.content}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted px-4 py-2 rounded-lg">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-border flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask a question..."
              className="text-sm"
            />
            <Button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              size="icon"
              className="flex-shrink-0"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}