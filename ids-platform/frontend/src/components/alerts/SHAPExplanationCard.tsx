import { SHAPExplanation, SHAPFeature } from "../../types/alert";

interface SHAPExplanationCardProps {
  explanation: SHAPExplanation | null;
  className?: string;
}

export function SHAPExplanationCard({ explanation, className = "" }: SHAPExplanationCardProps) {
  if (!explanation || explanation.top_features.length === 0) {
    return (
      <div className={`bg-surface-raised rounded-xl p-4 ${className}`}>
        <p className="text-sm text-slate-500 text-center py-8">
          No explanation available for this prediction.
        </p>
      </div>
    );
  }

  const positiveFeatures = explanation.top_features.filter(f => f.impact === "positive");
  const negativeFeatures = explanation.top_features.filter(f => f.impact === "negative");

  return (
    <div className={`bg-surface-raised rounded-xl p-4 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-100">
          Why was this classified as <span className="font-mono text-signal">{explanation.predicted_class}</span>?
        </h3>
        <span className="text-xs text-slate-500">
          Confidence: {explanation.confidence.toFixed(1)}%
        </span>
      </div>

      <div className="space-y-3">
        {positiveFeatures.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-emerald-400 mb-2 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              Factors increasing likelihood
            </h4>
            <div className="space-y-2">
              {positiveFeatures.slice(0, 5).map((feat, idx) => (
                <SHAPFeatureBar key={idx} feature={feat} color="emerald" />
              ))}
            </div>
          </div>
        )}

        {negativeFeatures.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-400" />
              Factors decreasing likelihood
            </h4>
            <div className="space-y-2">
              {negativeFeatures.slice(0, 5).map((feat, idx) => (
                <SHAPFeatureBar key={idx} feature={feat} color="red" />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface SHAPFeatureBarProps {
  feature: { feature: string; shap_value: number; magnitude: number; impact: string };
  color: "emerald" | "red";
}

function SHAPFeatureBar({ feature, color }: SHAPFeatureBarProps) {
  const barWidth = Math.min(100, Math.abs(feature.shap_value) * 100);
  
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-300 w-24 truncate">{feature.feature}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            color === "emerald" ? "bg-emerald-500" : "bg-red-500"
          }`}
          style={{ width: `${Math.min(100, Math.abs(feature.shap_value) * 100)}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-400 w-10 text-right">
        {feature.shap_value > 0 ? "+" : ""}{feature.shap_value.toFixed(3)}
      </span>
    </div>
  );
}