import { useEffect, useMemo, useState } from "react";
import Sidebar, { ScreenKey } from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Dashboard from "./screens/Dashboard";
import Overview from "./screens/Overview";
import UploadDetection from "./screens/UploadDetection";
import FingerprintScreen from "./screens/Fingerprint";
import EvidenceLocker from "./screens/EvidenceLocker";
import LineageMap from "./screens/LineageMap";
import AttributionGap from "./screens/AttributionGap";
import IncidentReport from "./screens/IncidentReport";
import CaseAutomation from "./screens/CaseAutomation";
import Roadmap from "./screens/Roadmap";
import Landing from "./screens/Landing";
import Login from "./screens/Login";
import NewInvestigation from "./screens/NewInvestigation";
import Settings from "./screens/Settings";
import MfaPanel from "./components/MfaPanel";
import Investigations from "./screens/Investigations";
import ResponsibleUse from "./screens/ResponsibleUse";
import InvestigationLayout from "./components/InvestigationLayout";
import { CaseProvider, useCase } from "./context/CaseContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoadingState } from "./components/states";
import DemoModeBanner from "./components/DemoModeBanner";
import CommandPalette from "./components/CommandPalette";
import { AnimatePresence, MotionRoot, PageTransition } from "./components/motion";
import type { Command } from "./lib/commandSearch";

function screenFromPath(path: string): ScreenKey | "landing" | "login" | "responsible" {
  if (path === "/" || path === "") return "landing";
  if (path === "/login") return "login";
  if (path === "/responsible-use") return "responsible";
  if (path === "/dashboard") return "dashboard";
  if (path === "/investigations" || path === "/investigations/") return "investigations";
  if (path === "/investigations/new") return "new";
  if (path.includes("/detection")) return "detection";
  if (path.includes("/fingerprint")) return "fingerprint";
  if (path.includes("/evidence")) return "evidence";
  if (path.includes("/lineage")) return "lineage";
  if (path.includes("/attribution")) return "gap";
  if (path.includes("/report")) return "report";
  if (path.includes("/automation")) return "automation";
  if (path.startsWith("/investigations/")) return "overview";
  if (path === "/roadmap") return "roadmap";
  if (path === "/settings") return "settings";
  return "dashboard";
}

const paths: Record<ScreenKey, string> = {
  dashboard: "/dashboard",
  investigations: "/investigations",
  new: "/investigations/new",
  overview: "/investigations",
  detection: "/investigations",
  fingerprint: "/investigations",
  evidence: "/investigations",
  lineage: "/investigations",
  gap: "/investigations",
  report: "/investigations",
  automation: "/investigations",
  roadmap: "/roadmap",
  settings: "/settings",
};

const investigationScreenKeys = new Set<ScreenKey>([
  "overview",
  "detection",
  "fingerprint",
  "evidence",
  "lineage",
  "gap",
  "report",
  "automation",
]);

export default function App() {
  return (
    <MotionRoot>
      <AuthProvider>
        <CaseProvider>
          <AppShell />
        </CaseProvider>
      </AuthProvider>
    </MotionRoot>
  );
}

function AppShell() {
  const { user, loading: authLoading, logout } = useAuth();
  const { incidentId, setIncidentId } = useCase();
  const [route, setRoute] = useState<ScreenKey | "landing" | "login" | "responsible">(screenFromPath(window.location.pathname));
  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("lineage_theme") === "dark");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const investigationPath = (s: ScreenKey, id: string | null) => {
    if (!id) return paths[s];
    const base = `/investigations/${encodeURIComponent(id)}`;
    const suffix: Partial<Record<ScreenKey, string>> = {
      overview: "", detection: "/detection", fingerprint: "/fingerprint", evidence: "/evidence",
      lineage: "/lineage", gap: "/attribution", report: "/report", automation: "/automation",
    };
    return suffix[s] !== undefined ? `${base}${suffix[s]}` : paths[s];
  };

  const navigate = (s: ScreenKey | "landing" | "login" | "responsible") => {
    const activeId = incidentId ?? localStorage.getItem("lineage_active_incident");
    const p = s === "landing" ? "/" : s === "login" ? "/login" : s === "responsible" ? "/responsible-use" : investigationScreenKeys.has(s as ScreenKey) ? investigationPath(s as ScreenKey, activeId) : paths[s];
    window.history.pushState({}, "", p);
    setRoute(s);
    setMobileNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    const syncRoute = () => {
      const match = window.location.pathname.match(/^\/investigations\/([^/]+)(?:\/|$)/);
      if (match) setIncidentId(decodeURIComponent(match[1]));
      setRoute(screenFromPath(window.location.pathname));
    };
    syncRoute();
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, [setIncidentId]);

  useEffect(() => {
    document.documentElement.classList.toggle("theme-dark", dark);
    localStorage.setItem("lineage_theme", dark ? "dark" : "light");
  }, [dark]);

  // Ctrl/Cmd+K toggles the command palette (only once signed in, never on the landing or login screens).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        if (!user || route === "landing" || route === "login") return;
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [user, route]);

  const openInvestigation = (id: string) => {
    setIncidentId(id);
    window.history.pushState({}, "", `/investigations/${encodeURIComponent(id)}`);
    setRoute("overview");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const commands = useMemo<Command[]>(() => {
    const go = (label: string, key: ScreenKey, group: string, keywords: string[] = []): Command => ({ id: `go-${key}-${label}`, label, group, keywords, hint: "Go to", run: () => navigate(key) });
    const list: Command[] = [
      go("Dashboard", "dashboard", "Navigate"), go("Investigations", "investigations", "Navigate", ["cases"]),
      go("New Investigation", "new", "Navigate", ["create", "start"]), go("Roadmap", "roadmap", "Navigate"), go("Settings", "settings", "Navigate", ["preferences", "account"]),
    ];
    if (incidentId) {
      list.push(
        go("Case overview", "overview", "Current case"), go("Detection Analysis", "detection", "Current case", ["deepfake", "manipulation"]),
        go("Fingerprinting", "fingerprint", "Current case", ["hash", "phash"]), go("Evidence Locker", "evidence", "Current case", ["sha-256", "preserve"]),
        go("Lineage / Propagation", "lineage", "Current case", ["graph", "map", "sources"]), go("Attribution Gap", "gap", "Current case"),
        go("Incident Report", "report", "Current case", ["pdf", "export"]), go("Case Automation", "automation", "Current case", ["timeline", "alerts"]),
      );
    }
    list.push(
      { id: "toggle-theme", label: dark ? "Switch to light theme" : "Switch to dark theme", group: "Actions", keywords: ["dark", "light", "theme"], run: () => setDark(!dark) },
      { id: "quick-exit", label: "Quick exit", group: "Actions", hint: "Leave this site immediately", keywords: ["safety", "panic", "leave"], run: () => window.location.replace("https://www.google.com") },
      { id: "sign-out", label: "Sign out", group: "Actions", run: () => { logout(); navigate("landing"); } },
    );
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId, dark]);

  // Wait for the stored token to be validated before deciding what to show —
  // otherwise a logged-in user briefly sees the landing page on every reload.
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <LoadingState label="Restoring your session…" />
      </div>
    );
  }

  if (route === "responsible") return <ResponsibleUse />;
  if (route === "landing") return <Landing onStart={() => navigate("login")} onLogin={() => navigate("login")} />;
  if (route === "login") return <Login onLogin={() => navigate("dashboard")} onBack={() => navigate("landing")} />;

  // Auth guard: every screen past this point needs a real session.
  if (!user) return <Login onLogin={() => navigate("dashboard")} onBack={() => navigate("landing")} />;

  // Two-factor required by the deployment and not yet set up: the API refuses everything else, so show only the setup panel.
  if (user.mfa_setup_required) {
    return (
      <div className="min-h-screen flex bg-bg text-ink">
        <div className="m-auto w-full max-w-md px-6">
          <h2 className="font-display text-2xl text-ink">Set up two-factor sign-in</h2>
          <p className="text-[13px] text-muted mt-2 mb-4">This deployment requires a second factor before you can open any case.</p>
          <MfaPanel required />
          <button onClick={() => window.location.reload()} className="mt-4 rounded-xl border border-border px-4 py-2 text-[12.5px]">Continue</button>
        </div>
      </div>
    );
  }

  // Investigation screens need an active case — send the user to pick one
  // rather than rendering a case view with nothing loaded.
  if (investigationScreenKeys.has(route as ScreenKey) && !incidentId) {
    return (
      <div className="min-h-screen flex bg-bg text-ink">
        <div className="m-auto text-center max-w-md px-6">
          <h2 className="font-display text-2xl text-ink">No investigation selected</h2>
          <p className="text-[13px] text-muted mt-2">
            Open an existing investigation or start a new one to view its analysis.
          </p>
          <div className="flex gap-2 justify-center mt-5">
            <button onClick={() => navigate("investigations")} className="rounded-xl border border-border px-4 py-2.5 text-[12.5px] font-medium">
              Browse Investigations
            </button>
            <button onClick={() => navigate("new")} className="rounded-xl bg-brand text-white px-4 py-2.5 text-[12.5px] font-semibold">
              New Investigation
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isInvestigationRoute = typeof route === "string" && investigationScreenKeys.has(route as ScreenKey);

  return (
    <>
      <div className={`min-h-screen flex bg-bg text-ink ${dark ? "dark-ui" : ""}`}>
        <Sidebar
          active={route as ScreenKey}
          onSelect={navigate}
          collapsed={collapsed}
          setCollapsed={setCollapsed}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
        />
        <div className="min-w-0 flex-1 flex flex-col min-h-screen">
          <TopBar
            dark={dark}
            setDark={setDark}
            onMenuClick={() => setMobileNavOpen(true)}
            onOpenPalette={() => setPaletteOpen(true)}
            user={user}
            onLogout={() => { logout(); navigate("landing"); }}
            onSearch={(q) => { window.history.pushState({}, "", `/investigations?search=${encodeURIComponent(q)}`); setRoute("investigations"); }}
          />
          <DemoModeBanner />
          <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-7">
            {isInvestigationRoute ? (
              <InvestigationLayout activeTab={route as ScreenKey} onNavigate={navigate}>
                {route === "overview" && <Overview onNavigate={navigate} />}
                {route === "detection" && <UploadDetection />}
                {route === "fingerprint" && <FingerprintScreen />}
                {route === "evidence" && <EvidenceLocker />}
                {route === "lineage" && <LineageMap onNavigate={navigate} />}
                {route === "gap" && <AttributionGap onNavigate={navigate} />}
                {route === "report" && <IncidentReport />}
                {route === "automation" && <CaseAutomation onNavigate={navigate} />}
              </InvestigationLayout>
            ) : (
              <div className="max-w-[1400px] mx-auto">
                <AnimatePresence mode="wait" initial={false}>
                  <PageTransition key={String(route)} id={String(route)}>
                    {route === "dashboard" && <Dashboard onNavigate={navigate} />}
                    {route === "investigations" && <Investigations onNavigate={navigate} />}
                    {route === "new" && <NewInvestigation onNavigate={navigate} />}
                    {route === "roadmap" && <Roadmap />}
                    {route === "settings" && <Settings dark={dark} setDark={setDark} />}
                  </PageTransition>
                </AnimatePresence>
              </div>
            )}
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} onOpenInvestigation={openInvestigation} />
    </>
  );
}
