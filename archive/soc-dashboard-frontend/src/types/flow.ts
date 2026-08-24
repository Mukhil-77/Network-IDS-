// Mirrors backend/api/schemas.py's FlowHistoryResponse/PaginatedFlowsResponse.

export interface FlowRow {
  id: string;
  protocol: string;
  source_ip: string;
  destination_ip: string;
  source_port: number;
  destination_port: number;
  start_time: string;
  end_time: string;
  packet_count: number;
  byte_count: number;
}

export interface PaginatedFlows {
  items: FlowRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface FlowFilters {
  source_ip?: string;
  destination_ip?: string;
  protocol?: string;
  page?: number;
  page_size?: number;
}
