import type { Appointment, BookingPayload, Doctor, DoctorSlot} from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(endpoint: string, options: RequestInit = {} ): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail || "Something went wrong");
  }

  return response.json() as Promise<T>;
}

export const api = {
  getDoctors: () =>
    request<Doctor[]>("/api/doctors"),

  getSlots: (doctorId?: string, date?: string) => {
    const params = new URLSearchParams();

    if (doctorId) params.set("doctor_id", doctorId);
    if (date) params.set("date", date);

    const query = params.toString();

    return request<DoctorSlot[]>(
      `/api/slots${query ? `?${query}` : ""}`,
    );
  },

   getAppointments: (phoneNumber?: string) =>
    request<Appointment[]>(
      phoneNumber
        ? `/api/appointments?phone_number=${encodeURIComponent(phoneNumber)}`
        : "/api/appointments",
    ),

  bookAppointment: (payload: BookingPayload) =>
    request<{ success: boolean; message: string }>(
      "/api/appointments",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  cancelAppointment: (appointmentId: string, phoneNumber: string) =>
    request<{ success: boolean; message: string }>(
      `/api/appointments/${appointmentId}/cancel`,
      {
        method: "POST",
        body: JSON.stringify({ phone_number: phoneNumber }),
      },
    ),
};
