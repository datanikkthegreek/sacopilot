import { createFileRoute } from "@tanstack/react-router";
import { MeetingsView } from "@/components/meetings-view";

export const Route = createFileRoute("/meetings")({ component: MeetingsView });
