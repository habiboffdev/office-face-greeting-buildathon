import { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ChevronRight, Building2, Users, Video, Settings } from 'lucide-react';

const STEPS = [
  { id: 1, title: 'Company Setup', icon: Building2 },
  { id: 2, title: 'Add Employees', icon: Users },
  { id: 3, title: 'Upload Videos', icon: Video },
  { id: 4, title: 'Configure Settings', icon: Settings }
];

export default function OnboardingWizard() {
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState('');
  const [skipped, setSkipped] = useState(false);

  useEffect(() => {
    const shown = localStorage.getItem('onboarding_shown');
    if (shown) setSkipped(true);
  }, []);

  if (skipped) return null;

  const handleSkip = () => {
    localStorage.setItem('onboarding_shown', 'true');
    setSkipped(true);
  };

  const handleNext = async () => {
    if (step === 1 && companyName) {
      const existing = await base44.entities.CompanySettings.list();
      if (existing.length > 0) {
        await base44.entities.CompanySettings.update(existing[0].id, { company_name: companyName });
      } else {
        await base44.entities.CompanySettings.create({ company_name: companyName });
      }
    }
    if (step < 4) {
      setStep(step + 1);
    } else {
      handleSkip();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-card rounded-2xl p-8 max-w-lg w-full mx-4 shadow-xl border border-border">
        {/* Progress */}
        <div className="flex gap-2 mb-8">
          {STEPS.map((s) => (
            <div
              key={s.id}
              className={`flex-1 h-1 rounded-full transition-colors ${
                s.id <= step ? 'bg-primary' : 'bg-muted'
              }`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="mb-8">
          {step === 1 && (
            <div>
              <div className="flex items-center gap-3 mb-6">
                <Building2 className="w-6 h-6 text-primary" />
                <h2 className="text-2xl font-display font-semibold">Company Setup</h2>
              </div>
              <p className="text-muted-foreground mb-4">Let's start with your company name</p>
              <Input
                placeholder="Company Name"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="mb-4"
              />
            </div>
          )}

          {step === 2 && (
            <div>
              <div className="flex items-center gap-3 mb-6">
                <Users className="w-6 h-6 text-primary" />
                <h2 className="text-2xl font-display font-semibold">Add Employees</h2>
              </div>
              <p className="text-muted-foreground mb-4">
                Go to the Admin Panel → Employees tab and add your team members with their photos
              </p>
            </div>
          )}

          {step === 3 && (
            <div>
              <div className="flex items-center gap-3 mb-6">
                <Video className="w-6 h-6 text-primary" />
                <h2 className="text-2xl font-display font-semibold">Upload Videos</h2>
              </div>
              <p className="text-muted-foreground mb-4">
                Add promotional videos to play on the display screen. Go to Admin Panel → Videos
              </p>
            </div>
          )}

          {step === 4 && (
            <div>
              <div className="flex items-center gap-3 mb-6">
                <Settings className="w-6 h-6 text-primary" />
                <h2 className="text-2xl font-display font-semibold">Configure Settings</h2>
              </div>
              <p className="text-muted-foreground mb-4">
                Customize language, idle screen timeout, Telegram alerts, and more in Settings tab
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleSkip} className="flex-1">
            Skip
          </Button>
          <Button
            onClick={handleNext}
            disabled={step === 1 && !companyName}
            className="flex-1 gap-2"
          >
            {step === 4 ? 'Finish' : 'Next'}
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}