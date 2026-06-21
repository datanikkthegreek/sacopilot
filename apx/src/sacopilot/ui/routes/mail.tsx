import { createFileRoute } from "@tanstack/react-router";
import { MailView } from "@/components/mail-view";

export const Route = createFileRoute("/mail")({ component: MailView });
