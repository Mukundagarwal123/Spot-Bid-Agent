import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PortalPage from "./pages/PortalPage";
import "./components/portal/portal.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PortalPage />
    </QueryClientProvider>
  );
}
