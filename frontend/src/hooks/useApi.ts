import { useCallback, useEffect, useState } from "react";
import type { ApiError } from "../api/client";

export type AsyncState<T> =
  | { status: "LOADING"; data: null; error: null }
  | { status: "READY"; data: T; error: null }
  | { status: "EMPTY"; data: null; error: null }
  | { status: "ERROR"; data: null; error: ApiError };

// Generic loader for one-shot GET endpoints with LOADING/READY/EMPTY/ERROR.
export function useApi<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
): { state: AsyncState<T>; reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({
    status: "LOADING",
    data: null,
    error: null,
  });

  const load = useCallback(() => {
    let alive = true;
    setState({ status: "LOADING", data: null, error: null });
    fn()
      .then((data) => {
        if (!alive) return;
        const isEmpty = Array.isArray(data)
          ? data.length === 0
          : typeof data === "object" &&
            data !== null &&
            "items" in data &&
            (data as { items: unknown[] }).items.length === 0;
        setState(
          isEmpty
            ? ({ status: "EMPTY", data: null, error: null } as AsyncState<T>)
            : ({ status: "READY", data, error: null } as AsyncState<T>),
        );
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setState({ status: "ERROR", data: null, error: e as ApiError });
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => load(), [load]);

  return { state, reload: load };
}