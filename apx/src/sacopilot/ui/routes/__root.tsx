import { ThemeProvider } from "@/components/apx/theme-provider";
import { ModeToggle } from "@/components/apx/mode-toggle";
import { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet, Link } from "@tanstack/react-router";
import { Toaster } from "sonner";

const TABS = [["/mail", "Mail"], ["/meetings", "Meetings"], ["/usecases", "Use-Cases"]] as const;

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient;
}>()({
  component: () => (
    <ThemeProvider defaultTheme="dark" storageKey="apx-ui-theme">
      <div className="h-screen flex flex-col bg-background text-foreground">
        <header className="h-14 flex items-center gap-4 px-4 border-b bg-background/80 backdrop-blur-sm">
          <h1 className="text-sm font-semibold tracking-tight">SA Copilot</h1>
          <nav className="flex gap-1">
            {TABS.map(([to, label]) => (
              <Link key={to} to={to}
                className="px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-muted/60 transition-colors"
                activeProps={{ className: "px-3 py-1.5 rounded-md text-sm bg-muted font-semibold" }}>
                {label}
              </Link>
            ))}
          </nav>
          <div className="flex-1" />
          <ModeToggle />
        </header>
        <div className="flex-1 min-h-0">
          <Outlet />
        </div>
      </div>
      <Toaster richColors />
    </ThemeProvider>
  ),
});
