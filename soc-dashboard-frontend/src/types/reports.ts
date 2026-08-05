export interface ReportSummary {
  report_type: string;
  title: string;
  available_formats: string[];
}

export interface ReportGenerateRequest {
  report_type: string;
  start_date?: string;
  end_date?: string;
  incident_id?: string;
  format: "json" | "csv" | "pdf";
}
