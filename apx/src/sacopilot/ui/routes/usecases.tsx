import { createFileRoute } from "@tanstack/react-router";
import { UseCasesView } from "@/components/usecases-view";

export const Route = createFileRoute("/usecases")({ component: UseCasesView });
