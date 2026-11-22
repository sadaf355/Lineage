import { useEffect, useState } from "react";
import { Bell, Database, Lock, Palette, Shield, User, Download, Trash2, ChevronRight, Gauge, HeartHandshake } from "lucide-react";
import { Panel, PanelHeader, StatusBadge, SectionTitle } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useCase } from "../context/CaseContext";
import { api } from "../lib/api";
import MfaPanel from "../components/MfaPanel";
import DetectorEvaluationPanel from "../components/DetectorEvaluationPanel";
import { Stagger, StaggerItem } from "../components/motion";

type Category = "Profile" | "Security" | "Detector" | "Privacy" | "Notifications" | "Data Management" | "Trust & Safety" | "Appearance";

export default function Settings({ dark, setDark }: { dark: boolean; setDark: (v: boolean) => void }) {
  const [activeCategory, setActiveCategory] = useState<Category>("Profile");
  const { user } = useAuth();
  const { incidentId, setIncidentId } = useCase();
  const [securityStatus, setSecurityStatus] = useState<any>(null);
  useEffect(() => { if (incidentId) api.securityStatus(incidentId).then(setSecurityStatus).catch(() => setSecurityStatus(null)); }, [incidentId]);

  const categories: [Category, any][] = [
    ["Profile", User],
    ["Security", Lock],
    ["Detector", Gauge],
    ["Privacy", Shield],
    ["Notifications", Bell],
    ["Data Management", Database],
    ["Trust & Safety", HeartHandshake],
    ["Appearance", Palette],
  ];

  return (
    <Stagger className="max-w-[1250px] mx-auto space-y-6">
      <StaggerItem><SectionTitle title="Settings" description="Manage your account, privacy, security, and preferences." /></StaggerItem>

      <StaggerItem><div className="grid lg:grid-cols-[240px_1fr] gap-6 items-start">
        {/* Left Menu Bar */}
        <Panel className="p-2 sm:p-3 overflow-x-auto no-scrollbar">
          <div className="flex lg:flex-col gap-1 min-w-max lg:min-w-0">
            {categories.map(([t, Icon]) => {
              const isActive = activeCategory === t;
              return (
                <button
                  key={t}
                  onClick={() => setActiveCategory(t)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[13px] font-medium text-left transition-all ${
                    isActive
                      ? "bg-soft text-brand font-semibold shadow-xs"
                      : "text-muted hover:text-ink hover:bg-soft/40"
                  }`}
                >
                  <Icon size={18} className={isActive ? "text-brand" : "text-muted"} />
                  {t}
                </button>
              );
            })}
          </div>
        </Panel>

        {/* Right Pane — Single Expanded Active Card */}
        <div className="w-full">
          {activeCategory === "Profile" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader
                title="Profile Information"
                subtitle="Manage your investigator details and pseudonymous profile."
                right={<button className="text-[12px] font-medium border border-border rounded-lg px-3.5 py-1.5 hover:bg-soft transition">Edit</button>}
              />
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 p-5 rounded-2xl bg-soft/50 border border-border/60">
                <div className="h-16 w-16 rounded-2xl bg-brand text-white flex items-center justify-center font-display text-2xl shadow-sm shrink-0">
                  A
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-ink">{user?.display_name || user?.email?.split("@")[0] || "Investigator"}</h3>
                  <p className="text-[13px] text-muted mt-0.5">{user?.email || "—"}</p>
                  <div className="flex gap-2 mt-2">
                    <StatusBadge tone="green">Verified Investigator</StatusBadge>
                  </div>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-4 pt-4 border-t border-border/60">
                <div className="p-4 rounded-xl border border-border/60 bg-[#FAFBF9]">
                  <p className="text-muted text-[12px] font-medium">Role</p>
                  <p className="mt-1 font-semibold text-ink text-[14px]">Lead Investigator</p>
                </div>
                <div className="p-4 rounded-xl border border-border/60 bg-[#FAFBF9]">
                  <p className="text-muted text-[12px] font-medium">Account Privacy Mode</p>
                  <p className="mt-1 font-semibold text-ink text-[14px]">Pseudonymous ID</p>
                </div>
                <div className="p-4 rounded-xl border border-border/60 bg-[#FAFBF9]">
                  <p className="text-muted text-[12px] font-medium">Organization</p>
                  <p className="mt-1 font-semibold text-ink text-[14px]">LINEAGE Defense Team</p>
                </div>
                <div className="p-4 rounded-xl border border-border/60 bg-[#FAFBF9]">
                  <p className="text-muted text-[12px] font-medium">Member Since</p>
                  <p className="mt-1 font-semibold text-ink text-[14px]">October 2024</p>
                </div>
              </div>
            </Panel>
          )}

          {activeCategory === "Security" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Security Settings" subtitle="Keep your account secure with strong credentials and two-factor authentication." />
              <div className="space-y-3">
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4"><p className="text-[13.5px] font-semibold text-ink">Authentication</p><p className="text-[12px] text-muted mt-1">Short-lived access tokens with refresh rotation are active. Login, upload, trace and Copilot requests are rate-limited.</p><div className="flex flex-wrap gap-2 mt-2"><StatusBadge tone="green">Protected</StatusBadge>{securityStatus && <StatusBadge tone="blue">{securityStatus.access_token_minutes}m access · {securityStatus.refresh_token_days}d refresh</StatusBadge>}</div></div>
                <MfaPanel />
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4"><p className="text-[13.5px] font-semibold text-ink">Distributed rate limiting</p><p className="text-[12px] text-muted mt-1">{securityStatus?.rate_limiting?.backend || "Loading…"}. Trace: {securityStatus?.trace_limit_per_minute ?? "—"}/min · Copilot: {securityStatus?.copilot_limit_per_minute ?? "—"}/min · Upload: {securityStatus?.upload_limit_per_minute ?? "—"}/min.</p><StatusBadge tone={securityStatus?.rate_limiting?.distributed ? "green" : "amber"}>{securityStatus?.rate_limiting?.distributed ? "Redis distributed" : "Single-process fallback"}</StatusBadge></div>
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4"><p className="text-[13.5px] font-semibold text-ink">Active session</p><p className="text-[12px] text-muted mt-1">This browser session is protected by the current access token.</p><StatusBadge tone="blue">Current device</StatusBadge></div>
              </div>
            </Panel>
          )}

          {activeCategory === "Detector" && <DetectorEvaluationPanel />}

          {activeCategory === "Privacy" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Privacy Preferences" subtitle="These preferences are stored locally on this device; they do not claim server-side consent where none exists." />
              <div className="divide-y divide-border/60">
                <ToggleRow title="Profile visibility" sub="Keep your investigator profile hidden from public search" initialOn={true} />
                <ToggleRow title="Usage analytics" sub="Share anonymous platform usage metrics to help improve LINEAGE" initialOn={false} />
                <ToggleRow title="Data sharing" sub="Allow investigation metadata cross-referencing across verified cases" initialOn={false} />
              </div>
            </Panel>
          )}

          {activeCategory === "Notifications" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Notification Preferences" subtitle="Control local interface notifications. External email/SMS delivery is not enabled in this demo." />
              <div className="divide-y divide-border/60">
                <ToggleRow title="Investigation updates" sub="Get notified on analysis progress and case changes" initialOn={true} />
                <ToggleRow title="System & Security alerts" sub="Important security alerts and system service updates" initialOn={true} />
                <ToggleRow title="Product updates" sub="New feature announcements and platform improvements" initialOn={false} />
              </div>
            </Panel>
          )}

          {activeCategory === "Data Management" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Data Management" subtitle="Export the active investigation bundle or delete its stored evidence." />
              
              <div className="p-5 rounded-2xl bg-soft/50 border border-border/60 space-y-2">
                <p className="text-[13px] font-semibold text-ink">Storage usage</p>
                <p className="text-[12px] text-muted">Server-side storage quota reporting is not exposed by this build, so LINEAGE does not display a fabricated usage number.</p>
                <StatusBadge tone="gray">Not reported by API</StatusBadge>
              </div>

              <div className="p-4 rounded-xl bg-amber/30 border border-[#E6D4A8] text-[12px] text-[#6F571F] leading-relaxed">Privacy note: uploaded media and investigation evidence are stored by the LINEAGE backend. For a real deployment, define a retention period, deletion workflow, and consent/privacy controls aligned with the DPDP Act 2023 and your legal review.</div>

              <div className="space-y-3 pt-2">
                <button disabled={!incidentId} onClick={async()=>{if(incidentId){await api.exportInvestigation(incidentId,"json");}}} className="w-full flex items-center justify-between border border-border rounded-xl p-4 text-[13px] font-medium text-ink hover:bg-soft transition group disabled:opacity-40">
                  <span className="flex items-center gap-3">
                    <Download size={18} className="text-brand" />
                    Export Active Investigation Data (.json)
                  </span>
                  <ChevronRight size={16} className="text-muted group-hover:translate-x-0.5 transition-transform" />
                </button>
                
                <button onClick={async()=>{ if(!incidentId) return; if(window.confirm("Delete the active investigation and its stored evidence? This cannot be undone.")){ await api.deleteIncident(incidentId); setIncidentId(null); window.location.assign("/investigations"); } }} disabled={!incidentId} className="w-full flex items-center justify-between border border-[#E9D4D0] text-[#8A4138] rounded-xl p-4 text-[13px] font-semibold hover:bg-[#FDF6F5] transition group disabled:opacity-40">
                  <span className="flex items-center gap-3">
                    <Trash2 size={18} />
                    Delete Active Investigation & Purge Evidence
                  </span>
                  <ChevronRight size={16} className="text-[#8A4138] group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>
            </Panel>
          )}

          {activeCategory === "Trust & Safety" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Trust, Safety & Legal Review" subtitle="Support tools are informational. LINEAGE does not make legal-admissibility or identity determinations." />
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4"><p className="text-[13px] font-semibold text-ink">Legal review status</p><p className="text-[12px] text-muted mt-1">Configured status only — it does not represent counsel approval.</p><StatusBadge tone="amber">Pending legal review</StatusBadge></div>
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4"><p className="text-[13px] font-semibold text-ink">Evidence certificate</p><p className="text-[12px] text-muted mt-1">Generate a BSA §63 certificate draft from the current evidence manifest.</p><button disabled={!incidentId} onClick={async()=>{if(incidentId){const x=await api.getBsaCertificate(incidentId); const blob=new Blob([JSON.stringify(x,null,2)],{type:"application/json"}); const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download=`lineage-bsa63-${incidentId.slice(0,8)}.json`; a.click(); URL.revokeObjectURL(a.href);}}} className="mt-3 rounded-lg bg-brand px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-40">Export draft</button></div>
                <div className="rounded-xl border border-border/60 bg-soft/40 p-4 sm:col-span-2"><p className="text-[13px] font-semibold text-ink">Victim support</p><p className="text-[12px] text-muted mt-1">Official cybercrime reporting resources and a safety note. LINEAGE does not automatically contact authorities or platforms.</p><button disabled={!incidentId} onClick={async()=>{if(incidentId){const x=await api.getVictimSupport(incidentId); window.open(x.resources?.[0]?.url,"_blank","noopener,noreferrer");}}} className="mt-3 rounded-lg border border-border px-3 py-2 text-[11px] font-semibold text-ink disabled:opacity-40">Open official support portal</button></div>
              </div>
              <div className="rounded-xl border border-border/60 p-4 text-[11px] leading-relaxed text-muted">BSA §63 certificate generation is a structured draft aid. A qualified lawyer or other appropriate person should complete statutory particulars and determine whether/how it should be used.</div>
            </Panel>
          )}

          {activeCategory === "Appearance" && (
            <Panel className="p-6 sm:p-8 space-y-6 w-full">
              <PanelHeader title="Appearance & Interface" subtitle="Customize theme and visual preferences." />
              
              <div className="space-y-4">
                <div className="flex items-center justify-between py-4 border-b border-border/60"><div><p className="text-[13.5px] font-semibold text-ink">Interface language</p><p className="text-[12px] text-muted mt-0.5">Choose English or Hindi for supported interface/report labels.</p></div><select defaultValue={localStorage.getItem("lineage_language") || "en"} onChange={e=>localStorage.setItem("lineage_language",e.target.value)} className="rounded-lg border border-border bg-card px-3 py-2 text-[12px]" aria-label="Interface language"><option value="en">English</option><option value="hi">हिन्दी</option></select></div>
                <div className="flex items-center justify-between py-4 border-b border-border/60">
                  <div>
                    <p className="text-[13.5px] font-semibold text-ink">Color Theme</p>
                    <p className="text-[12px] text-muted mt-0.5">Currently using {dark ? "Dark" : "Light"} mode</p>
                  </div>
                  <button
                    onClick={() => setDark(!dark)}
                    className="rounded-xl border border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink hover:bg-soft transition"
                  >
                    {dark ? "Switch to Light Mode" : "Switch to Dark Mode"}
                  </button>
                </div>

                <div className="flex items-center justify-between py-4 border-b border-border/60">
                  <div>
                    <p className="text-[13.5px] font-semibold text-ink">Brand Accent Color</p>
                    <p className="text-[12px] text-muted mt-0.5">LINEAGE Signature Green · #3E503C</p>
                  </div>
                  <span className="h-8 w-8 rounded-full bg-brand border-4 border-soft shadow-xs" />
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div></StaggerItem>
    </Stagger>
  );
}

function ToggleRow({ title, sub, initialOn = false }: { title: string; sub: string; initialOn?: boolean }) {
  const storageKey = `lineage_pref_${title.toLowerCase().replace(/[^a-z0-9]+/g,"_")}`;
  const [on, setOn] = useState(() => { const saved=localStorage.getItem(storageKey); return saved === null ? initialOn : saved === "1"; });
  useEffect(()=>{ localStorage.setItem(storageKey,on?"1":"0"); },[storageKey,on]);
  return (
    <div className="flex items-center justify-between gap-4 py-4 first:pt-0 last:pb-0">
      <div>
        <p className="text-[13.5px] font-semibold text-ink">{title}</p>
        <p className="text-[12px] text-muted mt-0.5">{sub}</p>
        <p className="text-[9.5px] text-faint mt-1">Saved on this device</p>
      </div>
      <button role="switch" aria-checked={on} aria-label={title}
        onClick={() => setOn(!on)}
        className={`w-11 h-6 rounded-full p-1 transition-colors shrink-0 ${on ? "bg-brand" : "bg-[#DCE1DC]"}`}
      >
        <span className={`block h-4 w-4 rounded-full bg-white transition-transform ${on ? "translate-x-5" : ""}`} />
      </button>
    </div>
  );
}
