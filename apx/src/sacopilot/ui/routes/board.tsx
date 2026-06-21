import { createFileRoute } from "@tanstack/react-router";
import { BoardView } from "@/components/board-view";

export const Route = createFileRoute("/board")({ component: BoardView });
