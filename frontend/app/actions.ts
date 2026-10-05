"use server";

import { revalidatePath } from "next/cache";
import { addIncidentNote, seedDemoData, updateIncidentStatus } from "../lib/api";
import type { IncidentStatus } from "../lib/types";

export type ActionResult = { ok: true } | { ok: false; error: string };

const allowedStatuses: IncidentStatus[] = ["open", "acknowledged", "resolved"];

function toActionResult(error: unknown): ActionResult {
  return { ok: false, error: error instanceof Error ? error.message : "Request failed" };
}

export async function setIncidentStatusAction(
  incidentId: string,
  status: IncidentStatus,
): Promise<ActionResult> {
  if (!allowedStatuses.includes(status)) {
    return { ok: false, error: `Unknown status: ${status}` };
  }
  try {
    await updateIncidentStatus(incidentId, status);
  } catch (error) {
    return toActionResult(error);
  }
  revalidatePath("/");
  revalidatePath(`/incidents/${incidentId}`);
  return { ok: true };
}

export async function addIncidentNoteAction(
  incidentId: string,
  formData: FormData,
): Promise<ActionResult> {
  const text = String(formData.get("text") ?? "").trim();
  const author = String(formData.get("author") ?? "").trim() || "operator";
  if (!text) {
    return { ok: false, error: "Note text is required" };
  }
  try {
    await addIncidentNote(incidentId, author.slice(0, 80), text.slice(0, 4000));
  } catch (error) {
    return toActionResult(error);
  }
  revalidatePath(`/incidents/${incidentId}`);
  return { ok: true };
}

export async function seedDemoDataAction(): Promise<ActionResult> {
  try {
    await seedDemoData(12);
  } catch (error) {
    return toActionResult(error);
  }
  revalidatePath("/");
  return { ok: true };
}
