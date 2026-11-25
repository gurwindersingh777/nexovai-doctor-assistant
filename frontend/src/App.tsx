import { useEffect } from "react";

import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { DoctorList } from "@/components/dashboard/DoctorList";
import { AppointmentList } from "@/components/dashboard/AppointmentList";
import { VoicePhone } from "@/components/voice/VoicePhone";

import { useDashboard } from "@/hooks/useDashboard";
import { useVoiceCall } from "@/hooks/useVoiceCall";

export default function App() {
  const voice = useVoiceCall();

  // Poll fast during a call so bookings show up almost instantly.
  const dashboard = useDashboard(voice.callState === "connected" ? 1500 : 15000);
  const { refresh } = dashboard;

  useEffect(() => {
    if (voice.callState === "ended") void refresh();
  }, [voice.callState, refresh]);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <DashboardHeader/>

        <main className="mt-8 grid gap-10 lg:grid-cols-[380px_minmax(0,1fr)] lg:gap-12">
          <div className="lg:sticky lg:top-6 lg:self-start">
            <VoicePhone
              state={voice.callState}
              muted={voice.muted}
              speaking={voice.speaking}
              seconds={voice.seconds}
              transcript={voice.transcript}
              error={voice.error}
              event={dashboard.lastEvent}
              getLevel={voice.getLevel}
              onStart={voice.startCall}
              onEnd={voice.endCall}
              onToggleMute={voice.toggleMute}
            />
          </div>

          <div className="space-y-12">
            <DoctorList doctors={dashboard.doctors} slots={dashboard.slots} />
            <AppointmentList
              appointments={dashboard.appointments}
              flashes={dashboard.flashes}
            />
          </div>
        </main>
      </div>
    </div>
  );
}