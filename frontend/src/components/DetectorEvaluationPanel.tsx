import { Panel, PanelHeader, StatusBadge, Notice, EmptyState } from "./ui";
import { LoadingState, ErrorState } from "./states";
import { useAsync } from "../hooks/useAsync";
import { api, DetectorMetrics, DetectorModelReport } from "../lib/api";
import { conditionLabel, formatAuc, weakestCondition } from "../lib/evaluation";

function MetricsTable({ name, model }: { name: string; model: DetectorModelReport }) {
  if (model.accuracy === undefined) {
    return (
      <div className="space-y-1">
        <p className="text-[13px] font-semibold text-ink break-all">{name}</p>
        <p className="text-[12px] text-muted">No image could be scored by this model ({model.unscored} unscored).</p>
      </div>
    );
  }
  const overall = model as DetectorMetrics;
  const rows: [string, DetectorMetrics][] = [["All images", overall], ...Object.entries(model.by_condition ?? {}).map(([k, v]) => [conditionLabel(k), v] as [string, DetectorMetrics])];
  const weak = weakestCondition(model);
  const [[tn, fp], [fn, tp]] = overall.confusion_matrix;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[13px] font-semibold text-ink break-all">{name}</p>
        {model.unscored > 0 && <StatusBadge tone="amber">{model.unscored} unscored</StatusBadge>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] text-left">
          <caption className="sr-only">Detector metrics for {name}, overall and per image condition</caption>
          <thead>
            <tr className="text-muted border-b border-border/60">
              <th scope="col" className="py-2 pr-3 font-medium">Condition</th>
              <th scope="col" className="py-2 pr-3 font-medium">Images</th>
              <th scope="col" className="py-2 pr-3 font-medium">Accuracy</th>
              <th scope="col" className="py-2 pr-3 font-medium">Precision</th>
              <th scope="col" className="py-2 pr-3 font-medium">Recall</th>
              <th scope="col" className="py-2 pr-3 font-medium">F1</th>
              <th scope="col" className="py-2 font-medium">ROC-AUC</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, m], i) => (
              <tr key={label} className={`border-b border-border/40 last:border-0 ${i === 0 ? "font-semibold text-ink" : "text-ink"}`}>
                <th scope="row" className="py-2 pr-3 font-medium">{label}</th>
                <td className="py-2 pr-3">{m.samples}</td>
                <td className="py-2 pr-3">{m.accuracy}%</td>
                <td className="py-2 pr-3">{m.precision}%</td>
                <td className="py-2 pr-3">{m.recall}%</td>
                <td className="py-2 pr-3">{m.f1}%</td>
                <td className="py-2">{formatAuc(m.roc_auc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {model.ci && (
        <p className="text-[12px] text-muted">
          95% intervals (a range, not a guarantee):{" "}
          {(["accuracy", "recall", "specificity"] as const).map((k, i) => {
            const x = model.ci?.metrics[k];
            if (!x || x.low === null || x.high === null) return null;
            return <span key={k}>{i > 0 && " · "}{k} <span className="font-medium text-ink">{x.point}% ({x.low} to {x.high})</span></span>;
          })}
          {model.threshold !== undefined && <> · threshold {model.threshold}%</>}
        </p>
      )}
      {weak && (
        <p className="text-[12px] text-muted">
          Weakest measured condition: <span className="font-medium text-ink">{conditionLabel(weak.condition)}</span> (F1 {weak.f1}%).
        </p>
      )}
      <p className="text-[11.5px] text-muted">
        Confusion matrix: real classed real {tn}, real classed fake {fp}, fake classed real {fn}, fake classed fake {tp}.
      </p>
    </div>
  );
}

export default function DetectorEvaluationPanel({ compact = false }: { compact?: boolean }) {
  const { data, loading, error, reload } = useAsync(() => api.detectorEvaluationLatest(), []);

  return (
    <Panel className="p-5 sm:p-6 space-y-4">
      <PanelHeader
        title="Detector evaluation"
        subtitle="Measured on a labelled image set, including re-compressed, resized, cropped and screenshot copies."
        right={data?.available && data.report
          ? (data.smoke_test
            ? <StatusBadge tone="amber">Smoke test, not a result</StatusBadge>
            : <StatusBadge tone="green">Measured {data.report.generated_at.slice(0, 10)}</StatusBadge>)
          : <StatusBadge tone="amber">Not measured yet</StatusBadge>}
      />
      {loading && <LoadingState label="Loading evaluation…" />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && (
        <>
          <p className="text-[12px] text-muted break-all">
            Primary model: <span className="font-medium text-ink">{data.configured_models.primary}</span>
            {data.configured_models.second
              ? <> · Second model: <span className="font-medium text-ink">{data.configured_models.second}</span> · Ensemble active</>
              : <> · No second model configured, so there is no ensemble</>}
          </p>
          {!data.available || !data.report ? (
            <EmptyState
              title="No evaluation has been run"
              description={data.how_to_generate ?? "Run the evaluation to see accuracy and limits here."}
            />
          ) : (
            <>
              <p className="text-[12px] text-muted">
                {data.report.protocol && data.report.originals_test !== undefined
                  ? <>{data.report.images_test} held-out test images from {data.report.originals_test} originals (threshold chosen on {data.report.originals_calib} separate originals)</>
                  : <>{data.report.images} images · decision threshold {data.report.threshold}%</>}
                {" "}· sources: {data.report.sources.join(", ")}
              </p>
              {data.smoke_test && (
                <Notice tone="warning">
                  This set is too small to quote. Treat these numbers as a check that the pipeline works, not as how well the detector performs.
                </Notice>
              )}
              <div className="space-y-6">
                {Object.entries(data.report.models).slice(0, compact ? 1 : undefined).map(([name, m]) => (
                  <MetricsTable key={name} name={name} model={m} />
                ))}
              </div>
              {compact && Object.keys(data.report.models).length > 1 && (
                <p className="text-[11.5px] text-muted">Showing the first model. Settings → Detector compares every model.</p>
              )}
              <Notice tone="warning">{data.report.warning}</Notice>
            </>
          )}
        </>
      )}
    </Panel>
  );
}
