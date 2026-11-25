export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  experience_years: number;
  bio: string;
}

export interface DoctorSlot {
  id: string;
  doctor_id: string;
  doctor_name: string;
  starts_at: string;
  status: string;
}

export type AppointmentStatus = "booked" | "cancelled";

export interface Appointment {
  id: string;
  patient_name: string;
  phone_number: string;
  doctor_name: string;
  specialty: string;
  starts_at: string;
  status: AppointmentStatus;
  created_at: string;
  cancelled_at: string | null;
}

export interface BookingPayload {
  patient_name: string;
  phone_number: string;
  doctor_id: string;
  slot_id: string;
}

export type FlashKind = "booked" | "cancelled";

export interface AppointmentEvent {
  kind: FlashKind;
  appointment: Appointment;
  at: number;
}