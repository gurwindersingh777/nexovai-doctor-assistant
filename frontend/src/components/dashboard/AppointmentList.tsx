import { Badge } from "@/components/ui/badge";
import { SectionHeading } from "@/components/dashboard/SectionHeading";
import { cn } from "@/lib/utils";
import {
  fmtDayNumber,
  fmtMonth,
  fmtTime,
  fmtWeekday,
  maskPhone,
} from "@/lib/format";
import type { Appointment, FlashKind } from "@/types";

interface AppointmentListProps {
  appointments: Appointment[];
  flashes: Record<string, FlashKind>;
}

export function AppointmentList({ appointments, flashes }: AppointmentListProps) {
  const booked = appointments.filter((item) => item.status === "booked").length;

  return (
    <section>
      <SectionHeading title="Appointments" meta={`${booked} booked`} />

      <div className="overflow-hidden rounded-2xl border border-border bg-card">
        {appointments.length === 0 ? (
          <p className="px-5 py-12 text-center text-sm text-muted-foreground">
            Nothing booked yet. Start a call.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {appointments.map((item) => {
              const cancelled = item.status === "cancelled";
              const flash = flashes[item.id];

              return (
                <li
                  key={item.id}
                  className={cn(
                    "grid grid-cols-[3.5rem_minmax(0,1fr)_auto] items-center gap-4 px-5 py-4",
                    flash === "booked" && "anim-flash-booked",
                    flash === "cancelled" && "anim-flash-cancelled",
                  )}
                >
                  <div
                    className={cn("text-center leading-none", cancelled && "opacity-40")}
                  >
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                      {fmtWeekday(item.starts_at)}
                    </p>
                    <p className="my-0.5 font-display text-3xl">
                      {fmtDayNumber(item.starts_at)}
                    </p>
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                      {fmtMonth(item.starts_at)}
                    </p>
                  </div>

                  <div className={cn("min-w-0", cancelled && "opacity-50")}>
                    <p className="truncate font-medium">{item.patient_name}</p>
                    <p className="truncate text-sm text-muted-foreground">
                      {item.doctor_name} · {item.specialty}
                    </p>
                    <p
                      className={cn(
                        "text-sm tabular-nums",
                        cancelled && "line-through",
                      )}
                    >
                      {fmtTime(item.starts_at)}
                    </p>
                  </div>

                  <div className="flex flex-col items-end gap-1.5">
                    {cancelled ? (
                      <Badge variant="secondary" className="rounded-md">
                        Cancelled
                      </Badge>
                    ) : (
                      <Badge className="rounded-md border-transparent bg-[#d6f55c] text-[#1b2b12] hover:bg-[#d6f55c]">
                        Booked
                      </Badge>
                    )}
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {maskPhone(item.phone_number)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}