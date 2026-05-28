import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LaneIntakeForm from "../components/portal/LaneIntakeForm";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("LaneIntakeForm", () => {
  it("renders all required fields", () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    expect(screen.getByLabelText(/origin city/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/destination city/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/equipment type/i)).toBeInTheDocument();
  });

  it("submit button is disabled when required fields are empty", () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    const btn = screen.getByRole("button", { name: /Create Lane/i });
    expect(btn).toBeDisabled();
  });

  it("submit button becomes enabled when all required fields are filled", async () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    fireEvent.change(screen.getByLabelText(/origin city/i), {
      target: { value: "Chicago" },
    });
    fireEvent.change(screen.getByLabelText(/origin state/i), {
      target: { value: "IL" },
    });
    fireEvent.change(screen.getByLabelText(/destination city/i), {
      target: { value: "Dallas" },
    });
    fireEvent.change(screen.getByLabelText(/destination state/i), {
      target: { value: "TX" },
    });
    fireEvent.change(screen.getByLabelText(/Equipment Type/i), {
      target: { value: "dry_van" },
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Create Lane/i })).not.toBeDisabled();
    });
  });

  it("shows validation error on blur for short city", async () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    const input = screen.getByLabelText(/origin city/i);
    fireEvent.change(input, { target: { value: "A" } });
    fireEvent.blur(input);
    await waitFor(() => {
      expect(screen.getByText(/at least 2 characters/i)).toBeInTheDocument();
    });
  });

  it("shows validation error on blur for invalid state code", async () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    const stateInput = screen.getByLabelText(/origin state/i);
    fireEvent.change(stateInput, { target: { value: "ILL" } });
    fireEvent.blur(stateInput);
    await waitFor(() => {
      expect(screen.getByText(/2-letter code/i)).toBeInTheDocument();
    });
  });

  it("can add and remove intermediate stops", () => {
    render(<LaneIntakeForm onCreated={() => {}} />, { wrapper });
    fireEvent.click(screen.getByText("+ Add Stop"));
    expect(screen.getByLabelText(/Stop 1 city/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Remove stop 1/i));
    expect(screen.queryByLabelText(/Stop 1 city/i)).not.toBeInTheDocument();
  });

  it("shows Cancel button when onCancel is provided", () => {
    const onCancel = vi.fn();
    render(<LaneIntakeForm onCreated={() => {}} onCancel={onCancel} />, { wrapper });
    const cancelBtn = screen.getByRole("button", { name: /Cancel/i });
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
