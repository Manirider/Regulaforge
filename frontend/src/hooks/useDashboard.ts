import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { DashboardOverview } from "@/types/dashboard";

const staticOverview: DashboardOverview = {
  metrics: [
    { id: "1", label: "Compliance Rate", value: 94, previous_value: 91, change_percentage: 3.3, trend: "up", icon: "shield" },
    { id: "2", label: "Open Findings", value: 23, previous_value: 28, change_percentage: -17.9, trend: "down", icon: "alert" },
    { id: "3", label: "Active Regulations", value: 156, previous_value: 148, change_percentage: 5.4, trend: "up", icon: "clipboard" },
    { id: "4", label: "Entities Monitored", value: 48, previous_value: 45, change_percentage: 6.7, trend: "up", icon: "building" },
  ],
  recent_activity: [
    { id: "1", type: "regulation", description: "GDPR update v2.1 published", user_name: "Admin", timestamp: new Date(Date.now() - 900000).toISOString(), metadata: {} },
    { id: "2", type: "assessment", description: "Q4 Compliance Assessment completed", user_name: "John Doe", timestamp: new Date(Date.now() - 7200000).toISOString(), metadata: {} },
    { id: "3", type: "document", description: "SOC 2 Report uploaded", user_name: "Jane Smith", timestamp: new Date(Date.now() - 18000000).toISOString(), metadata: {} },
    { id: "4", type: "user", description: "New user onboarded: Sarah Wilson", user_name: "Admin", timestamp: new Date(Date.now() - 86400000).toISOString(), metadata: {} },
  ],
  compliance_rate: 94,
  open_findings: 23,
  active_regulations: 156,
  entities_monitored: 48,
};

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: async () => {
      const { data } = await apiClient.get<DashboardOverview>("/dashboard/overview");
      return data;
    },
    staleTime: 60_000,
    retry: 1,
    placeholderData: staticOverview,
  });
}

export function useComplianceTrend() {
  return useQuery({
    queryKey: ["dashboard", "charts", "compliance-trend"],
    queryFn: async () => {
      const { data } = await apiClient.get("/dashboard/charts/compliance-trend");
      return data as Array<{ date: string; compliance: number; target: number }>;
    },
    staleTime: 60_000,
    retry: 1,
    placeholderData: [
      { date: "Jan", compliance: 85, target: 90 },
      { date: "Feb", compliance: 87, target: 90 },
      { date: "Mar", compliance: 86, target: 90 },
      { date: "Apr", compliance: 89, target: 90 },
      { date: "May", compliance: 91, target: 92 },
      { date: "Jun", compliance: 90, target: 92 },
      { date: "Jul", compliance: 92, target: 92 },
      { date: "Aug", compliance: 94, target: 93 },
      { date: "Sep", compliance: 93, target: 93 },
      { date: "Oct", compliance: 95, target: 94 },
      { date: "Nov", compliance: 94, target: 94 },
      { date: "Dec", compliance: 96, target: 95 },
    ],
  });
}

export function useRiskDistribution() {
  return useQuery({
    queryKey: ["dashboard", "charts", "risk-distribution"],
    queryFn: async () => {
      const { data } = await apiClient.get("/dashboard/charts/risk-distribution");
      return data as Array<{ name: string; value: number; color: string }>;
    },
    staleTime: 60_000,
    retry: 1,
    placeholderData: [
      { name: "Low", value: 45, color: "#22c55e" },
      { name: "Medium", value: 30, color: "#eab308" },
      { name: "High", value: 18, color: "#f97316" },
      { name: "Critical", value: 7, color: "#ef4444" },
    ],
  });
}

export function useFindingsTrend() {
  return useQuery({
    queryKey: ["dashboard", "charts", "findings-trend"],
    queryFn: async () => {
      const { data } = await apiClient.get("/dashboard/charts/findings-trend");
      return data as Array<{ month: string; open: number; closed: number }>;
    },
    staleTime: 60_000,
    retry: 1,
    placeholderData: [
      { month: "Jul", open: 12, closed: 8 },
      { month: "Aug", open: 15, closed: 11 },
      { month: "Sep", open: 10, closed: 14 },
      { month: "Oct", open: 8, closed: 12 },
      { month: "Nov", open: 6, closed: 10 },
      { month: "Dec", open: 9, closed: 13 },
    ],
  });
}

export function useCoverage() {
  return useQuery({
    queryKey: ["dashboard", "charts", "coverage"],
    queryFn: async () => {
      const { data } = await apiClient.get("/dashboard/charts/coverage");
      return data as Array<{ name: string; value: number; fill: string }>;
    },
    staleTime: 60_000,
    retry: 1,
    placeholderData: [
      { name: "GDPR", value: 92, fill: "#6366f1" },
      { name: "SOC 2", value: 88, fill: "#22c55e" },
      { name: "ISO 27001", value: 76, fill: "#f97316" },
      { name: "PCI DSS", value: 95, fill: "#06b6d4" },
      { name: "HIPAA", value: 70, fill: "#eab308" },
    ],
  });
}
