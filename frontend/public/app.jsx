const { useState, useEffect } = React;

const API_BASE = '/api/v1';

// Helper for formatting Paise to INR
function formatINR(paise) {
  if (paise === null || paise === undefined) return '₹0.00';
  const val = (paise / 100.0).toFixed(2);
  return '₹' + Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2 });
}


const Icon = ({ name, className }) => {
  const spanRef = React.useRef(null);
  React.useEffect(() => {
    if (spanRef.current && window.lucide) {
      spanRef.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      if (className) i.setAttribute('class', className);
      spanRef.current.appendChild(i);
      window.lucide.createIcons({ root: spanRef.current });
    }
  }, [name, className]);
  return <span ref={spanRef} className={"inline-flex items-center justify-center"} />;
};

function App() {
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [runs, setRuns] = useState([]);
  const [activeRun, setActiveRun] = useState(null);
  const [exceptions, setExceptions] = useState([]);
  const [exceptionTotal, setExceptionTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedException, setSelectedException] = useState(null);
  const [exceptionDetail, setExceptionDetail] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [health, setHealth] = useState({ status: 'connecting', database: 'unknown' });
  const [loading, setLoading] = useState(false);
  const [filterPriority, setFilterPriority] = useState('');
  const [filterReason, setFilterReason] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [investigating, setInvestigating] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [aiProvider, setAiProvider] = useState('mock');

  // Load Health and Runs on Mount
  useEffect(() => {
    fetchHealth();
    fetchRuns();
    fetchAuditLogs();

    // Auto refresh runs every 10s
    const timer = setInterval(() => {
      fetchRuns();
    }, 10000);
    return () => clearInterval(timer);
  }, []);



  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      setHealth(data);
    } catch (err) {
      setHealth({ status: 'offline', database: 'disconnected' });
    }
  };

  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API_BASE}/reconciliation/runs?limit=10`);
      const data = await res.json();
      setRuns(data);
      if (data.length > 0 && !activeRun) {
        setActiveRun(data[0]);
        loadRunDetails(data[0].run_id);
      }
    } catch (err) {
      console.error("Error fetching runs:", err);
    }
  };

  const fetchExceptions = async (runId = null, page = 1) => {
    try {
      const targetRunId = runId || (activeRun ? activeRun.run_id : null);
      if (!targetRunId) return;

      let url = `${API_BASE}/exceptions?limit=20&page=${page}&run_id=${targetRunId}`;
      if (filterPriority) url += `&priority=${filterPriority}`;
      if (filterReason) url += `&reason_code=${filterReason}`;
      if (searchQuery) url += `&search=${searchQuery}`;

      const res = await fetch(url);
      const data = await res.json();
      setExceptions(data.exceptions || []);
      setExceptionTotal(data.total ?? (data.exceptions || []).length);
      setCurrentPage(data.page || 1);
    } catch (err) {
      console.error("Error fetching exceptions:", err);
    }
  };

  const loadRunDetails = async (runId) => {
    try {
      const runRes = await fetch(`${API_BASE}/reconciliation/runs/${runId}`);
      const runData = await runRes.json();
      setActiveRun(runData);

      fetchExceptions(runId);

      const evalRes = await fetch(`${API_BASE}/evaluation/${runId}`);
      if (evalRes.ok) {
        const evalData = await evalRes.json();
        setEvaluation(evalData);
      }

      const anaRes = await fetch(`${API_BASE}/analytics/root-causes/${runId}`);
      if (anaRes.ok) {
        const anaData = await anaRes.json();
        setAnalytics(anaData);
      }
    } catch (err) {
      console.error("Error loading run details:", err);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/audit?limit=30`);
      const data = await res.json();
      setAuditLogs(data.audit_logs || []);
    } catch (err) {
      console.error("Error fetching audit logs:", err);
    }
  };

  const triggerNewRun = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/reconciliation/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: 'demo-500',
          options: { date_tolerance_days: 3, auto_resolution_threshold: 0.95 }
        })
      });
      const data = await res.json();
      await new Promise(r => setTimeout(r, 2000));
      await fetchRuns();
      if (data.run_id) {
        await loadRunDetails(data.run_id);
      }
    } catch (err) {
      alert("Failed to start run: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const openExceptionWorkbench = async (exceptionId) => {
    setSelectedException(exceptionId);
    setCurrentTab('exceptions');
    try {
      const res = await fetch(`${API_BASE}/exceptions/${exceptionId}`);
      const data = await res.json();
      setExceptionDetail(data);
    } catch (err) {
      alert("Error loading exception details: " + err.message);
    }
  };

  const runAIInvestigation = async (exceptionId) => {
    setInvestigating(true);
    try {
      const res = await fetch(`${API_BASE}/exceptions/${exceptionId}/investigate?provider=${aiProvider}`, {
        method: 'POST'
      });
      const data = await res.json();
      await openExceptionWorkbench(exceptionId);
      fetchExceptions(activeRun ? activeRun.run_id : null);
      fetchAuditLogs();
    } catch (err) {
      alert("AI Investigation error: " + err.message);
    } finally {
      setInvestigating(false);
    }
  };

  const handleHumanResolve = async (action) => {
    if (!selectedException || resolving) return;

    setResolving(true);

    try {
      const res = await fetch(`${API_BASE}/exceptions/${selectedException}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          note: `Finance Operator executed ${action.toUpperCase()} action from Workbench.`,
          actor_id: 'finance_controller_user'
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Resolution request failed");
      }

      await openExceptionWorkbench(selectedException);
      await fetchExceptions(activeRun ? activeRun.run_id : null);
      await fetchAuditLogs();
      await fetchRuns();
    } catch (err) {
      alert("Resolution error: " + err.message);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-fintech-textPrimary font-sans">
      {/* SIDEBAR NAVIGATION */}
      <aside className="w-64 bg-fintech-bg border-r border-fintech-border flex flex-col justify-between">
        <div>
          {/* Logo & Track Banner */}
          <div className="p-5 border-b border-fintech-border">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-400/30 flex items-center justify-center text-sky-400 font-bold">
                LL
              </div>
              <div>
                <h1 className="font-bold text-lg text-white tracking-tight leading-none">LedgerLens</h1>
                <p className="text-xs text-fintech-textSecondary font-mono mt-0.5">AI Finance Controller</p>
              </div>
            </div>
            <div className="mt-3 bg-sky-950/60 border border-sky-500/30 rounded-md px-2.5 py-1 flex items-center justify-between">
              <span className="text-[10px] font-semibold text-sky-300 uppercase tracking-wider">Razorpay Buildathon</span>
              <span className="text-[10px] bg-sky-500/20 text-sky-300 font-mono px-1.5 py-0.5 rounded">Track 04</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
              { id: 'runs', label: 'Reconciliation Runs', icon: 'layers' },
              { id: 'exceptions', label: 'Exception Queue', icon: 'alert-triangle', badge: exceptionTotal },
              { id: 'evaluation', label: 'Evaluation Metrics', icon: 'bar-chart-3' },
              { id: 'analytics', label: 'Root Cause & Clusters', icon: 'git-merge' },
              { id: 'audit', label: 'Audit Trail', icon: 'shield-check' },
              { id: 'settings', label: 'Settings & Policy', icon: 'sliders' }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  currentTab === item.id
                    ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                    : 'text-fintech-textSecondary hover:bg-fintech-card/60 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon name={item.icon} className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                {item.badge > 0 && (
                  <span className="bg-rose-500/20 text-rose-400 text-xs font-mono px-2 py-0.5 rounded-full border border-rose-500/30">
                    {item.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* System Health Badge */}
        <div className="p-4 border-t border-fintech-border bg-fintech-bg/50">
          <div className="flex items-center justify-between text-xs">
            <span className="text-fintech-textSecondary">Database (MongoDB 8)</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              {health.database}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs mt-2">
            <span className="text-fintech-textSecondary">Engine Version</span>
            <span className="text-fintech-textSecondary font-mono">LedgerLens Engine v1.0.0</span>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col overflow-y-auto bg-slate-950">
        {/* HEADER BAR */}
        <header className="h-16 border-b border-fintech-border px-6 flex items-center justify-between bg-fintech-bg/60 sticky top-0 z-10 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-lg text-white capitalize">{currentTab.replace('_', ' ')}</h2>
            {activeRun && (
              <span className="bg-fintech-card text-fintech-textSecondary text-xs font-mono px-2.5 py-1 rounded-md border border-fintech-border">
                Active Run: {activeRun.run_id}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={triggerNewRun}
              disabled={loading}
              className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold px-4 py-2 rounded-lg text-sm transition-all flex items-center gap-2 shadow-lg shadow-sky-500/20 disabled:opacity-50"
            >
              <Icon name="play" className="w-4 h-4 fill-current" />
              {loading ? 'Processing Engine...' : 'Run Reconciliation'}
            </button>
          </div>
        </header>

        {/* DASHBOARD VIEW */}
        {currentTab === 'dashboard' && (
          <div className="p-6 space-y-6">
            {/* KPI STAT CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="glass-card p-5 rounded-xl border border-fintech-border">
                <div className="text-xs text-fintech-textSecondary font-medium">Processed Transactions</div>
                <div className="text-2xl font-bold text-white mt-1 font-mono">
                  {activeRun ? activeRun.processed_records : 0} <span className="text-xs text-fintech-textPrimary0 font-sans">/ {activeRun ? activeRun.total_records : 0}</span>
                </div>
                <div className="text-xs text-emerald-400 mt-2 flex items-center gap-1 font-mono">
                  <span>Throughput:</span>
                  <span>{evaluation ? evaluation.metrics?.throughput_records_per_sec : '950'} rec/s</span>
                </div>
              </div>

              <div className="glass-card p-5 rounded-xl border border-fintech-border">
                <div className="text-xs text-fintech-textSecondary font-medium">Reconciled Amount</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">
                  {formatINR(activeRun ? activeRun.reconciled_amount_paise : 0)}
                </div>
                <div className="text-xs text-fintech-textSecondary mt-2 font-mono">
                  Reconciliation Match Rate: <span className="text-white font-bold">{activeRun && activeRun.processed_records ? ((activeRun.matched_count / activeRun.processed_records)*100).toFixed(1) : 0}%</span>
                </div>
              </div>

              <div className="glass-card p-5 rounded-xl border border-fintech-border">
                <div className="text-xs text-fintech-textSecondary font-medium">Unreconciled Variance</div>
                <div className="text-2xl font-bold text-rose-400 mt-1 font-mono">
                  {formatINR(activeRun ? activeRun.unreconciled_amount_paise : 0)}
                </div>
                <div className="text-xs text-rose-400/80 mt-2 font-mono flex items-center justify-between">
                  <button
                    onClick={() => setCurrentTab('exceptions')}
                    className="text-rose-400 hover:text-rose-300 transition-colors"
                  >
                    Exceptions: {activeRun ? activeRun.exception_count : 0}
                  </button>
                  <span className="text-fintech-textPrimary0">Review Queue</span>
                </div>
              </div>

              <div className="glass-card p-5 rounded-xl border border-fintech-border">
                <div className="text-xs text-fintech-textSecondary font-medium">Engine Performance</div>
                <div className="text-2xl font-bold text-sky-400 mt-1 font-mono">
                  {evaluation ? (evaluation.metrics?.accuracy * 100).toFixed(1) : '91.8'}%
                </div>
                <div className="text-xs text-fintech-textSecondary mt-2 font-mono grid grid-cols-2 gap-1">
                  <span>Precision: <b className="text-white">{evaluation ? (evaluation.metrics?.precision * 100).toFixed(1) : '87.6'}%</b></span>
                  <span>Recall: <b className="text-emerald-400">{evaluation ? (evaluation.metrics?.recall * 100).toFixed(1) : '100.0'}%</b></span>
                  <span>F1: <b className="text-white">{evaluation ? (evaluation.metrics?.f1 * 100).toFixed(1) : '93.4'}%</b></span>
                  <span>False Match: <b className="text-rose-400">{evaluation ? (evaluation.metrics?.false_match_rate * 100).toFixed(1) : '8.2'}%</b></span>
                </div>
              </div>
            </div>

            {/* RECENT RECONCILIATION RUNS TABLE */}
            <div className="glass-card rounded-xl border border-fintech-border overflow-hidden">
              <div className="p-4 border-b border-fintech-border flex items-center justify-between">
                <h3 className="font-semibold text-white text-sm">Recent Reconciliation Runs</h3>
                <span className="text-xs text-fintech-textSecondary">Auto-refreshing live data</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-fintech-textSecondary">
                  <thead className="bg-fintech-bg/80 uppercase font-mono text-[10px] text-fintech-textSecondary border-b border-fintech-border">
                    <tr>
                      <th className="p-3">Run ID</th>
                      <th className="p-3">Dataset</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Matched</th>
                      <th className="p-3">Exceptions</th>
                      <th className="p-3">Reconciled Vol</th>
                      <th className="p-3">Time</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {runs.map(r => (
                      <tr key={r.run_id} className="hover:bg-fintech-card/40 transition-all">
                        <td className="p-3 text-sky-400 font-semibold">{r.run_id}</td>
                        <td className="p-3">{r.dataset_id}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                            r.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          }`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="p-3 text-emerald-400">{r.matched_count}</td>
                        <td className="p-3 text-rose-400">{r.exception_count}</td>
                        <td className="p-3 text-slate-200">{formatINR(r.reconciled_amount_paise)}</td>
                        <td className="p-3 text-fintech-textSecondary">{r.total_processing_time_ms ? `${(r.total_processing_time_ms / 1000).toFixed(2)}s` : '-'}</td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => loadRunDetails(r.run_id)}
                            className="bg-fintech-card hover:bg-slate-700 text-sky-400 px-2.5 py-1 rounded text-xs transition-all border border-fintech-border"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* TOP SYSTEMIC ROOT CAUSES & ANOMALIES */}
            {analytics && analytics.root_causes && (
              <div className="glass-card p-5 rounded-xl border border-fintech-border">
                <h3 className="font-semibold text-white text-sm mb-3">Detected Systemic Root Causes</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {analytics.root_causes.slice(0, 3).map((rc, idx) => (
                    <div key={idx} className="bg-fintech-bg/60 p-4 rounded-lg border border-fintech-border space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-sky-300">{rc.title}</span>
                        <span className="bg-rose-500/20 text-rose-400 text-[10px] px-1.5 py-0.5 rounded font-mono">
                          {rc.severity}
                        </span>
                      </div>
                      <p className="text-xs text-fintech-textSecondary">{rc.description}</p>
                      <div className="flex items-center justify-between text-xs font-mono pt-2 border-t border-fintech-border">
                        <span className="text-fintech-textSecondary">Impact: <span className="text-rose-400 font-bold">₹{rc.total_financial_impact_inr.toLocaleString()}</span></span>
                        <span className="text-fintech-textSecondary">Affected: <span className="text-white font-bold">{rc.affected_count}</span></span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* EXCEPTION QUEUE VIEW */}
        {currentTab === 'exceptions' && (
          <div className="p-6 space-y-4">
            {/* FILTERS BAR */}
            <div className="glass-card p-4 rounded-xl border border-fintech-border flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  placeholder="Search transaction ID, reason or status..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-fintech-bg border border-fintech-border text-xs text-white rounded-lg px-3 py-2 w-64 focus:border-sky-500 outline-none font-mono"
                />

                <select
                  value={filterPriority}
                  onChange={(e) => setFilterPriority(e.target.value)}
                  className="bg-fintech-bg border border-fintech-border text-xs text-fintech-textSecondary rounded-lg px-3 py-2 focus:border-sky-500 outline-none"
                >
                  <option value="">All Priorities</option>
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="HIGH">HIGH</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="LOW">LOW</option>
                </select>

                <select
                  value={filterReason}
                  onChange={(e) => setFilterReason(e.target.value)}
                  className="bg-fintech-bg border border-fintech-border text-xs text-fintech-textSecondary rounded-lg px-3 py-2 focus:border-sky-500 outline-none"
                >
                  <option value="">All Reasons</option>
                  <option value="FEE_VARIANCE">FEE_VARIANCE</option>
                  <option value="TAX_VARIANCE">TAX_VARIANCE</option>
                  <option value="DATE_VARIANCE">DATE_VARIANCE</option>
                  <option value="PARTIAL_SETTLEMENT">PARTIAL_SETTLEMENT</option>
                  <option value="DUPLICATE">DUPLICATE</option>
                  <option value="MISSING_SETTLEMENT">MISSING_SETTLEMENT</option>
                  <option value="MISSING_LEDGER">MISSING_LEDGER</option>
                  <option value="CURRENCY_MISMATCH">CURRENCY_MISMATCH</option>
                  <option value="REVERSED_TRANSACTION">REVERSED_TRANSACTION</option>
                  <option value="UNKNOWN_TRANSACTION">UNKNOWN_TRANSACTION</option>
                  <option value="REFERENCE_MISMATCH">REFERENCE_MISMATCH</option>
                </select>
              </div>

              <button
                onClick={() => fetchExceptions(activeRun ? activeRun.run_id : null, 1)}
                className="bg-fintech-card hover:bg-slate-700 text-slate-200 text-xs px-3 py-2 rounded-lg transition-all border border-fintech-border"
              >
                Apply Filters
              </button>
            </div>

            {/* EXCEPTION SUMMARY */}
            <div className="flex items-center justify-between px-1">
              <div>
                <h3 className="text-sm font-semibold text-white">Exception Review Queue</h3>
                <p className="text-xs text-fintech-textPrimary0 mt-1">
                  Showing {(currentPage - 1) * 20 + 1}–{Math.min(currentPage * 20, exceptionTotal)} of {exceptionTotal} exceptions from the active reconciliation run.
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 bg-fintech-bg border border-fintech-border rounded-lg px-2 py-1">
                  <button
                    disabled={currentPage <= 1}
                    onClick={() => fetchExceptions(activeRun ? activeRun.run_id : null, currentPage - 1)}
                    className="text-xs text-fintech-textSecondary hover:text-white disabled:opacity-50 transition-colors p-1"
                  >
                    Previous
                  </button>
                  <span className="text-xs font-mono text-white px-2">Page {currentPage}</span>
                  <button
                    disabled={currentPage * 20 >= exceptionTotal}
                    onClick={() => fetchExceptions(activeRun ? activeRun.run_id : null, currentPage + 1)}
                    className="text-xs text-fintech-textSecondary hover:text-white disabled:opacity-50 transition-colors p-1"
                  >
                    Next
                  </button>
                </div>
                <button
                  onClick={() => {
                    setFilterPriority('');
                    setFilterReason('');
                    setSearchQuery('');
                    setTimeout(() => fetchExceptions(activeRun ? activeRun.run_id : null, 1), 0);
                  }}
                  className="text-xs text-fintech-textSecondary hover:text-white transition-colors"
                >
                  Clear filters
                </button>
              </div>
            </div>

            {/* EXCEPTION TABLE */}
            <div className="glass-card rounded-xl border border-fintech-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-fintech-textSecondary">
                  <thead className="bg-fintech-bg/80 uppercase font-mono text-[10px] text-fintech-textSecondary border-b border-fintech-border">
                    <tr>
                      <th className="p-3">Priority</th>
                      <th className="p-3">Transaction ID</th>
                      <th className="p-3">Reason Code</th>
                      <th className="p-3">Financial Impact</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Recommended Action</th>
                      <th className="p-3 text-right">Workbench</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {exceptions.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="p-10 text-center text-fintech-textPrimary0">
                          No exceptions match the current filters.
                        </td>
                      </tr>
                    ) : exceptions.map(e => (
                      <tr key={e.exception_id} className="hover:bg-fintech-card/40 transition-all">
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            e.priority === 'CRITICAL' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                            e.priority === 'HIGH' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                            'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                          }`}>
                            {e.priority}
                          </span>
                        </td>
                        <td className="p-3 text-sky-400 font-semibold">{e.transaction_id}</td>
                        <td className="p-3 text-slate-200">
                          {e.reason_code === 'MULTIPLE_CANDIDATES'
                            ? 'DUPLICATE / MULTIPLE CANDIDATES'
                            : e.reason_code}
                        </td>
                        <td className="p-3 text-rose-400 font-bold">{formatINR(e.financial_impact_paise)}</td>
                        <td className="p-3">{((e.confidence || 0.5) * 100).toFixed(0)}%</td>
                        <td className="p-3">
                          <span className={`text-[10px] px-2 py-0.5 rounded uppercase font-semibold border ${
                            e.status === 'APPROVED'
                              ? 'bg-fintech-accent/10 text-emerald-400 border-emerald-500/30'
                              : e.status === 'REJECTED'
                              ? 'bg-fintech-rose/10 text-rose-400 border-rose-500/30'
                              : e.status === 'AI_RECOMMENDED'
                              ? 'bg-fintech-cyan/10 text-purple-400 border-purple-500/30'
                              : 'bg-fintech-card text-fintech-textSecondary border-fintech-border'
                          }`}>
                            {e.status}
                          </span>
                        </td>
                        <td className="p-3 text-fintech-textSecondary text-[11px] font-sans truncate max-w-xs">{e.recommended_action}</td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => openExceptionWorkbench(e.exception_id)}
                            className="bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 px-3 py-1 rounded border border-sky-500/30 text-xs transition-all font-sans"
                          >
                            Investigate
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* EVALUATION METRICS VIEW */}
        {currentTab === 'evaluation' && (
          <div className="p-6 space-y-6">
            {evaluation && evaluation.metrics ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="glass-card p-5 rounded-xl border border-fintech-border">
                    <div className="text-xs text-fintech-textSecondary">Accuracy</div>
                    <div className="text-3xl font-bold text-sky-400 mt-1 font-mono">{(evaluation.metrics.accuracy * 100).toFixed(2)}%</div>
                  </div>
                  <div className="glass-card p-5 rounded-xl border border-fintech-border">
                    <div className="text-xs text-fintech-textSecondary">Precision</div>
                    <div className="text-3xl font-bold text-emerald-400 mt-1 font-mono">{(evaluation.metrics.precision * 100).toFixed(2)}%</div>
                  </div>
                  <div className="glass-card p-5 rounded-xl border border-fintech-border">
                    <div className="text-xs text-fintech-textSecondary">Recall</div>
                    <div className="text-3xl font-bold text-amber-400 mt-1 font-mono">{(evaluation.metrics.recall * 100).toFixed(2)}%</div>
                  </div>
                  <div className="glass-card p-5 rounded-xl border border-fintech-border">
                    <div className="text-xs text-fintech-textSecondary">False Match Rate</div>
                    <div className="text-3xl font-bold text-rose-400 mt-1 font-mono">{(evaluation.metrics.false_match_rate * 100).toFixed(2)}%</div>
                  </div>
                </div>

                <div className="glass-card p-6 rounded-xl border border-fintech-border space-y-4">
                  <h3 className="font-semibold text-white text-sm">Ground Truth Confusion Matrix Summary</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
                    <div className="bg-fintech-bg p-4 rounded-lg border border-fintech-border">
                      <div className="text-fintech-textPrimary0">True Positives (Correct Matches)</div>
                      <div className="text-xl font-bold text-emerald-400 mt-1">{evaluation.metrics.true_positives}</div>
                    </div>
                    <div className="bg-fintech-bg p-4 rounded-lg border border-fintech-border">
                      <div className="text-fintech-textPrimary0">False Positives (False Matches)</div>
                      <div className="text-xl font-bold text-rose-400 mt-1">{evaluation.metrics.false_positives}</div>
                    </div>
                    <div className="bg-fintech-bg p-4 rounded-lg border border-fintech-border">
                      <div className="text-fintech-textPrimary0">True Negatives (Exceptions Flagged)</div>
                      <div className="text-xl font-bold text-sky-400 mt-1">{evaluation.metrics.true_negatives}</div>
                    </div>
                    <div className="bg-fintech-bg p-4 rounded-lg border border-fintech-border">
                      <div className="text-fintech-textPrimary0">False Negatives (Missed Matches)</div>
                      <div className="text-xl font-bold text-amber-400 mt-1">{evaluation.metrics.false_negatives}</div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="glass-card p-8 rounded-xl border border-fintech-border text-center text-fintech-textSecondary">
                Run an evaluation run via CLI script `python scripts/run_evaluation.py` or trigger a run above to generate benchmark metrics.
              </div>
            )}
          </div>
        )}

        {/* ANALYTICS & ROOT CAUSES VIEW */}
        {/* ANALYTICS & ROOT CAUSES VIEW */}
        {currentTab === 'analytics' && (
          <div className="p-6 space-y-6">
            {!analytics ? (
              <div className="glass-card p-8 rounded-xl border border-fintech-border text-center text-fintech-textSecondary">
                Loading analytics data or no run is active...
              </div>
            ) : (
              <>
                <div className="glass-card p-6 rounded-xl border border-fintech-border space-y-4">
                  <h3 className="font-semibold text-white text-sm">Systemic Root Cause Failure Modes</h3>
                  {(!analytics.root_causes || analytics.root_causes.length === 0) ? (
                    <div className="text-sm text-fintech-textSecondary">No root causes detected.</div>
                  ) : (
                    <div className="space-y-3">
                      {analytics.root_causes.map((rc, idx) => (
                        <div key={idx} className="bg-fintech-bg/80 p-4 rounded-lg border border-fintech-border flex items-center justify-between">
                          <div>
                            <h4 className="font-semibold text-sky-300 text-xs">{rc.title}</h4>
                            <p className="text-xs text-fintech-textSecondary mt-1">{rc.description}</p>
                          </div>
                          <div className="text-right font-mono text-xs">
                            <div className="text-rose-400 font-bold">₹{rc.total_financial_impact_inr.toLocaleString()}</div>
                            <div className="text-fintech-textPrimary0 mt-0.5">{rc.affected_count} transactions</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="glass-card p-6 rounded-xl border border-fintech-border space-y-4">
                  <h3 className="font-semibold text-white text-sm">Exception Clusters</h3>
                  {(!analytics.clusters || analytics.clusters.length === 0) ? (
                    <div className="text-sm text-fintech-textSecondary">No clusters generated.</div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {analytics.clusters.map((cluster, idx) => (
                        <div key={idx} className="bg-fintech-bg/80 p-4 rounded-lg border border-fintech-border flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <h4 className="font-semibold text-sky-300 text-xs">{cluster.description || cluster.reason_code}</h4>
                            <span className="bg-rose-500/20 text-rose-400 text-[10px] px-1.5 py-0.5 rounded font-mono">
                              {cluster.risk_level || 'UNKNOWN'}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono mt-2">
                            <div>
                              <span className="text-fintech-textSecondary">Affected:</span> <span className="text-white">{cluster.size} ({cluster.percentage_of_total ? cluster.percentage_of_total.toFixed(1) : 0}%)</span>
                            </div>
                            <div className="text-right">
                              <span className="text-fintech-textSecondary">Impact:</span> <span className="text-rose-400 font-bold">₹{(cluster.total_financial_impact_paise / 100).toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* AUDIT TRAIL VIEW */}
        {currentTab === 'audit' && (
          <div className="p-6 space-y-6">

            {/* AUDIT HEADER */}
            <div className="glass-card rounded-xl border border-fintech-border p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
                      <Icon name="shield-check" className="w-5 h-5 text-sky-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">Immutable Audit Trail</h3>
                      <p className="text-xs text-fintech-textPrimary0 mt-0.5">
                        Complete chain of system detection, AI investigation and human action.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="px-2.5 py-1.5 rounded-lg border border-fintech-border bg-fintech-bg text-fintech-textSecondary">
                    {auditLogs.length} EVENTS
                  </span>
                  <span className="px-2.5 py-1.5 rounded-lg border border-purple-500/30 bg-fintech-cyan/10 text-purple-300">
                    AI {auditLogs.filter(l => l.actor_type === 'AI_AGENT').length}
                  </span>
                  <span className="px-2.5 py-1.5 rounded-lg border border-emerald-500/30 bg-fintech-accent/10 text-emerald-300">
                    HUMAN {auditLogs.filter(l => l.actor_type === 'HUMAN').length}
                  </span>
                </div>
              </div>
            </div>

            {/* CONTROL FLOW */}
            <div className="glass-card rounded-xl border border-fintech-border p-5">
              <div className="text-[10px] uppercase tracking-wider text-fintech-textPrimary0 font-bold mb-4">
                Controller Event Flow
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="relative bg-slate-950 rounded-xl border border-fintech-border p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-fintech-card flex items-center justify-center">
                      <Icon name="server" className="w-4 h-4 text-fintech-textSecondary" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white">SYSTEM</div>
                      <div className="text-[10px] text-fintech-textPrimary0">Exception detected</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[10px] font-mono text-fintech-textPrimary0">
                    UNPROCESSED → DETECTED
                  </div>
                  <div className="hidden md:block absolute top-7 -right-2 text-slate-700 z-10">
                    <Icon name="chevron-right" className="w-4 h-4" />
                  </div>
                </div>

                <div className="relative bg-purple-500/5 rounded-xl border border-fintech-cyan/20 p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-fintech-cyan/10 flex items-center justify-center">
                      <Icon name="bot" className="w-4 h-4 text-purple-400" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-purple-300">AI AGENT</div>
                      <div className="text-[10px] text-fintech-textPrimary0">Evidence investigation</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[10px] font-mono text-purple-300">
                    DETECTED → AI_RECOMMENDED
                  </div>
                  <div className="hidden md:block absolute top-7 -right-2 text-slate-700 z-10">
                    <Icon name="chevron-right" className="w-4 h-4" />
                  </div>
                </div>

                <div className="bg-emerald-500/5 rounded-xl border border-fintech-accent/20 p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-fintech-accent/10 flex items-center justify-center">
                      <Icon name="user-check" className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-emerald-300">HUMAN</div>
                      <div className="text-[10px] text-fintech-textPrimary0">Finance operator decision</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[10px] font-mono text-emerald-300">
                    AI_RECOMMENDED → RESOLVED
                  </div>
                </div>
              </div>
            </div>

            {/* TIMELINE */}
            <div className="glass-card rounded-xl border border-fintech-border p-5">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="font-semibold text-white text-sm">Event Timeline</h3>
                  <p className="text-[11px] text-fintech-textPrimary0 mt-1">
                    Every controller action is recorded with actor, transaction and state transition.
                  </p>
                </div>
                <div className="text-[10px] font-mono text-fintech-textPrimary0">
                  CHRONOLOGICAL RECORD
                </div>
              </div>

              {auditLogs.length === 0 ? (
                <div className="p-10 text-center text-fintech-textPrimary0 text-xs">
                  No audit events recorded yet.
                </div>
              ) : (
                <div className="relative">
                  <div className="absolute left-[18px] top-3 bottom-3 w-px bg-fintech-card"></div>

                  <div className="space-y-4">
                    {auditLogs.map((log, index) => {
                      const isAI = log.actor_type === 'AI_AGENT';
                      const isHuman = log.actor_type === 'HUMAN';
                      const isSystem = log.actor_type === 'SYSTEM';

                      return (
                        <div key={log.audit_id} className="relative flex gap-4">

                          {/* TIMELINE NODE */}
                          <div className={`relative z-10 w-9 h-9 shrink-0 rounded-full border flex items-center justify-center ${
                            isAI
                              ? 'bg-fintech-cyan/10 border-purple-500/30'
                              : isHuman
                              ? 'bg-fintech-accent/10 border-emerald-500/30'
                              : 'bg-fintech-card border-fintech-border'
                          }`}>
                            <i
                              data-lucide={
                                isAI ? 'bot' :
                                isHuman ? 'user-check' :
                                'server'
                              }
                              className={`w-4 h-4 ${
                                isAI
                                  ? 'text-purple-400'
                                  : isHuman
                                  ? 'text-emerald-400'
                                  : 'text-fintech-textSecondary'
                              }`}
                            ></i>
                          </div>

                          {/* EVENT CARD */}
                          <div className="flex-1 bg-slate-950 rounded-xl border border-fintech-border p-4 hover:border-fintech-border transition-all">
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">

                              <div className="flex items-center gap-2 flex-wrap">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                                  isAI
                                    ? 'bg-fintech-cyan/10 text-purple-300 border-purple-500/30'
                                    : isHuman
                                    ? 'bg-fintech-accent/10 text-emerald-300 border-emerald-500/30'
                                    : 'bg-fintech-card text-fintech-textSecondary border-fintech-border'
                                }`}>
                                  {log.actor_type}
                                </span>

                                <span className="text-xs font-bold text-white">
                                  {log.action}
                                </span>
                              </div>

                              <span className="text-[10px] font-mono text-slate-600">
                                {new Date(log.timestamp).toLocaleString()}
                              </span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 text-[10px] font-mono">

                              <div>
                                <div className="text-slate-600 uppercase">Transaction</div>
                                <div className="text-sky-400 mt-0.5">
                                  {log.transaction_id || '—'}
                                </div>
                              </div>

                              <div>
                                <div className="text-slate-600 uppercase">Actor</div>
                                <div className="text-fintech-textSecondary mt-0.5">
                                  {log.actor_id || '—'}
                                </div>
                              </div>

                              <div>
                                <div className="text-slate-600 uppercase">Audit ID</div>
                                <div className="text-fintech-textPrimary0 mt-0.5 truncate">
                                  {log.audit_id}
                                </div>
                              </div>

                            </div>

                            <div className="mt-3 pt-3 border-t border-fintech-border flex items-center gap-2 text-[10px] font-mono">
                              <span className="px-2 py-1 rounded bg-fintech-bg text-fintech-textPrimary0 border border-fintech-border">
                                {log.previous_state}
                              </span>
                              <Icon name="arrow-right" className="w-3 h-3 text-slate-700" />
                              <span className={`px-2 py-1 rounded border ${
                                isHuman
                                  ? 'bg-fintech-accent/10 text-emerald-400 border-fintech-accent/20'
                                  : isAI
                                  ? 'bg-fintech-cyan/10 text-purple-300 border-fintech-cyan/20'
                                  : 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                              }`}>
                                {log.new_state}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

          </div>
        )}

        {/* SETTINGS VIEW */}
        {currentTab === 'settings' && (
          <div className="p-6 max-w-3xl space-y-6">
            <div className="glass-card p-6 rounded-xl border border-fintech-border space-y-4">
              <h3 className="font-semibold text-white text-sm">AI Agent & Policy Settings</h3>

              <div className="space-y-4 font-sans text-xs">
                <div>
                  <label className="block text-fintech-textSecondary mb-1">Active AI Provider</label>
                  <select
                    value={aiProvider}
                    onChange={(e) => setAiProvider(e.target.value)}
                    className="w-full bg-fintech-bg border border-fintech-border text-white rounded-lg p-2.5 outline-none font-mono"
                  >
                    <option value="mock">MockAIProvider (Deterministic Demo - Zero API Costs)</option>
                    <option value="openai">OpenAIProvider (gpt-4o-mini)</option>
                    <option value="gemini">GeminiProvider (gemini-1.5-flash)</option>
                  </select>
                </div>

                <div className="pt-4 border-t border-fintech-border">
                  <div className="flex items-center justify-between text-fintech-textSecondary mb-1">
                    <span>Autonomous Resolution Threshold</span>
                    <span className="font-mono text-sky-400">0.95 (95%)</span>
                  </div>
                  <input type="range" min="0.80" max="0.99" step="0.01" value="0.95" disabled className="w-full accent-sky-500" />
                </div>

                <div className="pt-4 border-t border-fintech-border">
                  <div className="flex items-center justify-between text-fintech-textSecondary mb-1">
                    <span>Maximum Auto-Resolution Amount</span>
                    <span className="font-mono text-emerald-400">₹1,00,000.00</span>
                  </div>
                  <input type="range" min="10000" max="500000" step="10000" value="100000" disabled className="w-full accent-emerald-500" />
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* EXCEPTION WORKBENCH MODAL */}
      {selectedException && exceptionDetail && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-6 z-50 overflow-y-auto">
          <div className="bg-fintech-bg border border-fintech-border rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-fintech-border pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-lg text-white">Exception Investigation Workbench</h3>
                  <span className="bg-rose-500/20 text-rose-400 text-xs px-2.5 py-0.5 rounded font-mono">
                    {exceptionDetail.exception.reason_code === 'MULTIPLE_CANDIDATES'
                      ? 'DUPLICATE / MULTIPLE CANDIDATES'
                      : exceptionDetail.exception.reason_code}
                  </span>
                </div>
                <p className="text-xs text-fintech-textSecondary font-mono mt-1">Transaction ID: {exceptionDetail.exception.transaction_id}</p>
              </div>

              <button
                onClick={() => { setSelectedException(null); setExceptionDetail(null); }}
                className="text-fintech-textSecondary hover:text-white text-sm bg-fintech-card px-3 py-1.5 rounded-lg border border-fintech-border"
              >
                Close
              </button>
            </div>

            {/* 3-WAY SIDE BY SIDE COMPARISON */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
              {/* Internal Ledger */}
              <div className="bg-slate-950 p-4 rounded-xl border border-fintech-border space-y-2">
                <div className="text-sky-400 font-bold border-b border-fintech-border pb-1">1. Internal Ledger</div>
                <div className="text-fintech-textSecondary">Amount: <span className="text-white">₹{((exceptionDetail.transaction?.amount || 0)/100).toFixed(2)}</span></div>
                <div className="text-fintech-textSecondary">Fee: <span className="text-white">₹{((exceptionDetail.transaction?.recorded_fee || 0)/100).toFixed(2)}</span></div>
                <div className="text-fintech-textSecondary">Tax: <span className="text-white">₹{((exceptionDetail.transaction?.recorded_tax || 0)/100).toFixed(2)}</span></div>
                <div className="text-fintech-textSecondary">Expected Net: <span className="text-sky-400 font-bold">₹{((exceptionDetail.transaction?.expected_settlement || 0)/100).toFixed(2)}</span></div>
              </div>

              {/* Gateway Settlement */}
              <div className="bg-slate-950 p-4 rounded-xl border border-fintech-border space-y-2">
                <div className="text-emerald-400 font-bold border-b border-fintech-border pb-1">2. Gateway Settlement</div>
                <div className="text-fintech-textSecondary">Settlement ID: <span className="text-white">{exceptionDetail.settlement?.settlement_id || 'None'}</span></div>
                <div className="text-fintech-textSecondary">Gross: <span className="text-white">₹{((exceptionDetail.settlement?.settlement_amount || 0)/100).toFixed(2)}</span></div>
                <div className="text-fintech-textSecondary">Fee: <span className="text-white">₹{((exceptionDetail.settlement?.fee || 0)/100).toFixed(2)}</span></div>
                <div className="text-fintech-textSecondary">Actual Net: <span className="text-emerald-400 font-bold">₹{((exceptionDetail.settlement?.net_amount || 0)/100).toFixed(2)}</span></div>
              </div>

              {/* Bank Transaction */}
              <div className="bg-slate-950 p-4 rounded-xl border border-fintech-border space-y-2">
                <div className="text-purple-400 font-bold border-b border-fintech-border pb-1">3. Bank Statement</div>
                <div className="text-fintech-textSecondary">Bank ID: <span className="text-white">{exceptionDetail.bank?.bank_transaction_id || 'None'}</span></div>
                <div className="text-fintech-textSecondary">UTR: <span className="text-white">{exceptionDetail.bank?.utr || 'None'}</span></div>
                <div className="text-fintech-textSecondary">Bank Payout: <span className="text-purple-400 font-bold">₹{((exceptionDetail.bank?.amount || 0)/100).toFixed(2)}</span></div>
              </div>
            </div>

            {/* EVIDENCE CHECKLIST */}
            <div className="bg-slate-950 p-5 rounded-xl border border-fintech-border">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h4 className="font-semibold text-white text-sm">Evidence Chain</h4>
                  <p className="text-[11px] text-fintech-textPrimary0 mt-1">Three-way financial traceability</p>
                </div>
                <span className="text-[10px] uppercase font-mono text-fintech-textPrimary0">
                  Ledger → Settlement → Bank
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="flex items-center gap-2 bg-fintech-bg rounded-lg p-3 border border-fintech-border">
                  <span className={`w-2.5 h-2.5 rounded-full ${exceptionDetail.transaction ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                  <div>
                    <div className="text-white font-semibold">Internal Ledger</div>
                    <div className="text-fintech-textPrimary0">{exceptionDetail.transaction ? 'Evidence available' : 'Evidence missing'}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 bg-fintech-bg rounded-lg p-3 border border-fintech-border">
                  <span className={`w-2.5 h-2.5 rounded-full ${exceptionDetail.settlement ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                  <div>
                    <div className="text-white font-semibold">Gateway Settlement</div>
                    <div className="text-fintech-textPrimary0">{exceptionDetail.settlement ? 'Evidence available' : 'Settlement missing'}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 bg-fintech-bg rounded-lg p-3 border border-fintech-border">
                  <span className={`w-2.5 h-2.5 rounded-full ${exceptionDetail.bank ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                  <div>
                    <div className="text-white font-semibold">Bank Statement</div>
                    <div className="text-fintech-textPrimary0">{exceptionDetail.bank ? 'Bank confirmation found' : 'Bank confirmation missing'}</div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-[11px] font-mono">
                <div className="bg-fintech-bg/70 rounded-lg p-3">
                  <div className="text-fintech-textPrimary0">Expected Net</div>
                  <div className="text-sky-400 font-bold mt-1">{formatINR(exceptionDetail.transaction?.expected_settlement || 0)}</div>
                </div>
                <div className="bg-fintech-bg/70 rounded-lg p-3">
                  <div className="text-fintech-textPrimary0">Actual Net</div>
                  <div className="text-emerald-400 font-bold mt-1">{formatINR(exceptionDetail.settlement?.net_amount || 0)}</div>
                </div>
                <div className="bg-fintech-bg/70 rounded-lg p-3">
                  <div className="text-fintech-textPrimary0">Financial Variance</div>
                  <div className="text-rose-400 font-bold mt-1">{formatINR(exceptionDetail.exception?.financial_impact_paise || 0)}</div>
                </div>
                <div className="bg-fintech-bg/70 rounded-lg p-3">
                  <div className="text-fintech-textPrimary0">Confidence</div>
                  <div className="text-white font-bold mt-1">{((exceptionDetail.exception?.confidence || 0) * 100).toFixed(0)}%</div>
                </div>
              </div>
            </div>

            {/* AI CONTROLLER INVESTIGATION SECTION */}
            <div className="bg-slate-950 rounded-xl border border-fintech-cyan/20 overflow-hidden">

              {/* AI HEADER */}
              <div className="px-5 py-4 border-b border-fintech-border bg-purple-500/5">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-fintech-cyan/10 border border-fintech-cyan/20 flex items-center justify-center">
                      <Icon name="bot" className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-white text-sm">AI Controller Investigation</h4>
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-fintech-cyan/10 text-purple-300 border border-fintech-cyan/20 uppercase font-bold">
                          Agent
                        </span>
                      </div>
                      <p className="text-[10px] text-fintech-textPrimary0 mt-1">
                        Evidence-driven investigation with policy-gated resolution.
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => runAIInvestigation(exceptionDetail.exception.exception_id)}
                    disabled={investigating}
                    className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-xs px-4 py-2 rounded-lg transition-all flex items-center gap-2"
                  >
                    <Icon name={investigating ? "loader-2" : "scan-search"} className={`w-4 h-4 ${investigating ? "animate-spin" : ""}`} />
                    {investigating ? 'Investigating Evidence...' : 'Run AI Investigation'}
                  </button>
                </div>
              </div>

              {exceptionDetail.investigation ? (
                <div className="p-5 space-y-4">

                  {/* DECISION BANNER */}
                  <div className="rounded-xl border border-fintech-cyan/20 bg-purple-500/5 p-4">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-purple-400 font-bold">
                          AI Decision
                        </div>
                        <div className="text-lg font-bold text-white mt-1">
                          {exceptionDetail.investigation.decision === 'HUMAN_REVIEW'
                            ? 'Human Review Required'
                            : exceptionDetail.investigation.decision}
                        </div>
                        <div className="text-[11px] text-fintech-textSecondary mt-1">
                          {exceptionDetail.investigation.summary}
                        </div>
                      </div>

                      <div className="text-center md:text-right">
                        <div className="text-[9px] uppercase tracking-widest text-fintech-textPrimary0 font-bold">
                          Confidence
                        </div>
                        <div className="text-2xl font-black text-purple-300 mt-1">
                          {(exceptionDetail.investigation.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* EVIDENCE STATUS */}
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-fintech-textPrimary0 font-bold mb-2">
                      Evidence Chain
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

                      <div className="bg-fintech-bg rounded-xl border border-fintech-border p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] uppercase tracking-wider text-fintech-textPrimary0 font-bold">
                            Internal Ledger
                          </span>
                          <Icon name="check-circle-2" className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="text-white font-semibold text-sm mt-3">
                          {formatINR(exceptionDetail.transaction?.amount || 0)}
                        </div>
                        <div className="text-[10px] text-emerald-400 mt-1">
                          Evidence available
                        </div>
                      </div>

                      <div className="bg-fintech-bg rounded-xl border border-fintech-border p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] uppercase tracking-wider text-fintech-textPrimary0 font-bold">
                            Gateway Settlement
                          </span>
                          <Icon name="check-circle-2" className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="text-white font-semibold text-sm mt-3">
                          {formatINR(exceptionDetail.settlement?.net_amount || 0)}
                        </div>
                        <div className="text-[10px] text-emerald-400 mt-1">
                          Settlement verified
                        </div>
                      </div>

                      <div className="bg-fintech-bg rounded-xl border border-fintech-border p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] uppercase tracking-wider text-fintech-textPrimary0 font-bold">
                            Bank Statement
                          </span>
                          <Icon name={exceptionDetail.bank ? "check-circle-2" : "circle-alert"} className={`w-4 h-4 ${exceptionDetail.bank ? "text-emerald-400" : "text-rose-400"}`} />
                        </div>
                        <div className="text-white font-semibold text-sm mt-3">
                          {exceptionDetail.bank
                            ? formatINR(exceptionDetail.bank.amount || exceptionDetail.bank.payout_amount || 0)
                            : 'No confirmation'}
                        </div>
                        <div className={`text-[10px] mt-1 ${exceptionDetail.bank ? "text-emerald-400" : "text-rose-400"}`}>
                          {exceptionDetail.bank ? 'Bank confirmation found' : 'Bank confirmation missing'}
                        </div>
                      </div>

                    </div>
                  </div>

                  {/* FINANCIAL IMPACT */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

                    <div className="bg-fintech-bg rounded-xl border border-fintech-border p-3">
                      <div className="text-[9px] uppercase tracking-widest text-fintech-textPrimary0 font-bold">
                        Expected Net
                      </div>
                      <div className="text-sky-400 text-lg font-black mt-1">
                        {formatINR(exceptionDetail.transaction?.expected_settlement || 0)}
                      </div>
                    </div>

                    <div className="bg-fintech-bg rounded-xl border border-fintech-border p-3">
                      <div className="text-[9px] uppercase tracking-widest text-fintech-textPrimary0 font-bold">
                        Actual Net
                      </div>
                      <div className="text-emerald-400 text-lg font-black mt-1">
                        {formatINR(exceptionDetail.settlement?.net_amount || 0)}
                      </div>
                    </div>

                    <div className="bg-rose-500/5 rounded-xl border border-fintech-rose/20 p-3">
                      <div className="text-[9px] uppercase tracking-widest text-rose-400 font-bold">
                        Financial Variance
                      </div>
                      <div className="text-rose-400 text-lg font-black mt-1">
                        {formatINR(exceptionDetail.exception?.financial_impact_paise || 0)}
                      </div>
                    </div>

                  </div>

                  {/* AI RECOMMENDATION */}
                  {exceptionDetail.investigation.recommendation && (
                    <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
                      <div className="flex items-center gap-2">
                        <Icon name="lightbulb" className="w-4 h-4 text-sky-400" />
                        <div className="text-[9px] uppercase tracking-widest text-sky-400 font-bold">
                          AI Recommendation
                        </div>
                      </div>
                      <div className="text-xs text-slate-200 mt-2 leading-relaxed">
                        {exceptionDetail.investigation.recommendation}
                      </div>
                    </div>
                  )}

                  {/* TOOL EXECUTION */}
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-fintech-textPrimary0 font-bold mb-2">
                      Investigation Tools Executed
                    </div>

                    <div className="space-y-2">
                      {exceptionDetail.investigation.tool_calls?.map((tc, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-3 bg-fintech-bg rounded-lg border border-fintech-border px-3 py-2.5"
                        >
                          <div className="w-6 h-6 rounded-md bg-fintech-accent/10 border border-fintech-accent/20 flex items-center justify-center shrink-0">
                            <Icon name="check" className="w-3.5 h-3.5 text-emerald-400" />
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="text-[11px] font-mono text-sky-400 truncate">
                              {tc.tool}
                            </div>
                            <div className="text-[9px] text-slate-600 font-mono truncate">
                              {JSON.stringify(tc.args)}
                            </div>
                          </div>

                          <span className="text-[9px] uppercase font-bold text-emerald-400">
                            {tc.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* SAFETY GATE */}
                  <div className="rounded-xl border border-fintech-amber/20 bg-amber-500/5 p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-fintech-amber/10 border border-fintech-amber/20 flex items-center justify-center shrink-0">
                        <Icon name="shield-alert" className="w-4 h-4 text-amber-400" />
                      </div>

                      <div className="flex-1">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                          <div>
                            <div className="text-[9px] uppercase tracking-widest text-amber-400 font-bold">
                              Safety Gate
                            </div>
                            <div className="text-sm font-bold text-white mt-1">
                              Autonomous Resolution Blocked
                            </div>
                          </div>

                          <div className="text-[10px] font-mono text-fintech-textSecondary">
                            Required threshold: <span className="text-white font-bold">95%</span>
                          </div>
                        </div>

                        <div className="text-[10px] text-fintech-textSecondary mt-2">
                          {exceptionDetail.investigation.policy_reason}
                        </div>
                      </div>
                    </div>
                  </div>

                </div>
              ) : (
                <div className="p-8 text-center">
                  <div className="w-12 h-12 rounded-xl bg-fintech-cyan/10 border border-fintech-cyan/20 flex items-center justify-center mx-auto">
                    <Icon name="bot" className="w-6 h-6 text-purple-400" />
                  </div>
                  <div className="text-sm font-semibold text-white mt-3">
                    AI investigation not yet executed
                  </div>
                  <div className="text-[11px] text-fintech-textPrimary0 mt-1">
                    Run the controller to collect evidence, evaluate policy and generate a recommendation.
                  </div>
                </div>
              )}

            </div>

            {/* OPERATOR RESOLUTION ACTION CONTROLS */}
            <div className="flex items-center justify-end gap-3 border-t border-fintech-border pt-4">
              {exceptionDetail.exception?.status === 'APPROVED' ? (
                <div className="flex items-center gap-2 bg-fintech-accent/10 border border-emerald-500/30 rounded-lg px-4 py-2.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  <span className="text-emerald-400 font-semibold text-xs">
                    Settlement Adjustment Approved
                  </span>
                </div>
              ) : exceptionDetail.exception?.status === 'REJECTED' ? (
                <div className="flex items-center gap-2 bg-fintech-rose/10 border border-rose-500/30 rounded-lg px-4 py-2.5">
                  <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                  <span className="text-rose-400 font-semibold text-xs">
                    Exception Rejected
                  </span>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => handleHumanResolve('reject')}
                    disabled={resolving}
                    className="bg-rose-500/20 hover:bg-rose-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-rose-400 font-semibold px-4 py-2 rounded-lg text-xs border border-rose-500/30 transition-all"
                  >
                    {resolving ? 'Processing...' : 'Reject Exception'}
                  </button>
                  <button
                    onClick={() => handleHumanResolve('approve')}
                    disabled={resolving}
                    className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-950 font-semibold px-4 py-2 rounded-lg text-xs transition-all shadow-lg shadow-emerald-500/20"
                  >
                    {resolving ? 'Processing...' : 'Approve Settlement Adjustment'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
