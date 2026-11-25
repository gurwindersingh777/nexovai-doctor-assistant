import { Badge } from "@/components/ui/badge";
import { SectionHeading } from "@/components/dashboard/SectionHeading";
import { fmtTime, groupSlotsByDay, initials } from "@/lib/format";
import type { Doctor, DoctorSlot } from "@/types";

interface DoctorListProps {
  doctors: Doctor[];
  slots: DoctorSlot[];
}

export function DoctorList({ doctors, slots }: DoctorListProps) {
  return (
    <section>
      <SectionHeading title="Doctors" meta={`${slots.length} open slots`} />

      <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
        {doctors.length === 0 && (
          <p className="px-5 py-12 text-center text-sm text-muted-foreground">
            No doctors yet
          </p>
        )}

        {doctors.map((doctor) => {
          const days = groupSlotsByDay(
            slots.filter((slot) => slot.doctor_id === doctor.id),
          );

          return (
            <article
              key={doctor.id}
              title={doctor.bio}
              className="flex flex-col gap-5 p-5 sm:flex-row sm:gap-8"
            >
              <div className="flex items-start gap-4 sm:w-60 sm:shrink-0">
                <div className="grid size-12 shrink-0 place-items-center rounded-full bg-primary font-display text-lg text-primary-foreground">
                  {initials(doctor.name)}
                </div>
                <div>
                  <h3 className="font-display text-2xl leading-tight">
                    {doctor.name}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {doctor.specialty} · {doctor.experience_years} yrs
                  </p>
                </div>
              </div>

              <div className="flex-1 space-y-2">
                {days.length === 0 && (
                  <p className="text-sm text-muted-foreground">No open slots</p>
                )}

                {days.map((day) => (
                  <div key={day.key} className="flex flex-wrap items-center gap-2">
                    <span className="w-24 shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {day.label}
                    </span>
                    {day.slots.map((slot) => (
                      <Badge
                        key={slot.id}
                        variant="outline"
                        className="h-auto rounded-md bg-background px-2.5 py-1 text-xs font-normal tabular-nums"
                      >
                        {fmtTime(slot.starts_at)}
                      </Badge>
                    ))}
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}