import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type {
  Appointment,
  AppointmentEvent,
  Doctor,
  DoctorSlot,
  FlashKind,
} from "@/types";

export function useDashboard(pollMs = 15000) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [slots, setSlots] = useState<DoctorSlot[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [flashes, setFlashes] = useState<Record<string, FlashKind>>({});
  const [lastEvent, setLastEvent] = useState<AppointmentEvent | null>(null);

  const initialised = useRef(false);
  const known = useRef<Map<string, string>>(new Map());

  const detectChanges = useCallback((next: Appointment[]) => {
    const changed: Record<string, FlashKind> = {};
    let event: AppointmentEvent | null = null;

    // Skip the very first load so existing rows don't flash.
    if (initialised.current) {
      for (const appointment of next) {
        const previous = known.current.get(appointment.id);

        if (previous === undefined && appointment.status === "booked") {
          changed[appointment.id] = "booked";
          event = { kind: "booked", appointment, at: Date.now() };
        } else if (previous === "booked" && appointment.status === "cancelled") {
          changed[appointment.id] = "cancelled";
          event = { kind: "cancelled", appointment, at: Date.now() };
        }
      }
    }

    initialised.current = true;
    known.current = new Map(next.map((item) => [item.id, item.status]));
    setAppointments(next);

    const ids = Object.keys(changed);
    if (ids.length > 0) {
      setFlashes((previous) => ({ ...previous, ...changed }));
      window.setTimeout(() => {
        setFlashes((previous) => {
          const copy = { ...previous };
          for (const id of ids) delete copy[id];
          return copy;
        });
      }, 5000);
    }

    if (event) setLastEvent(event);
  }, []);

    const refresh = useCallback(async () => {
    const [doctorsResult, slotsResult, appointmentsResult] =
      await Promise.allSettled([
        api.getDoctors(),
        api.getSlots(),
        api.getAppointments(),
      ]);

    if (doctorsResult.status === "fulfilled") setDoctors(doctorsResult.value);
    if (slotsResult.status === "fulfilled") setSlots(slotsResult.value);
    if (appointmentsResult.status === "fulfilled") {
      detectChanges(appointmentsResult.value);
    }

    for (const result of [doctorsResult, slotsResult, appointmentsResult]) {
      if (result.status === "rejected") {
        console.error("Dashboard fetch failed:", result.reason);
      }
    }
  }, [detectChanges]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(id);
  }, [refresh, pollMs]);

  return {
    doctors,
    slots,
    appointments,
    flashes,
    lastEvent,
    refresh,
  };
}