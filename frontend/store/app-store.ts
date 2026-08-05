import { create } from "zustand";

type AppState = {
  graphFilter: "all" | "impacted" | "critical";
  selectedProviderId: string | null;
  setGraphFilter: (filter: AppState["graphFilter"]) => void;
  setSelectedProviderId: (providerId: string | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  graphFilter: "all",
  selectedProviderId: null,
  setGraphFilter: (graphFilter) => set({ graphFilter }),
  setSelectedProviderId: (selectedProviderId) => set({ selectedProviderId })
}));

