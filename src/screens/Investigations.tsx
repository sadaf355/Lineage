import { useState } from "react";
import { motion } from "framer-motion";
import {
  FolderOpen,
  PieChart,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  Plus,
  Video,
  Image as ImageIcon,
  FileText,
  AudioLines,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { allInvestigationsList, InvestigationItem } from "../data/caseData";
import { StatusBadge } from "../components/ui";
import { ScreenKey } from "../components/Sidebar";

export default function Investigations({ onNavigate }: { onNavigate: (k: ScreenKey) => void }) {
  const [activeTab, setActiveTab] = useState<"all" | "in-progress" | "completed" | "needs-attention">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
  const [currentPage, setCurrentPage] = useState(1);

  // Filtering
  const filtered = allInvestigationsList.filter((item) => {
    // Filter tab check
    if (activeTab === "in-progress" && item.status !== "In Progress" && item.status !== "Evidence Building") return false;
    if (activeTab === "completed" && item.status !== "Completed") return false;
    if (activeTab === "needs-attention" && item.status !== "Needs Attention") return false;

    // Search query check
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = item.id.toLowerCase().includes(q);
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchDesc = item.description.toLowerCase().includes(q);
      if (!matchId && !matchTitle && !matchDesc) return false;
    }
    return true;
  });

  // Sorting
  const sorted = [...filtered].sort((a, b) => {
    if (sortOrder === "oldest") return a.id.localeCompare(b.id);
    return b.id.localeCompare(a.id);
  });

  // Pagination (8 items per page)
  const pageSize = 8;
  const totalPages = Math.ceil(sorted.length / pageSize) || 1;
  const paginated = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const getMediaIcon = (type: string) => {
    switch (type) {
      case "Video":
        return <Video size={15} className="text-muted" />;
      case "Image":
        return <ImageIcon size={15} className="text-muted" />;
      case "Document":
        return <FileText size={15} className="text-muted" />;
      case "Audio":
        return <AudioLines size={15} className="text-muted" />;
      default:
        return <FileText size={15} className="text-muted" />;
    }
  };

  const getStatusTone = (status: string) => {
    switch (status) {
      case "Evidence Building":
        return "amber";
      case "In Progress":
        return "blue";
      case "Completed":
        return "green";
      case "Needs Attention":
        return "red";
      default:
        return "gray";
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "bg-[#B96255]";
    if (score >= 50) return "bg-[#C79B42]";
    return "bg-brand";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-6 max-w-[1400px] mx-auto"
    >
      {/* Header Section */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 pb-2">
        <div>
          <p className="text-[11px] uppercase tracking-[.18em] text-brand font-semibold mb-1">INVESTIGATIONS</p>
          <h1 className="font-display text-3xl sm:text-4xl lg:text-[40px] tracking-[-.03em] font-semibold text-ink">
            All Investigations
          </h1>
          <p className="text-[13.5px] text-muted mt-2 max-w-2xl leading-relaxed">
            View, manage, and continue your investigations. Each case helps trace the truth behind digital content.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-5 shrink-0">
          <div className="hidden xl:block text-right pr-4 border-r border-border/70">
            <p className="font-display italic text-[14px] text-ink/80">“Investigations today, a safer tomorrow.”</p>
            <div className="h-0.5 w-12 bg-brand/40 ml-auto mt-1" />
          </div>

          <button
            onClick={() => onNavigate("new")}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand text-white px-5 py-3 text-[13px] font-semibold hover:bg-brandDark transition shadow-sm"
          >
            <Plus size={18} /> New Investigation
          </button>
        </div>
      </div>

      {/* 4 Summary Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-2xl p-5 shadow-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
            <FolderOpen size={22} />
          </div>
          <div>
            <p className="text-2xl font-bold text-ink leading-none">12</p>
            <p className="text-[12px] text-muted font-medium mt-1">Total Investigations</p>
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 shadow-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-blue/60 text-[#3B5A7D] flex items-center justify-center shrink-0">
            <PieChart size={22} />
          </div>
          <div>
            <p className="text-2xl font-bold text-ink leading-none">5</p>
            <p className="text-[12px] text-muted font-medium mt-1">In Progress</p>
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 shadow-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-soft text-brand flex items-center justify-center shrink-0">
            <CheckCircle2 size={22} />
          </div>
          <div>
            <p className="text-2xl font-bold text-ink leading-none">6</p>
            <p className="text-[12px] text-muted font-medium mt-1">Completed</p>
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 shadow-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-amber/70 text-[#78571A] flex items-center justify-center shrink-0">
            <AlertTriangle size={22} />
          </div>
          <div>
            <p className="text-2xl font-bold text-ink leading-none">1</p>
            <p className="text-[12px] text-muted font-medium mt-1">Requires Attention</p>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-2">
        {/* Left Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1 lg:pb-0">
          {[
            ["all", "All (12)"],
            ["in-progress", "In Progress (5)"],
            ["completed", "Completed (6)"],
            ["needs-attention", "Needs Attention (1)"],
          ].map(([key, label]) => {
            const isActive = activeTab === key;
            return (
              <button
                key={key}
                onClick={() => {
                  setActiveTab(key as any);
                  setCurrentPage(1);
                }}
                className={`px-4 py-2 rounded-xl text-[12.5px] font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-[#3E503C] text-white shadow-xs font-semibold"
                    : "bg-card border border-border text-muted hover:text-ink hover:bg-soft/40"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Right Search & Controls */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] sm:w-[240px]">
            <Search size={15} className="absolute left-3.5 top-3 text-faint" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search cases..."
              className="w-full h-10 rounded-xl border border-border bg-card pl-9 pr-3 text-[12.5px] outline-none focus:ring-2 focus:ring-brand/20 transition"
            />
          </div>

          <button className="h-10 px-4 rounded-xl border border-border bg-card text-[12.5px] font-medium text-ink hover:bg-soft transition flex items-center gap-2">
            <Filter size={14} /> Filter
          </button>

          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as any)}
            className="h-10 px-3 rounded-xl border border-border bg-card text-[12.5px] font-medium text-ink outline-none cursor-pointer"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="bg-card border border-border rounded-2xl shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[950px] border-collapse">
            <thead>
              <tr className="bg-[#FAFBF9] border-b border-border text-[11px] uppercase tracking-wide text-faint font-semibold">
                <th className="py-3.5 px-4">Case ID</th>
                <th className="py-3.5 px-4">Title / Description</th>
                <th className="py-3.5 px-4">Media Type</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Manipulation Likelihood</th>
                <th className="py-3.5 px-4">Last Updated</th>
                <th className="py-3.5 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {paginated.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => onNavigate("overview")}
                  className="hover:bg-soft/40 cursor-pointer transition text-[13px]"
                >
                  {/* Case ID with Avatar */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-lg bg-brandDark/90 text-white flex items-center justify-center font-display font-semibold shrink-0 shadow-xs">
                        {item.title.charAt(0)}
                      </div>
                      <span className="font-mono text-[12px] font-medium text-muted">{item.id}</span>
                    </div>
                  </td>

                  {/* Title & Description */}
                  <td className="py-4 px-4">
                    <p className="font-semibold text-ink text-[13.5px]">{item.title}</p>
                    <p className="text-[11.5px] text-muted mt-0.5">{item.description}</p>
                  </td>

                  {/* Media Type */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-2 text-[12.5px] text-ink font-medium">
                      {getMediaIcon(item.mediaType)}
                      <span>{item.mediaType}</span>
                    </div>
                  </td>

                  {/* Status Badge */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <StatusBadge tone={getStatusTone(item.status)}>{item.status}</StatusBadge>
                  </td>

                  {/* Manipulation Likelihood */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-3 w-40">
                      <b className="text-ink font-semibold text-[13px] shrink-0 w-9">{item.score}%</b>
                      <div className="h-2 bg-[#EEF1ED] rounded-full flex-1 overflow-hidden">
                        <div
                          className={`h-full ${getScoreColor(item.score)} rounded-full transition-all`}
                          style={{ width: `${item.score}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Last Updated */}
                  <td className="py-4 px-4 whitespace-nowrap">
                    <p className="text-[12.5px] text-ink font-medium">{item.updatedAgo}</p>
                    <p className="text-[11px] text-muted">{item.updatedDate}</p>
                  </td>

                  {/* Actions */}
                  <td className="py-4 px-4 text-center whitespace-nowrap">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigate("overview");
                      }}
                      className="h-8 w-8 rounded-lg hover:bg-soft text-muted hover:text-ink flex items-center justify-center mx-auto transition"
                    >
                      <MoreVertical size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footer Pagination */}
        <div className="p-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-[12px] text-muted">
          <span>
            Showing {Math.min(1, sorted.length)}–{Math.min(currentPage * pageSize, sorted.length)} of {sorted.length} investigations
          </span>

          <div className="flex items-center gap-1.5 self-end sm:self-auto">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="h-8 w-8 rounded-lg border border-border hover:bg-soft disabled:opacity-40 flex items-center justify-center transition"
            >
              <ChevronLeft size={16} />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setCurrentPage(p)}
                className={`h-8 w-8 rounded-lg text-[12px] font-semibold transition ${
                  currentPage === p ? "bg-[#3E503C] text-white" : "border border-border hover:bg-soft text-ink"
                }`}
              >
                {p}
              </button>
            ))}

            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="h-8 w-8 rounded-lg border border-border hover:bg-soft disabled:opacity-40 flex items-center justify-center transition"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
